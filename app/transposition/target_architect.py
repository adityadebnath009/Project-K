"""
app/transposition/target_architect.py - Phase 7A Layer 3: LLM Target Architect.

Interprets the factual TargetEvidenceManifest using structured LLM output
to produce a TargetRepositoryProfile.
"""
from typing import Any
import json
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from app.config import settings
from app.schemas.transposition import (
    TargetEvidenceManifest,
    TargetRepositoryProfile,
)

TARGET_ARCHITECT_SYSTEM_PROMPT = """You are a Principal Software Architect specializing in Python architecture reverse engineering.
Your task is to analyze a factual TARGET EVIDENCE MANIFEST and produce a structured TARGET REPOSITORY PROFILE.

MANDATORY RULES:
1. Ground every conclusion in the provided evidence. DO NOT hallucinate files, symbols, or frameworks that are not in the manifest.
2. If evidence is ambiguous, set confidence lower (< 0.7) and document the question in unresolved_questions.
3. architectural_style: If entities, repositories, and services are separated into distinct layers, classify architectural_style as "Clean Architecture".
4. orm: Identify ORM from declared dependencies (e.g. "SQLAlchemy" -> "sqlalchemy_2.0", "tortoise", "django_orm", or "none").
5. dto_pattern: Identify DTO from declared dependencies (e.g. "pydantic" -> "pydantic_v2", "dataclasses", or "attrs").
6. components: You MUST populate 4 to 8 ComponentAssessment items from production_classes_by_layer. DO NOT return an empty list.
   For each component:
   - component_id: use the exact "file_path:ClassName" coordinate (e.g. "entities/user.py:User")
   - role: entry_point, domain_model, data_access, business_logic, data_contract, test_suite, infrastructure, or unknown
   - confidence: float between 0.0 and 1.0 (e.g. 0.95)
   - rationale: clear explanation grounded in the evidence
7. reusable_services: MUST list at least 3 reusable service symbols using "file_path:ClassName" (e.g. "services/conversation_service.py:ConversationService").
8. existing_domain_models: MUST list at least 3 domain models using "file_path:ClassName" (e.g. "entities/user.py:User").
"""


class TargetArchitect:
    """
    Synthesizes structural facts into an architectural profile using structured LLM output.
    """

    def __init__(self, llm: Any | None = None) -> None:
        base_url = settings.ai_base_url.rstrip("/").removesuffix("/v1")
        self.llm = llm or ChatOllama(
            base_url=base_url,
            model=settings.model_name,
            temperature=0,
        )
        self.structured_llm = self.llm.with_structured_output(TargetRepositoryProfile)

    def analyze_manifest(self, manifest: TargetEvidenceManifest) -> TargetRepositoryProfile:
        """
        Interprets the factual evidence manifest and returns a structured TargetRepositoryProfile.
        """
        # Separate non-test production inheritance and decorators for high signal
        prod_inheritance = {
            k: v for k, v in manifest.inheritance_map.items() if not k.startswith("test/")
        }
        prod_decorators = {
            k: v for k, v in manifest.decorators_by_symbol.items() if not k.startswith("test/")
        }

        # Group production classes by top-level layer (e.g. entities, services, repositories)
        prod_classes_by_layer: dict[str, list[str]] = {}
        for sym_id in prod_inheritance.keys():
            if ":" in sym_id:
                f_path, cls_name = sym_id.split(":", 1)
                layer = f_path.split("/")[0] if "/" in f_path else "root"
                prod_classes_by_layer.setdefault(layer, []).append(f"{f_path}:{cls_name}")

        non_test_files = [f for f in manifest.imports_by_file.keys() if not f.startswith("test/")]

        key_framework_deps = [
            d for d in manifest.declared_dependencies
            if any(k in d.lower() for k in ["sqlalchemy", "alembic", "pydantic", "fastapi", "flask", "django", "pytest", "tortoise"])
        ]

        evidence_summary = {
            "target_root": manifest.target_root,
            "files_scanned": manifest.total_files_scanned,
            "key_framework_dependencies": key_framework_deps,
            "declared_dependencies": manifest.declared_dependencies,
            "call_resolution_rate": f"{manifest.call_resolution_rate * 100:.1f}%",
            "production_layers": list(prod_classes_by_layer.keys()),
            "production_classes_by_layer": {k: v[:8] for k, v in prod_classes_by_layer.items()},
            "sample_inheritance": dict(list(manifest.inheritance_map.items())[:30]),
            "sample_decorators": dict(list(manifest.decorators_by_symbol.items())[:30]),
            "sample_imports": {k: v[:5] for k, v in list(manifest.imports_by_file.items())[:25]},
            "sample_production_files": sorted(non_test_files)[:30],
        }

        user_content = (
            f"Analyze the following evidence manifest of the target codebase and generate the TargetRepositoryProfile.\n"
            f"IMPORTANT:\n"
            f"- Identify the architectural_style (e.g. 'Clean Architecture' if entities/repositories/services are separated, 'Layered MVC', 'Flat Library').\n"
            f"- Identify orm (e.g. 'sqlalchemy_2.0' from SQLAlchemy in dependencies), dto_pattern (e.g. 'pydantic_v2' from pydantic in dependencies), and test_framework ('pytest').\n"
            f"- Identify 4 to 8 key production components using the full 'file_path:ClassName' coordinate from production_classes_by_layer and classify each as domain_model, data_access, business_logic, data_contract, or infrastructure.\n"
            f"- List key reusable services (e.g. ConversationService, TokenCounter) and existing domain models (e.g. User, Conversation).\n\n"
            f"```json\n{json.dumps(evidence_summary, indent=2)}\n```"
        )

        messages = [
            SystemMessage(content=TARGET_ARCHITECT_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]

        result = self.structured_llm.invoke(messages)
        if isinstance(result, TargetRepositoryProfile):
            return result

        # Fallback if raw dict is returned
        return TargetRepositoryProfile.model_validate(result)