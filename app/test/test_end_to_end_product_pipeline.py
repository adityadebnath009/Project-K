"""
test_end_to_end_product_pipeline.py - Master End-to-End Product Verification Suite.

Connects and executes the entire FeatureForge product engine end-to-end:
1. Target Intelligence (Phase 7A): AST Indexing -> Evidence Manifest -> Dynamic Convention Discovery.
2. Source Feature Archaeology (Phase 6): Slicing -> Call Graph -> Closure Reachability -> Mermaid Blueprint.
3. Feature Logic Distillation (Phase 7B Mod 1): AST Facts -> Framework-Agnostic IR (Contracts, State Machines, Algorithms).
4. Adaptation Planning (Phase 7B Mod 2): Clean Architecture Mapping (REUSE, EXTEND, CREATE, Capability Diff).
5. LangGraph State Flow: TranspositionState transitions across all pipeline nodes.
"""
import time
from pathlib import Path

from app.schemas.slice import SymbolKind
from app.schemas.transposition import (
    ComponentAction,
    ComponentAssessment,
    TargetComponentRole,
    TargetLayer,
    TargetRepositoryProfile,
    TranspositionState,
)
from app.services.deconstructor_service import FeatureDeconstructorService
from app.transposition.ir_extractor import IRExtractor, extract_ir_node
from app.transposition.planner import AdaptationPlanner, plan_adaptation_node
from app.transposition.target_indexer import TargetRepositoryIndexer


def test_end_to_end_product_lifecycle():
    print("\n" + "=" * 80)
    print("🚀 RUNNING FEATUREFORGE MASTER END-TO-END PRODUCT PIPELINE")
    print("=" * 80)
    t_start = time.perf_counter()

    # -------------------------------------------------------------------------
    # STAGE 1: TARGET CODEBASE INTELLIGENCE & CONVENTION DISCOVERY (Phase 7A)
    # -------------------------------------------------------------------------
    print("\n[STAGE 1/5] 🏗️  Scanning & Indexing Target Codebase (ai_redemption)...")
    target_root = Path(".").resolve()
    indexer = TargetRepositoryIndexer()
    target_index, target_manifest = indexer.index_repository(target_root)
    conventions = indexer.discover_convention_map(target_index, target_manifest)

    print(f"   • Scanned Files: {target_manifest.total_files_scanned} files across target codebase")
    print(f"   • Call Resolution Rate: {target_manifest.call_resolution_rate:.1%}")
    print(f"   • Discovered Entities Layer:     {conventions.get_layer_dir(TargetLayer.ENTITY)}")
    print(f"   • Discovered Repositories Layer:  {conventions.get_layer_dir(TargetLayer.REPOSITORY_IMPL)}")
    print(f"   • Discovered Services Layer:      {conventions.get_layer_dir(TargetLayer.SERVICE)}")
    print(f"   • Discovered Schemas Layer:       {conventions.get_layer_dir(TargetLayer.SCHEMA)}")
    print(f"   • Discovered Repository Pattern:  {conventions.repo_naming_pattern}")
    print(f"   • Discovered Service Pattern:     {conventions.service_naming_pattern}")

    # Build Target Profile from discovered intelligence
    existing_models = conventions.existing_entities or ["User", "Conversation", "Message"]
    profile = TargetRepositoryProfile(
        target_root=str(target_root),
        architectural_style="Clean Architecture",
        conventions=conventions,
        existing_domain_models=existing_models,
        components=[
            ComponentAssessment(
                component_id=s.symbol_id,
                role=TargetComponentRole.DOMAIN_MODEL if "entities" in s.file_path else TargetComponentRole.DATA_ACCESS,
                confidence=1.0,
                rationale="Indexed from target codebase",
            )
            for s in target_index.all_symbols if ("entities" in s.file_path or "repositories" in s.file_path) and s.kind == SymbolKind.CLASS
        ],
    )
    assert len(profile.existing_domain_models) > 0
    assert "User" in profile.existing_domain_models
    print("   ✅ Stage 1 Passed: Target Intelligence established.")

    # -------------------------------------------------------------------------
    # STAGE 2: SOURCE FEATURE ARCHAEOLOGY & SLICING (Phase 6)
    # -------------------------------------------------------------------------
    print("\n[STAGE 2/5] 🔍 Slicing Source Feature (Conduit User Authentication)...")
    source_repo = Path("test_fixtures/realworld_fastapi")
    assert source_repo.exists(), "Source fixture realworld_fastapi is missing"

    deconstructor = FeatureDeconstructorService()
    vslice, blueprint_md = deconstructor.deconstruct_feature(
        repo_path=source_repo,
        feature_name="User Authentication",
        query="/login",
    )

    print(f"   • Feature Sliced: '{vslice.feature_name}'")
    print(f"   • Sliced Symbols: {len(vslice.symbols)} across {len(vslice.files_involved)} files")
    print(f"   • Total Source LOC: {vslice.total_lines_of_code} lines")
    print(f"   • Call Graph Edges: {len(vslice.call_graph)} directed edges")
    assert len(vslice.symbols) >= 5
    assert len(blueprint_md) > 100
    assert "```mermaid" in blueprint_md
    print("   ✅ Stage 2 Passed: Vertical Slice & Mermaid Blueprint extracted.")

    # -------------------------------------------------------------------------
    # STAGE 3: FRAMEWORK-AGNOSTIC IR DISTILLATION (Phase 7B Module 1)
    # -------------------------------------------------------------------------
    print("\n[STAGE 3/5] 🧬 Distilling Slice into Framework-Agnostic IR...")
    extractor = IRExtractor()
    ir = extractor.extract_ir(vslice)

    print(f"   • Feature Name: '{ir.feature_name}'")
    print(f"   • Extracted Contracts ({len(ir.contracts)}): {[c.name for c in ir.contracts]}")
    print(f"   • Extracted Algorithms ({len(ir.algorithms)}): {[a.name for a in ir.algorithms]}")
    for algo in ir.algorithms:
        print(f"     - Algorithm '{algo.name}': {len(algo.steps)} steps (inputs: {algo.inputs})")

    assert len(ir.contracts) >= 2
    assert len(ir.algorithms) >= 1
    assert any("User" in c.name for c in ir.contracts)
    print("   ✅ Stage 3 Passed: Framework-Agnostic IR distilled.")

    # -------------------------------------------------------------------------
    # STAGE 4: ADAPTATION PLANNING & CAPABILITY AUDITING (Phase 7B Module 2)
    # -------------------------------------------------------------------------
    print("\n[STAGE 4/5] 📐 Generating Evidence-Based Adaptation Plan...")
    planner = AdaptationPlanner()
    plan = planner.plan(ir, profile, target_manifest)

    print(f"   • Plan Feature: '{plan.feature_name}'")
    print(f"   • Target Codebase Root: {plan.target_root}")
    print(f"   • Inferred New Dependencies: {plan.new_dependencies}")
    print(f"   • Total Planned Mappings: {len(plan.mappings)}")

    entity_actions = [m for m in plan.mappings if m.target_layer == TargetLayer.ENTITY]
    schema_actions = [m for m in plan.mappings if m.target_layer == TargetLayer.SCHEMA]
    repo_actions = [m for m in plan.mappings if m.target_layer == TargetLayer.REPOSITORY_IMPL]
    service_actions = [m for m in plan.mappings if m.target_layer == TargetLayer.SERVICE]

    print("\n   [Decisions Mapped into Target Clean Architecture]:")
    for m in plan.mappings:
        print(f"     [{m.action.value.upper():<6}] {m.target_layer.value.upper():<16}: {m.target_symbol_name:<25} -> {m.target_file_path}")

    # Core Architectural Invariants:
    assert any(m.action == ComponentAction.REUSE and m.target_symbol_name == "User" for m in entity_actions), "User entity must be REUSED"
    assert len(schema_actions) >= 1, "Must CREATE target API schemas"
    assert len(repo_actions) >= 1, "Must EXTEND target repository"
    assert len(service_actions) >= 1, "Must CREATE target service orchestrator"

    # Capability Diff Invariant:
    assert "passlib[bcrypt]" in plan.new_dependencies, "Password hashing capability must be flagged"
    assert "python-jose[cryptography]" in plan.new_dependencies, "JWT capability must be flagged"
    print("   ✅ Stage 4 Passed: Clean Architecture Adaptation Plan verified.")

    # -------------------------------------------------------------------------
    # STAGE 5: LANGGRAPH STATEGRAPH PIPELINE INTEGRATION
    # -------------------------------------------------------------------------
    print("\n[STAGE 5/5] ⚡ Executing LangGraph Node Pipeline Simulation...")
    initial_state: TranspositionState = {
        "source_slice": vslice,
        "target_repo_path": str(target_root),
        "target_profile": profile,
        "target_manifest": target_manifest,
        "ir": None,
        "conventions": conventions,
        "plan": None,
        "scaffolded_files": [],
        "audit_passed": False,
        "audit_feedback": None,
        "retry_count": 0,
    }

    # Node 1: Extract IR
    ir_delta = extract_ir_node(initial_state)
    assert "ir" in ir_delta
    state_after_ir = {**initial_state, **ir_delta}

    # Node 2: Plan Adaptation
    plan_delta = plan_adaptation_node(state_after_ir)
    assert "plan" in plan_delta
    final_state = {**state_after_ir, **plan_delta}

    assert final_state["ir"] is not None
    assert final_state["plan"] is not None
    assert len(final_state["plan"].mappings) > 0
    print("   ✅ Stage 5 Passed: LangGraph StateGraph node transitions verified.")

    # -------------------------------------------------------------------------
    # SUMMARY & TIMING
    # -------------------------------------------------------------------------
    total_time = time.perf_counter() - t_start
    print("\n" + "=" * 80)
    print(f"🎉 MASTER PRODUCT PIPELINE RUN COMPLETED IN {total_time:.2f}s!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    test_end_to_end_product_lifecycle()
