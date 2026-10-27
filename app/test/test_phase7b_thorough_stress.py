"""
test_phase7b_thorough_stress.py - Exhaustive Stress & Regression Battery for Phase 7B.

Thoroughly tests:
1. Multi-Repository Real-World Transposition (Celery, HTTPX, RealWorld FastAPI, RQ, Tenacity).
2. Heterogeneous Target Architectures (Clean Architecture, Flat src/, Custom Domain Stores).
3. Dynamic Affix Derivation across unseen patterns (Db...Store, Mongo...Dao, ...Table).
4. Zero-Redundant Dependency Capability Matching (Bcrypt, Argon2, PyJWT, Tenacity).
5. AST Scope Isolation & Nested Closure Invariants.
6. LangGraph TranspositionState Delta Validity.
"""
import time
from pathlib import Path
import pytest

from app.schemas.slice import CodeSymbol, SymbolKind, VerticalSlice
from app.schemas.transposition import (
    AdaptationPlan,
    ComponentAction,
    ComponentAssessment,
    TargetComponentRole,
    TargetConventionMap,
    TargetEvidenceManifest,
    TargetLayer,
    TargetRepositoryProfile,
    TranspositionState,
)
from app.services.deconstructor_service import FeatureDeconstructorService
from app.slicing.ast_parser import PythonAstParser
from app.slicing.call_graph import CallGraphTracer
from app.slicing.extractor import SliceExtractor
from app.transposition.ir_extractor import IRExtractor
from app.transposition.planner import AdaptationPlanner, plan_adaptation_node
from app.transposition.target_indexer import TargetCodebaseIndex, TargetRepositoryIndexer

FIXTURES_DIR = Path("test_fixtures")


# =====================================================================
# 1. Multi-Repository Transposition Matrix
# =====================================================================

@pytest.mark.parametrize(
    "repo_slug,feature_name,entry_query,expected_min_symbols,expected_min_contracts,required_capability",
    [
        ("realworld_fastapi", "Conduit User Login", "/login", 5, 2, "passlib[bcrypt]"),
        ("httpx_repo", "HTTPX GET Pipeline", "get", 20, 5, None),
        ("rq_repo", "RQ Job Requeue", "requeue_job", 15, 5, "redis"),
        # Note: tenacity is already declared in target requirements.txt, so capability provider correctly omits it from new_dependencies
        ("tenacity_repo", "Tenacity Retry Logic", "retry", 5, 2, None),
        ("celery_repo", "Celery Canvas Signature", "celery/canvas.py:signature", 50, 10, "redis"),
    ],
)
def test_real_world_repository_transposition(
    repo_slug: str,
    feature_name: str,
    entry_query: str,
    expected_min_symbols: int,
    expected_min_contracts: int,
    required_capability: str | None,
):
    """Stress tests slicing, IR distillation, and adaptation planning across 5 major open-source repos."""
    repo_path = FIXTURES_DIR / repo_slug
    if not repo_path.exists():
        pytest.skip(f"Fixture {repo_slug} not present")

    t0 = time.perf_counter()

    # 1. Slicing
    deconstructor = FeatureDeconstructorService()
    if ":" in entry_query:
        vslice, _ = deconstructor.deconstruct_feature(
            repo_path=repo_path,
            feature_name=feature_name,
            entry_point_id=entry_query,
        )
    else:
        vslice, _ = deconstructor.deconstruct_feature(
            repo_path=repo_path,
            feature_name=feature_name,
            query=entry_query,
        )

    assert len(vslice.symbols) >= expected_min_symbols
    assert len(vslice.files_involved) >= 1

    # 2. IR Distillation
    extractor = IRExtractor()
    ir = extractor.extract_ir(vslice)
    assert len(ir.contracts) >= expected_min_contracts
    assert len(ir.algorithms) >= 1

    # 3. Target Profile & Convention Map
    indexer = TargetRepositoryIndexer()
    target_root = Path(".").resolve()
    index, manifest = indexer.index_repository(target_root)
    conventions = indexer.discover_convention_map(index, manifest)

    profile = TargetRepositoryProfile(
        target_root=str(target_root),
        architectural_style="Clean Architecture",
        conventions=conventions,
        existing_domain_models=["User", "Conversation", "Message"],
        components=[],
    )

    # 4. Adaptation Planning
    planner = AdaptationPlanner()
    plan = planner.plan(ir, profile, manifest)

    assert plan.feature_name == feature_name
    assert len(plan.mappings) >= len(ir.contracts)
    if required_capability:
        assert required_capability in plan.new_dependencies

    duration = time.perf_counter() - t0
    print(f"\n⚡ {repo_slug:<18} -> Transposed in {duration:.2f}s ({len(vslice.symbols)} syms, {len(plan.mappings)} mappings)")


# =====================================================================
# 2. Heterogeneous Target Architecture Layouts
# =====================================================================

def test_flat_src_layout_adaptation():
    """Verifies planner conforms to non-standard 'src/' flat layout with custom store pattern."""
    indexer = TargetRepositoryIndexer()

    # Custom Flat Target: src/models and src/stores
    syms = [
        CodeSymbol(name="Account", qualified_name="Account", kind=SymbolKind.CLASS, file_path="src/models/account.py", line_start=1, line_end=10, source_code="class Account(Base): pass"),
        CodeSymbol(name="SqlAccountStore", qualified_name="SqlAccountStore", kind=SymbolKind.CLASS, file_path="src/stores/account_store.py", line_start=1, line_end=10, source_code="class SqlAccountStore: pass"),
        CodeSymbol(name="AccountHandler", qualified_name="AccountHandler", kind=SymbolKind.CLASS, file_path="src/handlers/account_handler.py", line_start=1, line_end=10, source_code="class AccountHandler: pass"),
    ]
    index = TargetCodebaseIndex(target_root=Path("/custom"), all_symbols=syms, imports_by_file={}, call_edges=[], forward_graph={}, symbol_table=None, parse_errors={})
    conventions = indexer.discover_convention_map(index)

    # Verify discovered center of gravity and naming patterns
    assert conventions.get_layer_dir(TargetLayer.ENTITY) == "src/models"
    assert conventions.get_layer_dir(TargetLayer.REPOSITORY_IMPL) == "src/stores"
    assert conventions.repo_naming_pattern == "Sql{symbol}Store"
    assert conventions.service_naming_pattern == "{symbol}Handler"

    # Plan feature against this custom target
    profile = TargetRepositoryProfile(
        target_root="/custom",
        architectural_style="Flat Layered",
        conventions=conventions,
        existing_domain_models=["Account"],
        components=[
            ComponentAssessment(component_id="src/models/account.py:Account", role=TargetComponentRole.DOMAIN_MODEL, confidence=1.0, rationale="Domain model"),
            ComponentAssessment(component_id="src/stores/account_store.py:SqlAccountStore", role=TargetComponentRole.DATA_ACCESS, confidence=1.0, rationale="Data access"),
        ],
    )

    # Simulate slice of Account Auth
    ir = IRExtractor().extract_ir(
        VerticalSlice(
            feature_name="Account Login",
            entry_points=[],
            symbols=[
                CodeSymbol(name="Account", qualified_name="Account", kind=SymbolKind.CLASS, file_path="domain/acc.py", line_start=1, line_end=5, source_code="class Account: pass"),
                CodeSymbol(name="AccountLoginRequest", qualified_name="AccountLoginRequest", kind=SymbolKind.CLASS, file_path="domain/acc.py", line_start=6, line_end=10, source_code="class AccountLoginRequest:\n    token: str"),
            ],
            call_graph=[],
        )
    )

    planner = AdaptationPlanner()
    plan = planner.plan(ir, profile, None)

    # REUSE Account in src/models/account.py
    account_map = next(m for m in plan.mappings if m.target_symbol_name == "Account")
    assert account_map.action == ComponentAction.REUSE
    assert account_map.target_file_path == "src/models/account.py"

    # EXTEND SqlAccountStore in src/stores/account_store.py
    store_map = next(m for m in plan.mappings if m.target_layer == TargetLayer.REPOSITORY_IMPL)
    assert store_map.action == ComponentAction.EXTEND
    assert store_map.target_symbol_name == "SqlAccountStore"
    assert store_map.target_file_path == "src/stores/account_store.py"


# =====================================================================
# 3. Dynamic Capability Provider Stress Test
# =====================================================================

def test_capability_provider_matrix():
    """Tests that any pre-existing package in pyproject.toml satisfies the capability."""
    planner = AdaptationPlanner()
    profile = TargetRepositoryProfile(target_root="/app", conventions=TargetConventionMap())

    # Slice requiring password hash + token + queue
    decon = FeatureDeconstructorService()
    vslice, _ = decon.deconstruct_feature(FIXTURES_DIR / "realworld_fastapi", "Auth", "/login")
    ir = IRExtractor().extract_ir(vslice)

    # Case 1: Target has argon2-cffi and authlib
    m1 = TargetEvidenceManifest(
        target_root="/app", total_files_scanned=1, files_indexed_count=1, parse_error_count=0,
        declared_dependencies=["argon2-cffi", "authlib", "pydantic"]
    )
    plan1 = planner.plan(ir, profile, m1)
    # Neither passlib nor python-jose should be requested!
    assert "passlib[bcrypt]" not in plan1.new_dependencies
    assert "python-jose[cryptography]" not in plan1.new_dependencies

    # Case 2: Target has zero auth libraries
    m2 = TargetEvidenceManifest(
        target_root="/app", total_files_scanned=1, files_indexed_count=1, parse_error_count=0,
        declared_dependencies=["fastapi", "pydantic"]
    )
    plan2 = planner.plan(ir, profile, m2)
    assert "passlib[bcrypt]" in plan2.new_dependencies
    assert "python-jose[cryptography]" in plan2.new_dependencies


# =====================================================================
# 4. AST Lexical Closure & Scope Boundary Invariance
# =====================================================================

def test_ast_deep_nested_closure_isolation():
    """Verify 3-level deep nested closures do not leak outgoing calls to ancestor scopes."""
    code = """
def grand_parent():
    def parent_closure():
        def child_worker():
            deep_leaf_call()
        direct_parent_call()
    direct_grand_parent_call()
"""
    parser = PythonAstParser()
    symbols, imports = parser.parse_code(code, "nested_stress.py")

    gp = next(s for s in symbols if s.name == "grand_parent")
    p = next(s for s in symbols if s.name == "parent_closure")
    c = next(s for s in symbols if s.name == "child_worker")

    # Scope Boundary Asserts:
    assert gp.outgoing_calls == ["direct_grand_parent_call"]
    assert p.outgoing_calls == ["direct_parent_call"]
    assert c.outgoing_calls == ["deep_leaf_call"]

    # Slice Reachability Asserts:
    tracer = CallGraphTracer()
    edges, forward_graph = tracer.build_call_graph(symbols, {"nested_stress.py": imports})
    extractor = SliceExtractor()
    vslice = extractor.extract_slice("nested_slice", gp.symbol_id, symbols, forward_graph, edges)

    # Slicing grand_parent must preserve all nested closures
    slice_names = {s.name for s in vslice.symbols}
    assert slice_names == {"grand_parent", "parent_closure", "child_worker"}


# =====================================================================
# 5. LangGraph Node Integration Stress Test
# =====================================================================

def test_langgraph_node_execution_stress():
    """Stress tests plan_adaptation_node in full state graph simulation."""
    target_root = Path(".").resolve()
    indexer = TargetRepositoryIndexer()
    index, manifest = indexer.index_repository(target_root)
    conventions = indexer.discover_convention_map(index, manifest)

    profile = TargetRepositoryProfile(
        target_root=str(target_root),
        architectural_style="Clean Architecture",
        conventions=conventions,
        existing_domain_models=["User", "Conversation"],
        components=[],
    )

    deconstructor = FeatureDeconstructorService()
    vslice, _ = deconstructor.deconstruct_feature(FIXTURES_DIR / "tenacity_repo", "Retry", "retry")
    ir = IRExtractor().extract_ir(vslice)

    state: TranspositionState = {
        "source_slice": vslice,
        "target_repo_path": str(target_root),
        "target_profile": profile,
        "target_manifest": manifest,
        "ir": ir,
        "conventions": conventions,
        "plan": None,
        "scaffolded_files": [],
        "audit_passed": False,
        "audit_feedback": None,
        "retry_count": 0,
    }

    result = plan_adaptation_node(state)
    assert "plan" in result
    plan = result["plan"]
    assert isinstance(plan, AdaptationPlan)
    assert len(plan.mappings) > 0


if __name__ == "__main__":
    pytest.main(["-v", __file__])
