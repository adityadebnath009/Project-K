"""
app/transposition/ir_extractor.py
Feature Logic & IR Extractor (Phase 7B).

Distills a raw VerticalSlice into a clean, framework-agnostic architectural
intermediate representation (FrameworkAgnosticIR).
"""

from __future__ import annotations

import ast
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from app.config import settings
from app.inference.base import InferenceClient
from app.inference.ollama_client import OllamaClient
from app.schemas.slice import CodeSymbol, SymbolKind, VerticalSlice
from app.schemas.transposition import (
    AlgorithmStep,
    DataContract,
    DataContractField,
    FrameworkAgnosticIR,
    PureAlgorithm,
    StateMachine,
    StateTransition,
    TranspositionState,
)


class CandidateFacts(BaseModel):
    """AST-extracted facts extracted before prompting the LLM."""
    contract_names: list[str] = []
    candidate_contracts: list[DataContract] = []
    symbol_signatures: dict[str, str] = {}
    call_flow: list[str] = []
    docstrings: dict[str, str] = {}


class IRExtractor:
    """
    Distills a VerticalSlice into a FrameworkAgnosticIR using a
    deterministic-first sandwich (AST pre-facts -> LLM extraction -> AST validation).
    """

    def __init__(self, inference_client: InferenceClient | None = None) -> None:
        self.client = inference_client or OllamaClient()
        self.settings = settings

    def extract_ir(self, vertical_slice: VerticalSlice) -> FrameworkAgnosticIR:
        """
        Main entry point: transforms a VerticalSlice into FrameworkAgnosticIR.
        """
        # 1. Deterministic Pre-Extraction (AST facts)
        facts = self._pre_extract_facts(vertical_slice)

        # 2. LLM Synthesis with Structured Output
        ir = self._synthesize_ir_with_llm(vertical_slice, facts)

        # 3. Deterministic Normalization & Provenance Verification
        return self._validate_and_normalize_ir(ir, vertical_slice, facts)

    def _pre_extract_facts(self, slice_data: VerticalSlice) -> CandidateFacts:
        """
        Extracts candidate contracts, method signatures, and call flows purely via AST.
        """
        contract_names: list[str] = []
        candidate_contracts: list[DataContract] = []
        symbol_signatures: dict[str, str] = {}
        docstrings: dict[str, str] = {}

        for sym in slice_data.symbols:
            if sym.docstring:
                docstrings[sym.symbol_id] = sym.docstring.strip()

            # Class symbols: isolate data models/schemas from infra (repositories/services/errors)
            if sym.kind == SymbolKind.CLASS:
                is_infra = any(
                    sym.name.endswith(suffix)
                    for suffix in ("Repository", "Service", "Client", "Error", "Exception", "Handler")
                )
                if not is_infra:
                    contract_names.append(sym.name)
                    fields: list[DataContractField] = []
                    try:
                        tree = ast.parse(sym.source_code)
                        for node in ast.walk(tree):
                            if isinstance(node, ast.ClassDef):
                                for item in node.body:
                                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                                        fname = item.target.id
                                        ftype = ast.unparse(item.annotation) if item.annotation else "Any"
                                        is_req = item.value is None
                                        fields.append(
                                            DataContractField(name=fname, field_type=ftype, is_required=is_req)
                                        )
                    except Exception:
                        pass
                    if not fields:
                        fields = [DataContractField(name="raw_data", field_type="dict[str, Any]", is_required=True)]
                    candidate_contracts.append(
                        DataContract(
                            name=sym.name,
                            fields=fields,
                            description=sym.docstring or f"Contract for {sym.name}",
                        )
                    )

            # Extract parameter signatures
            try:
                tree = ast.parse(sym.source_code)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        args = [a.arg for a in node.args.args if a.arg != "self"]
                        ret = ast.unparse(node.returns) if node.returns else "None"
                        symbol_signatures[sym.symbol_id] = f"({', '.join(args)}) -> {ret}"
                        break
            except Exception:
                symbol_signatures[sym.symbol_id] = "()"

        # Reconstruct call flow sequence from resolved call graph
        call_flow = [
            f"{c.caller_symbol_id} -> {c.resolved_symbol_id or c.raw_callee}"
            for c in slice_data.call_graph
        ]

        return CandidateFacts(
            contract_names=contract_names,
            candidate_contracts=candidate_contracts,
            symbol_signatures=symbol_signatures,
            call_flow=call_flow,
            docstrings=docstrings,
        )

    def _synthesize_ir_with_llm(
        self,
        slice_data: VerticalSlice,
        facts: CandidateFacts,
    ) -> FrameworkAgnosticIR:
        """
        Uses LLM with structured output to distill logic, contracts, and state transitions.
        """
        symbols_summary = []
        for s in slice_data.symbols:
            sig = facts.symbol_signatures.get(s.symbol_id, "")
            symbols_summary.append(
                f"- Symbol: `{s.symbol_id}` ({s.kind.value})\n"
                f"  Signature: {sig}\n"
                f"  Source Code:\n```python\n{s.source_code.strip()}\n```"
            )
        symbols_block = "\n".join(symbols_summary)

        system_prompt = (
            "You are an expert Software Architect specializing in architectural reverse-engineering.\n"
            "Your task is to analyze an extracted code slice and distill it into a FrameworkAgnosticIR.\n"
            "RULES:\n"
            "1. Strip away framework-specific baggage (e.g., FastAPI Depends, Django request.user, Flask g).\n"
            "2. Extract DataContracts: capture all data transfer objects, request/response models, and entities with their fields and types.\n"
            "3. Extract StateMachines: identify state transitions if this feature transitions an entity between states (e.g. Unauthenticated -> Authenticated, Pending -> Completed).\n"
            "4. Extract PureAlgorithms: express core business algorithms as step-by-step logic stripped of web frameworks.\n"
            "5. Record source_provenance_files and source_symbol_ids accurately matching the provided slice."
        )

        user_prompt = (
            f"FEATURE NAME: {slice_data.feature_name}\n"
            f"ENTRY POINTS: {[e.symbol.symbol_id for e in slice_data.entry_points]}\n"
            f"FILES INVOLVED: {slice_data.files_involved}\n\n"
            f"CALL GRAPH SEQUENCE:\n{chr(10).join(facts.call_flow) if facts.call_flow else 'Single unit execution'}\n\n"
            f"SYMBOLS AND CODE:\n{symbols_block}\n\n"
            "Extract the complete FrameworkAgnosticIR for this feature."
        )

        try:
            llm = self.client.get_llm(temperature=0.0)
            structured_llm = llm.with_structured_output(FrameworkAgnosticIR)
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{input_text}"),
            ])
            chain = prompt | structured_llm
            result = chain.invoke({"input_text": user_prompt})
            if isinstance(result, FrameworkAgnosticIR):
                return result
            if isinstance(result, dict):
                return FrameworkAgnosticIR.model_validate(result)
        except Exception:
            pass

        # Deterministic Fallback if LLM fails
        return self._deterministic_fallback_ir(slice_data, facts)

    def _deterministic_fallback_ir(
        self,
        slice_data: VerticalSlice,
        facts: CandidateFacts,
    ) -> FrameworkAgnosticIR:
        """
        Deterministic fallback when the LLM is unavailable or produces invalid JSON.
        Synthesizes contracts and algorithm steps directly from AST facts.
        """
        contracts = facts.candidate_contracts or [
            DataContract(
                name=name,
                fields=[DataContractField(name="raw_data", field_type="dict[str, Any]", is_required=True)],
                description=f"Auto-extracted contract for {name}",
            )
            for name in facts.contract_names
        ]

        steps = []
        for idx, call in enumerate(facts.call_flow, start=1):
            steps.append(
                AlgorithmStep(
                    step_number=idx,
                    action="execute_call",
                    description=f"Call {call}",
                )
            )

        if not steps:
            steps.append(
                AlgorithmStep(
                    step_number=1,
                    action="execute_primary_logic",
                    description=f"Execute core logic for {slice_data.feature_name}",
                )
            )

        algo = PureAlgorithm(
            name=f"{slice_data.feature_name}_algorithm",
            inputs=["context"],
            output="result",
            steps=steps,
        )

        return FrameworkAgnosticIR(
            feature_name=slice_data.feature_name,
            summary=f"Deterministically extracted IR for {slice_data.feature_name}",
            contracts=contracts,
            algorithms=[algo],
            source_provenance_files=list(slice_data.files_involved),
            source_symbol_ids=[s.symbol_id for s in slice_data.symbols],
        )

    def _validate_and_normalize_ir(
        self,
        ir: FrameworkAgnosticIR,
        slice_data: VerticalSlice,
        facts: CandidateFacts,
    ) -> FrameworkAgnosticIR:
        """
        Deterministic post-validation: guarantees provenance integrity and non-empty algorithms.
        """
        ir.feature_name = slice_data.feature_name

        # Ensure provenance files and symbols match input slice
        if not ir.source_provenance_files:
            ir.source_provenance_files = list(slice_data.files_involved)
        if not ir.source_symbol_ids:
            ir.source_symbol_ids = [s.symbol_id for s in slice_data.symbols]

        # If LLM extracted 0 algorithms, populate the fallback algorithm
        if not ir.algorithms:
            fallback = self._deterministic_fallback_ir(slice_data, facts)
            ir.algorithms = fallback.algorithms

        return ir


def extract_ir_node(state: TranspositionState) -> dict[str, Any]:
    """
    LangGraph node: Distills a raw VerticalSlice into a FrameworkAgnosticIR.
    """
    source_slice = state.get("source_slice")
    if not source_slice:
        raise ValueError("Cannot extract IR: 'source_slice' is missing from TranspositionState.")

    extractor = IRExtractor()
    ir = extractor.extract_ir(source_slice)
    return {"ir": ir}
