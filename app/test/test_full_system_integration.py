import pytest
from pathlib import Path
from app.schemas.transposition import (
    TargetRepositoryProfile,
    TargetConventionMap,
    TargetLayer,
    TargetEvidenceManifest,
    ComponentAction
)
from app.services.deconstructor_service import FeatureDeconstructorService
from app.transposition.ir_extractor import IRExtractor
from app.transposition.planner import AdaptationPlanner

def test_end_to_end_real_repo_pipeline():
    """
    REAL INTEGRATION TEST:
    Source Repo (RealWorld FastAPI) -> Slicing -> IR -> Adaptation Plan (Custom Target)
    This test connects all services and verifies the actual output.
    """
    print("\n🚀 Starting Real-World System Integration Test...")

    # --- 1. SOURCE SLICING (Real Repository) ---
    source_repo_path = "test_fixtures/realworld_fastapi"
    deconstructor = FeatureDeconstructorService()
    
    # Deconstruct a real feature from the real repo
    vslice, blueprint_md = deconstructor.deconstruct_feature(
        repo_path=source_repo_path,
        feature_name="User Authentication",
        query="/login",
    )
    assert vslice is not None
    assert len(vslice.symbols) > 0
    print(f"✅ Step 1: Sliced {len(vslice.symbols)} symbols from real repo.")

    # --- 2. IR EXTRACTION (Distillation) ---
    ir_extractor = IRExtractor()
    ir = ir_extractor.extract_ir(vslice)
    assert ir is not None
    assert len(ir.contracts) > 0
    assert len(ir.algorithms) > 0
    print(f"✅ Step 2: Distilled into IR with {len(ir.contracts)} contracts.")

    # --- 3. TARGET PROFILE (Custom Conventions) ---
    # We simulate a target that is NOT like the source
    custom_conventions = TargetConventionMap(
        layer_directories={
            TargetLayer.ENTITY: "src/domain/models",
            TargetLayer.REPOSITORY_IMPL: "src/infra/repos",
            TargetLayer.SERVICE: "src/application/services",
            TargetLayer.SCHEMA: "src/application/dtos",
            TargetLayer.TEST: "tests/unit",
        },
        repo_naming_pattern="{symbol}Store",
        service_naming_pattern="{symbol}Manager",
    )
    
    target_profile = TargetRepositoryProfile(
        target_root="/workspace/target_app",
        architectural_style="Clean Architecture",
        conventions=custom_conventions,
        existing_domain_models=["User"], # Simulate existing entity
    )
    
    manifest = TargetEvidenceManifest(
        target_root="/workspace/target_app",
        total_files_scanned=10,
        files_indexed_count=10,
        parse_error_count=0,
        declared_dependencies=["fastapi", "sqlalchemy"],
    )

    # --- 4. ADAPTATION PLANNING ---
    planner = AdaptationPlanner()
    plan = planner.plan(ir, target_profile, manifest)
    
    assert plan is not None
    assert len(plan.mappings) > 0
    print(f"✅ Step 3: Generated Adaptation Plan with {len(plan.mappings)} mappings.")

    # --- 5. FINAL VERIFICATION ---
    print("\n--- Verifying Output Integrity ---")
    
    # Verify: No hard-coded 'app/' folders
    for m in plan.mappings:
        assert "app/" not in m.target_file_path, f"Found hardcoded 'app/' in {m.target_file_path}"
        assert "src/" in m.target_file_path, f"Expected 'src/' in {m.target_file_path}"

    # Verify: Correct naming patterns applied
    has_store = any("Store" in m.target_symbol_name for m in plan.mappings)
    has_manager = any("Manager" in m.target_symbol_name for m in plan.mappings)
    assert has_store, "Target naming pattern 'Store' not applied"
    assert has_manager, "Target naming pattern 'Manager' not applied"

    # Verify: Correct REUSE logic
    entity_mappings = [m for m in plan.mappings if m.target_layer == TargetLayer.ENTITY]
    assert any(m.action == ComponentAction.REUSE for m in entity_mappings), "Failed to reuse existing User entity"
    
    print("\n🎉 SYSTEM INTEGRATION SUCCESSFUL: Slicing -> IR -> Planning (Dynamic)")

if __name__ == "__main__":
    test_end_to_end_real_repo_pipeline()
