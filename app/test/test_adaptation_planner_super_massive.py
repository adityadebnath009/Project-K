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
    TargetConventionMap,
    TargetEvidenceManifest,
)
from app.transposition.planner import AdaptationPlanner

def random_string(length=10):
    return ''.join(random.choices(string.ascii_letters, k=length))

def test_super_massive_adaptation_permutations():
    """
    Runs 200 randomized permutations with varying ConventionMaps
    to ensure the planner adapts to DIFFERENT project structures,
    not just the default one.
    """
    planner = AdaptationPlanner()
    
    for i in range(200):
        # RANDOMIZE CONVENTIONS (Crucial for testing the fix)
        # This simulates projects that DON'T use 'app/'
        root_folders = ["src", "app", "internal", "lib", "core"]
        chosen_root = random.choice(root_folders)
        
        custom_conventions = TargetConventionMap(
            layer_directories={
                TargetLayer.ENTITY: f"{chosen_root}/models",
                TargetLayer.REPOSITORY_IMPL: f"{chosen_root}/repositories",
                TargetLayer.SERVICE: f"{chosen_root}/logic",
                TargetLayer.SCHEMA: f"{chosen_root}/dtos",
                TargetLayer.TEST: f"{chosen_root}/tests",
            },
            repo_naming_pattern=random.choice([
                "Db{symbol}Repo", 
                "{symbol}Store", 
                "Postgres{symbol}Repository", 
                "Sql{symbol}Repository"
            ]),
            service_naming_pattern=random.choice([
                "{symbol}Service", 
                "{symbol}Manager", 
                "{symbol}Handler"
            ])
        )

        # Randomize Target Profile
        num_models = random.randint(0, 30)
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
            conventions=custom_conventions,
            components=[
                ComponentAssessment(
                    component_id=f"{custom_conventions.layer_directories[TargetLayer.ENTITY]}/{m.lower()}.py:{m}",
                    role=TargetComponentRole.DOMAIN_MODEL,
                    confidence=1.0,
                    evidence=[],
                    rationale="Random model"
                ) for m in existing_models
            ]
        )

        # Randomize IR
        num_contracts = random.randint(1, 15)
        contracts = [
            DataContract(
                name=f"Contract_{random_string()}", 
                fields=[DataContractField(name="f1", field_type="str")], 
                description="Random contract"
            ) for _ in range(num_contracts)
        ]
        
        num_algos = random.randint(1, 10)
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
        
        # Check that every mapping follows the RANDOMIZED conventions, not the defaults
        for m in plan.mappings:
            expected_dir = custom_conventions.layer_directories.get(m.target_layer)
            if expected_dir:
                assert m.target_file_path.startswith(expected_dir), f"Path {m.target_file_path} should start with {expected_dir}"
            
        # Check that the repo naming pattern was applied correctly if a repo was created
        for m in plan.mappings:
            if m.target_layer == TargetLayer.REPOSITORY_IMPL:
                pattern = custom_conventions.repo_naming_pattern
                # Check if the resulting symbol name matches the pattern logic
                # (Essentially checking if it's not just hardcoded 'Postgres...Repository')
                if "Postgres" not in pattern and "Postgres" in m.target_symbol_name:
                    pytest.fail(f"Hardcoded Postgres prefix found despite pattern {pattern}")

    print(f"\n✅ Successfully processed 200 randomized permutations with DYNAMIC conventions.")

if __name__ == "__main__":
    test_super_massive_adaptation_permutations()
