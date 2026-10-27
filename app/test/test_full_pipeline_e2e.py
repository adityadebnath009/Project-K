import pytest
from pathlib import Path
from app.schemas.transposition import (
    TargetRepositoryProfile,
    TargetConventionMap,
    TargetLayer,
    TargetEvidenceManifest
)
from app.services.deconstructor_service import FeatureDeconstructorService
from app.transposition.ir_extractor import IRExtractor
from app.transposition.planner import AdaptationPlanner

def test_end_to_end_feature_transposition_pipeline():
    """
    INTEGRATION TEST: Connects the entire project logic from Source Slicing 
    to Architectural Transposition.
    
    Pipeline:
    Source Repo -> Vertical Slice -> Framework Agnostic IR -> Adaptation Plan
    """
    print("\n🚀 Starting Full Pipeline E2E Integration Test...")

    # --- PHASE 1: Feature Slicing (Source) ---
    # We use the RealWorld FastAPI fixture as our source repo
    source_repo_path = "test_fixtures/realworld_fastapi"
    deconstructor = FeatureDeconstructorService()
    
    print("Step 1: Deconstructing feature from source repo...")
    vslice, blueprint_md = deconstructor.deconstruct_feature(
        repo_path=source_repo_path,
        feature_name="User Authentication",
        query="/login",
    )
    assert vslice is not None
    assert len(vslice.symbols) > 0
    print(f"✅ Successfully sliced feature: {vslice.feature_name} ({len(vslice.symbols)} symbols)")

    # --- PHASE 2: Invariant Distillation (IR Extraction) ---
    print("Step 2: Extracting Framework-Agnostic IR...")
    ir_extractor = IRExtractor()
    ir = ir_extractor.extract_ir(vslice)
    assert ir is not None
    assert len(ir.contracts) > 0
    assert len(ir.algorithms) > 0
    print(f"✅ Extracted IR with {len(ir.contracts)} contracts and {len(ir.algorithms)} algorithms")

    # --- PHASE 3: Target Architecture Alignment ---
    # We simulate a Target Project with specific, non-standard conventions
    print("Step 3: Mapping to Target Architecture...")
    custom_conventions = TargetConventionMap(
        layer_directories={
            TargetLayer.ENTITY: "src/domain/models",
            TargetLayer.REPOSITORY_IMPL: "src/infra/repos",
            TargetLayer.SERVICE: "src/app/services",
            TargetLayer.SCHEMA: "src/app/dtos",
            TargetLayer.TEST: "tests/unit",
        },
        repo_naming_pattern="{symbol}Store",
        service_naming_pattern="{symbol}Manager",
    )
    
    target_profile = TargetRepositoryProfile(
        target_root="/workspace/target_project",
        architectural_style="Clean Architecture",
        conventions=custom_conventions,
        existing_domain_models=["User"], # Target already has a User entity
    )
    
    manifest = TargetEvidenceManifest(
        target_root="/workspace/target_project",
        total_files_scanned=50,
        files_indexed_count=50,
        parse_error_count=0,
        declared_dependencies=["fastapi", "sqlalchemy"],
    )

    planner = AdaptationPlanner()
    plan = planner.plan(ir, target_profile, manifest)
    
    assert plan is not None
    assert len(plan.mappings) > 0
    print(f"✅ Generated Adaptation Plan with {len(plan.mappings)} component mappings")

    # --- PHASE 4: Final Verification of the Pipeline Output ---
    print("\n--- Final Pipeline Verification ---")
    
    # Verify: Did it respect the Target's custom directories?
    for m in plan.mappings:
        expected_dir = custom_conventions.layer_directories.get(m.target_layer)
        if expected_dir:
            assert m.target_file_path.startswith(expected_dir), \
                f"Mapping for {m.source_id} failed path check. Expected {expected_dir}, got {m.target_file_path}"

    # Verify: Did it use the custom 'Store' and 'Manager' naming?
    has_store = any("Store" in m.target_symbol_name for m in plan.mappings)
    has_manager = any("Manager" in m.target_symbol_name for m in plan.mappings)
    assert has_store, "Pipeline failed to apply Target naming pattern: Store"
    assert has_manager, "Pipeline failed to apply Target naming pattern: Manager"

    # Verify: Did it correctly REUSE the existing User model?
    entity_mappings = [m for m in plan.mappings if m.target_layer == TargetLayer.ENTITY]
    assert any(m.action == "reuse" or m.action == ComponentAction.REUSE for m in entity_mappings), \
        "Pipeline failed to reuse existing target User entity"

    print("\n🎉 FULL PIPELINE E2E TEST PASSED: Source Slicing -> IR -> Adaptation Plan")

if __name__ == "__main__":
    test_end_to_end_feature_transposition_pipeline()
