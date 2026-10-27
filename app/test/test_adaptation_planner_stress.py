"""
test_adaptation_planner_stress.py - High-intensity stress tests for AdaptationPlanner.
Targets edge cases in deterministic matching, layer validation, and dependency inference.
"""
import pytest
from app.schemas.transposition import (
    AdaptationPlan,
    ComponentAction,
    ComponentMapping,
    DataContract,
    DataContractField,
    FrameworkAgnosticIR,
    PureAlgorithm,
    AlgorithmStep,
    TargetLayer,
    TargetRepositoryProfile,
    ComponentAssessment,
    TargetComponentRole,
    EvidenceReference,
    TargetEvidenceManifest,
)
from app.transposition.planner import AdaptationPlanner

def _create_base_profile(existing_models=None, components=None) -> TargetRepositoryProfile:
    if existing_models is None:
        existing_models = []
    if components is None:
        components = []

    return TargetRepositoryProfile(
        target_root="/workspace/target_app",
        architectural_style="Clean Architecture",
        framework="fastapi",
        orm="sqlalchemy_2.0",
        dto_pattern="pydantic_v2",
        primary_key_pattern="uuid7",
        test_framework="pytest",
        existing_domain_models=existing_models,
        reusable_interfaces=[],
        reusable_services=[],
        components=components,
    )

def test_planner_collision_handling():
    """Test how planner handles ambiguity when multiple target models match a source contract."""
    # Target has both 'User' and 'UserAccount'
    profile = _create_base_profile(
        existing_models=["User", "UserAccount"],
        components=[
            ComponentAssessment(
                component_id="app/entities/user.py:User",
                role=TargetComponentRole.DOMAIN_MODEL,
                confidence=1.0,
                evidence=[],
                rationale="User model",
            ),
            ComponentAssessment(
                component_id="app/entities/account.py:UserAccount",
                role=TargetComponentRole.DOMAIN_MODEL,
                confidence=1.0,
                evidence=[],
                rationale="Account model",
            ),
        ]
    )

    # Source contract is 'User'
    ir = FrameworkAgnosticIR(
        feature_name="Collision Test",
        summary="Testing collision",
        contracts=[DataContract(name="User", fields=[], description="Test")],
        algorithms=[],
        source_provenance_files=[],
        source_symbol_ids=[],
    )

    planner = AdaptationPlanner()
    plan = planner.plan(ir, profile)

    # It should pick one and not crash
    entity_mappings = [m for m in plan.mappings if m.target_layer == TargetLayer.ENTITY]
    assert len(entity_mappings) == 1
    assert entity_mappings[0].action == ComponentAction.REUSE

def test_planner_layer_violation_correction():
    """Verify that the validator forcibly corrects paths that violate Clean Architecture."""
    profile = _create_base_profile()
    ir = FrameworkAgnosticIR(
        feature_name="Violation Test",
        summary="Testing violations",
        contracts=[DataContract(name="TestContract", fields=[], description="Test")],
        algorithms=[],
        source_provenance_files=[],
        source_symbol_ids=[],
    )

    planner = AdaptationPlanner()

    # Manually inject a bad plan into the validation logic
    # We simulate a bad LLM output where a SERVICE is placed in the ENTITIES folder
    bad_mapping = ComponentMapping(
        source_id="TestAlgo",
        target_layer=TargetLayer.SERVICE,
        action=ComponentAction.CREATE,
        target_file_path="app/entities/wrong_place.py",
        target_symbol_name="TestService",
        description="Bad placement",
    )

    plan = AdaptationPlan(
        feature_name="Violation Test",
        target_root="/workspace/target_app",
        mappings=[bad_mapping],
        new_dependencies=[],
        schema_diff_summary="",
    )

    planner._validate_plan(plan, profile)

    # Path should be corrected to app/services/wrong_place.py
    assert plan.mappings[0].target_file_path == "app/services/wrong_place.py"

def test_planner_dependency_inference_full_spectrum():
    """Stress test the library inference for all supported keywords (Redis, Celery, Tenacity, etc)."""
    ir = FrameworkAgnosticIR(
        feature_name="Dep Stress",
        summary="Testing deps",
        contracts=[],
        algorithms=[
            PureAlgorithm(
                name="ComplexAlgo",
                inputs=[],
                output="",
                steps=[
                    AlgorithmStep(step_number=1, action="action", description="Use redis to cache"),
                    AlgorithmStep(step_number=2, action="action", description="Schedule via celery queue"),
                    AlgorithmStep(step_number=3, action="action", description="Retry with exponential backoff tenacity"),
                    AlgorithmStep(step_number=4, action="action", description="Verify password with bcrypt"),
                ],
                exceptions_raised=[],
            )
        ],
        source_provenance_files=[],
        source_symbol_ids=[],
    )

    planner = AdaptationPlanner()
    profile = _create_base_profile()
    manifest = TargetEvidenceManifest(
        target_root="/root",
        total_files_scanned=0,
        files_indexed_count=0,
        parse_error_count=0,
        declared_dependencies=[], # Empty target deps to force all inferences
    )

    plan = planner.plan(ir, profile, manifest)

    expected = {"redis", "passlib[bcrypt]", "tenacity"} # 'celery' is matched via 'redis' or 'queue' in current impl
    # Note: current implementation matches 'redis', 'rq', 'celery' all to 'redis'
    assert "redis" in plan.new_dependencies
    assert "passlib[bcrypt]" in plan.new_dependencies
    assert "tenacity" in plan.new_dependencies

def test_planner_zero_match_scenario():
    """Verify the system creates everything from scratch when target is empty."""
    profile = _create_base_profile(existing_models=[], components=[])
    ir = FrameworkAgnosticIR(
        feature_name="Greenfield Feature",
        summary="Nothing exists",
        contracts=[DataContract(name="NewContract", fields=[], description="Test")],
        algorithms=[PureAlgorithm(name="NewAlgo", inputs=[], output="", steps=[], exceptions_raised=[])],
        source_provenance_files=[],
        source_symbol_ids=[],
    )

    planner = AdaptationPlanner()
    plan = planner.plan(ir, profile)

    # Everything should be CREATE
    for m in plan.mappings:
        assert m.action == ComponentAction.CREATE

def test_planner_complex_ir_intertwined():
    """Test mapping for a feature with multiple intertwined contracts and algorithms."""
    ir = FrameworkAgnosticIR(
        feature_name="Complex Feature",
        summary="Multi-component",
        contracts=[
            DataContract(name="ReqA", fields=[], description="A"),
            DataContract(name="ReqB", fields=[], description="B"),
            DataContract(name="ResC", fields=[], description="C"),
        ],
        algorithms=[
            PureAlgorithm(name="Algo1", inputs=[], output="ResC", steps=[], exceptions_raised=[]),
            PureAlgorithm(name="Algo2", inputs=[], output="ResC", steps=[], exceptions_raised=[]),
        ],
        source_provenance_files=[],
        source_symbol_ids=[],
    )

    planner = AdaptationPlanner()
    profile = _create_base_profile()
    plan = planner.plan(ir, profile)

    # Should have 3 schema mappings and 2 service mappings
    schemas = [m for m in plan.mappings if m.target_layer == TargetLayer.SCHEMA]
    services = [m for m in plan.mappings if m.target_layer == TargetLayer.SERVICE]

    assert len(schemas) == 3
    assert len(services) == 2
