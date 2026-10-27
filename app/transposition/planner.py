"""
planner.py - Adaptation Planner (Phase 7B Module 2).
Compares FrameworkAgnosticIR with TargetRepositoryProfile to generate an AdaptationPlan
with typed decisions: REUSE, EXTEND, CREATE, and ADAPT.
Uses evidence-based convention mapping from TargetConventionMap and TargetEvidenceManifest.
Provides the plan_adaptation_node for LangGraph StateGraph execution.
"""
import re
from typing import Any

from app.inference.ollama_client import OllamaClient
from app.schemas.transposition import (
    AdaptationPlan,
    ComponentAction,
    ComponentMapping,
    FrameworkAgnosticIR,
    TargetEvidenceManifest,
    TargetLayer,
    TargetRepositoryProfile,
    TranspositionState,
)

# Standard capability provider registry mapping abstract capabilities to supported libraries
CAPABILITY_PROVIDERS: dict[str, dict[str, Any]] = {
    "PASSWORD_HASHING": {
        "keywords": ["hash", "password", "bcrypt", "verify_password", "hash_password"],
        "supported": ["bcrypt", "argon2-cffi", "passlib[bcrypt]", "passlib", "hashlib"],
        "default": "passlib[bcrypt]",
    },
    "TOKEN_SIGNING": {
        "keywords": ["jwt", "token", "encode", "decode", "bearer", "access_token"],
        "supported": ["python-jose[cryptography]", "python-jose", "pyjwt", "authlib"],
        "default": "python-jose[cryptography]",
    },
    "QUEUE_SCHEDULING": {
        "keywords": ["redis", "queue", "rq", "celery", "enqueue", "requeue"],
        "supported": ["redis", "rq", "celery", "dramatiq"],
        "default": "redis",
    },
    "RETRY_BACKOFF": {
        "keywords": ["retry", "backoff", "stop_after_attempt", "wait_exponential"],
        "supported": ["tenacity", "backoff", "retry"],
        "default": "tenacity",
    },
}


class AdaptationPlanner:
    """
    Evidence-based architectural planner that maps FrameworkAgnosticIR to target codebase conventions.
    """

    def __init__(self, inference_client: OllamaClient | None = None) -> None:
        self.inference_client = inference_client

    def plan(
        self,
        ir: FrameworkAgnosticIR,
        target_profile: TargetRepositoryProfile,
        target_manifest: TargetEvidenceManifest | None = None,
    ) -> AdaptationPlan:
        """
        Generates an AdaptationPlan from the IR, target profile, and dependency manifest.
        Attempts structured LLM alignment; falls back to evidence-based deterministic rule matching.
        """
        # Step 1: Deterministic Pre-Matching using TargetConventionMap
        pre_mappings, pre_deps, schema_diff = self._deterministic_pre_match(
            ir=ir,
            profile=target_profile,
            manifest=target_manifest,
        )

        # Step 2: Attempt LLM Synthesis if client is configured
        if self.inference_client and self.inference_client.is_available():
            try:
                llm_plan = self._llm_synthesize_plan(
                    ir=ir,
                    profile=target_profile,
                    pre_mappings=pre_mappings,
                    pre_deps=pre_deps,
                )
                if self._validate_plan(llm_plan, target_profile):
                    return llm_plan
            except Exception:
                # LLM synthesis failed; gracefully continue to deterministic plan
                pass

        # Step 3: Deterministic Fallback & Validation
        plan = AdaptationPlan(
            feature_name=ir.feature_name,
            target_root=target_profile.target_root,
            mappings=pre_mappings,
            new_dependencies=pre_deps,
            schema_diff_summary=schema_diff,
        )
        self._validate_plan(plan, target_profile)
        return plan

    def _deterministic_pre_match(
        self,
        ir: FrameworkAgnosticIR,
        profile: TargetRepositoryProfile,
        manifest: TargetEvidenceManifest | None,
    ) -> tuple[list[ComponentMapping], list[str], str]:
        """Evidence-based architectural matching against target conventions."""
        mappings: list[ComponentMapping] = []
        feature_slug = re.sub(r"[^a-zA-Z0-9_]", "_", ir.feature_name.lower()).strip("_")
        schema_diff_lines: list[str] = []
        conventions = profile.conventions

        existing_models_lower = {m.lower(): m for m in profile.existing_domain_models}

        # 1. Map DataContracts -> Entities or Schemas (Evidence-Based DTO detection)
        for contract in ir.contracts:
            matched_model = None
            c_name_lower = contract.name.lower()
            for em_lower, em_orig in existing_models_lower.items():
                if em_lower in c_name_lower or c_name_lower in em_lower:
                    matched_model = em_orig
                    break

            is_dto = any(suffix in c_name_lower for suffix in conventions.dto_suffixes)

            if matched_model and not is_dto:
                # REUSE existing domain entity at its discovered directory
                entity_dir = conventions.get_layer_dir(TargetLayer.ENTITY)
                entity_file = self._find_component_path(profile, matched_model, entity_dir)
                mappings.append(
                    ComponentMapping(
                        source_id=contract.name,
                        target_layer=TargetLayer.ENTITY,
                        action=ComponentAction.REUSE,
                        target_file_path=entity_file,
                        target_symbol_name=matched_model,
                        description=f"Reuse existing domain model '{matched_model}' in target architecture.",
                    )
                )
                schema_diff_lines.append(f"Entity '{matched_model}': Reused as-is without database migrations.")
            else:
                # CREATE target schema (DTO) using dynamic convention path
                schema_file = conventions.get_file_path(TargetLayer.SCHEMA, feature_slug)
                mappings.append(
                    ComponentMapping(
                        source_id=contract.name,
                        target_layer=TargetLayer.SCHEMA,
                        action=ComponentAction.CREATE,
                        target_file_path=schema_file,
                        target_symbol_name=contract.name,
                        description=f"Create Pydantic v2 DTO '{contract.name}' for data transfer.",
                    )
                )
                field_names = [f.name for f in contract.fields]
                schema_diff_lines.append(f"Schema '{contract.name}': New DTO with fields {field_names}")

        # 2. Map Repositories -> EXTEND using Discovered Naming Pattern
        has_reused_entity = any(
            m.action == ComponentAction.REUSE and m.target_layer == TargetLayer.ENTITY for m in mappings
        )
        if has_reused_entity:
            reused_sym = next(m.target_symbol_name for m in mappings if m.action == ComponentAction.REUSE)
            expected_repo_name = conventions.format_repo_name(reused_sym)
            repo_dir = conventions.get_layer_dir(TargetLayer.REPOSITORY_IMPL)

            # Discover existing repo class name if present in components
            existing_repo_sym = next(
                (
                    c.component_id.split(":")[-1]
                    for c in profile.components
                    if f"{reused_sym.lower()}repo" in c.component_id.lower()
                    or expected_repo_name.lower() in c.component_id.lower()
                ),
                expected_repo_name,
            )
            repo_file = self._find_component_path(profile, existing_repo_sym, repo_dir)
            mappings.append(
                ComponentMapping(
                    source_id=f"{reused_sym}Repository",
                    target_layer=TargetLayer.REPOSITORY_IMPL,
                    action=ComponentAction.EXTEND,
                    target_file_path=repo_file,
                    target_symbol_name=existing_repo_sym,
                    description=f"Extend '{existing_repo_sym}' with feature-specific query methods.",
                )
            )

        # 3. Map Algorithms -> Target Services using Discovered Service Naming Pattern
        for algo in ir.algorithms:
            service_class_name = conventions.service_naming_pattern.format(
                symbol="".join(word.capitalize() for word in feature_slug.split("_"))
            )
            service_file = conventions.get_file_path(TargetLayer.SERVICE, f"{feature_slug}_service")
            mappings.append(
                ComponentMapping(
                    source_id=algo.name,
                    target_layer=TargetLayer.SERVICE,
                    action=ComponentAction.CREATE,
                    target_file_path=service_file,
                    target_symbol_name=service_class_name,
                    description=f"Create service orchestrator '{service_class_name}' implementing '{algo.name}'.",
                )
            )

        # 4. Dependency Capability Diffing (Checks Target pyproject.toml / requirements.txt)
        new_deps = self._infer_required_libraries(ir, manifest)

        diff_summary = "\n".join(schema_diff_lines) if schema_diff_lines else "No schema changes required."
        return mappings, new_deps, diff_summary

    def _infer_required_libraries(
        self,
        ir: FrameworkAgnosticIR,
        manifest: TargetEvidenceManifest | None,
    ) -> list[str]:
        """
        Detects required capabilities and checks if target already satisfies them.
        Only suggests new libraries if the target repository lacks the capability.
        """
        algo_text = " ".join([f"{a.name} {' '.join(s.description for s in a.steps)}" for a in ir.algorithms]).lower()
        declared = set(d.lower() for d in (manifest.declared_dependencies if manifest else []))

        needed_libs: list[str] = []
        for cap_name, cap_meta in CAPABILITY_PROVIDERS.items():
            if any(k in algo_text for k in cap_meta["keywords"]):
                # Check if any supported library for this capability is already declared in target
                already_satisfied = any(
                    any(sup.split("[")[0].lower() in dec for dec in declared)
                    for sup in cap_meta["supported"]
                )
                if not already_satisfied:
                    needed_libs.append(cap_meta["default"])

        return sorted(needed_libs)

    def _find_component_path(self, profile: TargetRepositoryProfile, symbol_name: str, default_dir: str) -> str:
        """Finds the relative file path for an existing component in the target profile."""
        # 1. Exact symbol match within the target layer directory
        for comp in profile.components:
            comp_path, comp_sym = comp.component_id.split(":", 1) if ":" in comp.component_id else (comp.component_id, "")
            if comp_path.startswith(default_dir) and comp_sym.lower() == symbol_name.lower():
                return comp_path

        # 2. Exact symbol match anywhere in profile
        for comp in profile.components:
            comp_path, comp_sym = comp.component_id.split(":", 1) if ":" in comp.component_id else (comp.component_id, "")
            if comp_sym.lower() == symbol_name.lower():
                return comp_path

        # 3. Substring match within the target layer directory
        for comp in profile.components:
            comp_path, comp_sym = comp.component_id.split(":", 1) if ":" in comp.component_id else (comp.component_id, "")
            if comp_path.startswith(default_dir) and symbol_name.lower() in comp_sym.lower():
                return comp_path

        return f"{default_dir}/{symbol_name.lower().replace('repository', '_repo')}.py"

    def _llm_synthesize_plan(
        self,
        ir: FrameworkAgnosticIR,
        profile: TargetRepositoryProfile,
        pre_mappings: list[ComponentMapping],
        pre_deps: list[str],
    ) -> AdaptationPlan:
        """Uses Ollama structured output to refine architectural mappings."""
        prompt = (
            f"You are the FeatureForge Adaptation Planner. Plan the transposition of feature '{ir.feature_name}' "
            f"into a target Python codebase with architectural style: {profile.architectural_style}, "
            f"ORM: {profile.orm}, and DTO pattern: {profile.dto_pattern}.\n\n"
            f"Existing Target Domain Models: {profile.existing_domain_models}\n"
            f"Reusable Services: {profile.reusable_services}\n\n"
            f"Framework-Agnostic IR:\n"
            f"- Contracts: {[c.name for c in ir.contracts]}\n"
            f"- Algorithms: {[a.name for a in ir.algorithms]}\n\n"
            f"Pre-matched candidate mappings: {[m.model_dump() for m in pre_mappings]}\n"
            f"Pre-inferred dependencies: {pre_deps}\n\n"
            f"Synthesize an exact AdaptationPlan adhering strictly to Clean Architecture separation."
        )
        return self.inference_client.generate_structured(prompt, AdaptationPlan)

    def _validate_plan(self, plan: AdaptationPlan, profile: TargetRepositoryProfile) -> bool:
        """Validates that all mappings in the plan strictly conform to target conventions."""
        if not plan.mappings:
            raise ValueError("AdaptationPlan must contain at least one ComponentMapping.")

        conventions = profile.conventions
        for mapping in plan.mappings:
            expected_layer_dir = conventions.get_layer_dir(mapping.target_layer)
            if not mapping.target_file_path.startswith(expected_layer_dir):
                filename = mapping.target_file_path.split("/")[-1]
                mapping.target_file_path = f"{expected_layer_dir}/{filename}"

        return True


def plan_adaptation_node(state: TranspositionState) -> dict[str, Any]:
    """
    LangGraph node: Computes the AdaptationPlan comparing FrameworkAgnosticIR
    against the target repository's architectural profile.
    """
    ir = state.get("ir")
    if not ir:
        raise ValueError("Cannot plan adaptation: 'ir' is missing from TranspositionState.")

    target_profile = state.get("target_profile")
    if not target_profile:
        raise ValueError("Cannot plan adaptation: 'target_profile' is missing from TranspositionState.")

    target_manifest = state.get("target_manifest")

    planner = AdaptationPlanner()
    plan = planner.plan(
        ir=ir,
        target_profile=target_profile,
        target_manifest=target_manifest,
    )

    return {"plan": plan}
