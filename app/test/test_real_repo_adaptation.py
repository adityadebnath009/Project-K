import pytest
from pathlib import Path
from app.schemas.transposition import (
    FrameworkAgnosticIR,
    DataContract,
    DataContractField,
    PureAlgorithm,
    AlgorithmStep,
    TargetLayer,
    TargetRepositoryProfile,
    TargetConventionMap,
    TargetEvidenceManifest,
    ComponentAction,
    ComponentAssessment,
    TargetComponentRole,
)
from app.transposition.planner import AdaptationPlanner
from app.services.deconstructor_service import FeatureDeconstructorService
from app.transposition.ir_extractor import IRExtractor

def test_real_world_repo_adaptation_dynamic():
    """
    Tests the planner against a real open-source repo (RealWorld FastAPI / Conduit).
    We will simulate a target project that has DIFFERENT conventions than the source
    to verify that the planner adapts to the TARGET, not the SOURCE.
    """
    # 1. Extract IR from the real open source repo (Source)
    conduit_path = Path("test_fixtures/realworld_fastapi")
    deconstructor = FeatureDeconstructorService()
    vslice, _ = deconstructor.deconstruct_feature(
        repo_path=str(conduit_path),
        feature_name="User Authentication",
        query="/login",
    )
    ir_extractor = IRExtractor()
    ir = ir_extractor.extract_ir(vslice)
    
    # 2. Define a Target Profile with NON-STANDARD conventions
    # We'll pretend the target project puts everything in 'src/' instead of 'app/'
    custom_conventions = TargetConventionMap(
        layer_directories={
            TargetLayer.ENTITY: "src/domain/entities",
            TargetLayer.REPOSITORY_IMPL: "src/infrastructure/repositories",
            TargetLayer.SERVICE: "src/application/services",
            TargetLayer.SCHEMA: "src/application/dtos",
            TargetLayer.TEST: "tests/unit",
        },
        repo_naming_pattern="{symbol}Store", # Different from 'Repository'
        service_naming_pattern="{symbol}Manager", # Different from 'Service'
    )
    
    target_profile = TargetRepositoryProfile(
        target_root="/workspace/my_custom_app",
        architectural_style="Clean Architecture",
        conventions=custom_conventions,
        existing_domain_models=["User"], # Target already has a User model
        components=[
            # Existing User entity in the custom location
            # This is used to test the REUSE logic
        ]
    )
    # Add the existing User entity to the components list to ensure match
    target_profile.components.append(
        ComponentAssessment(
            component_id="src/domain/entities/user.py:User",
            role=TargetComponentRole.DOMAIN_MODEL,
            confidence=1.0,
            evidence=[],
            rationale="Existing User entity",
        )
    )
    # Manually adding to components for the test since we aren't running the full indexer
    # Actually, the planner uses existing_domain_models for the initial check
    
    manifest = TargetEvidenceManifest(
        target_root="/workspace/my_custom_app",
        total_files_scanned=10,
        files_indexed_count=10,
        parse_error_count=0,
        declared_dependencies=["fastapi", "sqlalchemy"],
    )

    # 3. Plan the Adaptation
    planner = AdaptationPlanner()
    plan = planner.plan(ir, target_profile, manifest)

    print("\n--- Adaptation Plan for Real Repo ---")
    for m in plan.mappings:
        print(f"Layer: {m.target_layer} | Action: {m.action} | Path: {m.target_file_path} | Symbol: {m.target_symbol_name}")

    # ASSERTIONS
    
    # Check that the planner used the CUSTOM target paths, not the source paths or defaults
    for m in plan.mappings:
        assert "app/" not in m.target_file_path, f"Plan used hardcoded 'app/' path: {m.target_file_path}"
        assert "src/" in m.target_file_path, f"Plan failed to use custom root 'src/': {m.target_file_path}"

    # Check that the User entity was REUSED and placed in the custom directory
    entity_mappings = [m for m in plan.mappings if m.target_layer == TargetLayer.ENTITY]
    assert any(m.action == ComponentAction.REUSE for m in entity_mappings)
    assert any("src/domain/entities" in m.target_file_path for m in entity_mappings)

    # Check that the Repository used the custom 'Store' naming pattern
    repo_mappings = [m for m in plan.mappings if m.target_layer == TargetLayer.REPOSITORY_IMPL]
    assert any("Store" in m.target_symbol_name for m in repo_mappings)
    assert not any("Repository" in m.target_symbol_name for m in repo_mappings)

    # Check that the Service used the custom 'Manager' naming pattern
    service_mappings = [m for m in plan.mappings if m.target_layer == TargetLayer.SERVICE]
    assert any("Manager" in m.target_symbol_name for m in service_mappings)
    assert not any("Service" in m.target_symbol_name for m in service_mappings)

    print("\n✅ Real-world adaptation successfully adapted to CUSTOM target conventions!")

if __name__ == "__main__":
    test_real_world_repo_adaptation_dynamic()
