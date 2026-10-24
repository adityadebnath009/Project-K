"""
app/transposition/profile_validator.py - Phase 7A Layer 4: Deterministic Profile Validator.

Verifies that all files and symbols cited by the LLM Target Architect actually
exist in the ground-truth TargetCodebaseIndex. Filters out hallucinations.
"""
from dataclasses import dataclass
from pathlib import Path

from app.schemas.transposition import (
    ComponentAssessment,
    EvidenceReference,
    TargetRepositoryProfile,
)
from app.transposition.target_indexer import TargetCodebaseIndex


@dataclass
class ValidationReport:
    """Audit report produced by the deterministic profile validator."""
    is_valid: bool
    verified_components_count: int
    rejected_components_count: int
    hallucinated_files: list[str]
    hallucinated_symbols: list[str]
    coverage_score: float


class ProfileValidator:
    """
    Deterministic safety layer that verifies LLM architectural assessments
    against the ground-truth AST index.
    """

    def validate_profile(
        self,
        profile: TargetRepositoryProfile,
        index: TargetCodebaseIndex,
    ) -> tuple[TargetRepositoryProfile, ValidationReport]:
        """
        Validates and sanitizes a TargetRepositoryProfile against a TargetCodebaseIndex.

        Returns:
            A tuple of (sanitized_profile, validation_report).
        """
        known_files = set(index.imports_by_file.keys())
        root_path = Path(index.target_root).resolve()

        hallucinated_files: list[str] = []
        hallucinated_symbols: list[str] = []
        verified_components: list[ComponentAssessment] = []
        rejected_components_count = 0

        # 1. Verify Components & Evidence
        for comp in profile.components:
            comp_id = comp.component_id.strip()
            comp_file = comp_id.split(":")[0]
            symbol_name = comp_id.split(":")[-1].split(".")[-1]

            if ":" in comp_id or "/" in comp_id or comp_file.endswith(".py"):
                # Path specified: the file must exist
                file_exists = (
                    comp_file in known_files
                    or (root_path / comp_file).exists()
                    or (root_path / f"{comp_file}.py").exists()
                )
                is_valid_comp = file_exists
            else:
                # Standalone symbol name or folder name
                file_exists = (
                    comp_id in known_files
                    or (root_path / comp_id).exists()
                    or (root_path / f"{comp_id}.py").exists()
                )
                symbol_exists = bool(index.symbol_table.find_by_name(comp_id))
                is_valid_comp = file_exists or symbol_exists

            if not is_valid_comp:
                hallucinated_files.append(comp_file)
                rejected_components_count += 1
                profile.unresolved_questions.append(
                    f"Hallucination Warning: LLM cited non-existent component '{comp_id}'."
                )
                continue

            # Verify individual evidence references
            verified_evidence: list[EvidenceReference] = []
            for ev in comp.evidence:
                ev_file = ev.file_path
                if (
                    ev_file in known_files
                    or (root_path / ev_file).exists()
                    or (root_path / f"{ev_file}.py").exists()
                ):
                    verified_evidence.append(ev)
                else:
                    hallucinated_files.append(ev_file)

            comp.evidence = verified_evidence
            verified_components.append(comp)

        def _symbol_in_table(name: str) -> bool:
            clean = name.split(":")[-1].split(".")[-1].strip()
            if index.symbol_table.find_by_name(clean):
                return True
            # Case-normalized / CamelCase check (e.g. user -> User, conversation_service -> ConversationService)
            camel = clean.replace("_", " ").title().replace(" ", "")
            return bool(index.symbol_table.find_by_name(camel))

        # 2. Verify Reusable Services & Domain Models against SymbolTable
        verified_services: list[str] = []
        for s in profile.reusable_services:
            if _symbol_in_table(s):
                verified_services.append(s)
            else:
                hallucinated_symbols.append(s)
                profile.unresolved_questions.append(
                    f"Warning: Reusable service '{s}' was not found in symbol table."
                )

        verified_models: list[str] = []
        for m in profile.existing_domain_models:
            if _symbol_in_table(m):
                verified_models.append(m)
            else:
                hallucinated_symbols.append(m)
                profile.unresolved_questions.append(
                    f"Warning: Domain model '{m}' was not found in symbol table."
                )

        # 3. Calculate Coverage & Safety Score
        total_proposed = len(profile.components)
        coverage_score = (
            len(verified_components) / total_proposed if total_proposed > 0 else 1.0
        )

        profile.components = verified_components
        profile.reusable_services = verified_services
        profile.existing_domain_models = verified_models
        profile.indexing_coverage_rate = round(coverage_score, 4)

        report = ValidationReport(
            is_valid=(len(hallucinated_files) == 0 and len(hallucinated_symbols) == 0),
            verified_components_count=len(verified_components),
            rejected_components_count=rejected_components_count,
            hallucinated_files=sorted(list(set(hallucinated_files))),
            hallucinated_symbols=sorted(list(set(hallucinated_symbols))),
            coverage_score=coverage_score,
        )

        return profile, report