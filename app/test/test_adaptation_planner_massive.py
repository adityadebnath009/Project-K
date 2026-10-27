import pytest
import random
import string
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

def random_string(length=10):
    return ''.join(random.choices(string.ascii_letters, k=length))

def test_massive_adaptation_permutations():
    """
    Runs 100 randomized permutations of IRs and Target Profiles to ensure 
    the planner is robust against arbitrary inputs.
    """
    planner = AdaptationPlanner()
    
    for i in range(100):
        # Randomize Target Profile
        num_models = random.randint(0, 20)
        existing_models = [f"Model_{random_string()}" for _ in range(num_models)]
        
        profile = TargetRepositoryProfile(
            target_root="/workspace/target",
            architectural_style="Clean Architecture",
            framework="fastapi",
            orm="sqlalchemy_2.0",
            dto_pattern="pydantic_v2",
            primary_key_pattern="uuid7",
            test_framework="pytest",
            existing_domain_models=existing_models,
            components=[
                ComponentAssessment(
                    component_id=f"app/entities/{m.lower()}.py:{m}",
                    role=TargetComponentRole.DOMAIN_MODEL,
                    confidence=1.0,
                    evidence=[],
                    rationale="Random model"
                ) for m in existing_models
            ]
        )

        # Randomize IR
        num_contracts = random.randint(1, 10)
        contracts = [
            DataContract(
                name=f"Contract_{random_string()}", 
                fields=[DataContractField(name="f1", field_type="str")], 
                description="Random contract"
            ) for _ in range(num_contracts)
        ]
        
        num_algos = random.randint(1, 5)
        algos = [
            PureAlgorithm(
                name=f"Algo_{random_string()}", 
                inputs=[], 
                output="Res", 
                steps=[AlgorithmStep(step_number=1, action="do", description=random_string(50))],
                exceptions_raised=[]
            ) for _ in range(num_algos)
        ]

        ir = FrameworkAgnosticIR(
            feature_name=f"Feature_{i}",
            summary="Stress test",
            contracts=contracts,
            algorithms=algos,
            source_provenance_files=[],
            source_symbol_ids=[]
        )

        manifest = TargetEvidenceManifest(
            target_root="/root",
            total_files_scanned=100,
            files_indexed_count=100,
            parse_error_count=0,
            declared_dependencies=[]
        )

        # EXECUTE
        plan = planner.plan(ir, profile, manifest)

        # ASSERTIONS
        assert plan.feature_name == f"Feature_{i}"
        assert len(plan.mappings) > 0
        
        # Check that every mapping is in a valid layer
        for m in plan.mappings:
            assert m.target_layer in TargetLayer
            assert m.target_file_path.startswith("app/")
            
        # Check that we didn't crash on an empty target
        if not existing_models:
            for m in plan.mappings:
                if m.target_layer == TargetLayer.ENTITY:
                    assert m.action == ComponentAction.CREATE

    print(f"\n✅ Successfully processed 100 randomized adaptation permutations.")

if __name__ == "__main__":
    test_massive_adaptation_permutations()
