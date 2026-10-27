"""
test_adaptation_planner.py - Verification suite for AdaptationPlanner & LangGraph node.
Verifies Phase 7B Module 2:
1. Deterministic REUSE / EXTEND / CREATE decisions against Clean Architecture conventions.
2. Algorithmic dependency inference (passlib, python-jose, etc.).
3. LangGraph node plan_adaptation_node execution with TranspositionState.
4. Real-world end-to-end alignment using sliced Conduit (RealWorld FastAPI) feature.
"""
from app.schemas.slice import (
    CodeSymbol,
    EntryPoint,
    FunctionCall,
    SymbolKind,
    VerticalSlice,
)
from app.schemas.transposition import (
    AlgorithmStep,
    ComponentAction,
    ComponentAssessment,
    DataContract,
    DataContractField,
    EvidenceReference,
    FrameworkAgnosticIR,
    PureAlgorithm,
    TargetComponentRole,
    TargetEvidenceManifest,
    TargetLayer,
    TargetRepositoryProfile,
    TranspositionState,
)
from app.transposition.planner import AdaptationPlanner, plan_adaptation_node


def _create_synthetic_target_profile() -> TargetRepositoryProfile:
    """Creates a sample target profile resembling ai_redemption Clean Architecture."""
    return TargetRepositoryProfile(
        target_root="/workspace/target_app",
        architectural_style="Clean Architecture",
        framework="fastapi",
        orm="sqlalchemy_2.0",
        dto_pattern="pydantic_v2",
        primary_key_pattern="uuid7",
        test_framework="pytest",
        existing_domain_models=["User", "Conversation", "Message"],
        reusable_interfaces=["UserRepository", "ConversationRepository"],
        reusable_services=["UserService", "ConversationService"],
        components=[
            ComponentAssessment(
                component_id="app/entities/user.py:User",
                role=TargetComponentRole.DOMAIN_MODEL,
                confidence=1.0,
                evidence=[EvidenceReference(file_path="app/entities/user.py", observation="Inherits Base")],
                rationale="Target User entity",
            ),
            ComponentAssessment(
                component_id="app/repositories/user_repo.py:PostgresUserRepository",
                role=TargetComponentRole.DATA_ACCESS,
                confidence=1.0,
                evidence=[EvidenceReference(file_path="app/repositories/user_repo.py", observation="DB queries")],
                rationale="Target User repository",
            ),
            ComponentAssessment(
                component_id="app/services/user_service.py:UserService",
                role=TargetComponentRole.BUSINESS_LOGIC,
                confidence=1.0,
                evidence=[EvidenceReference(file_path="app/services/user_service.py", observation="Business logic")],
                rationale="Target User service",
            ),
        ],
    )


def _create_synthetic_auth_ir() -> FrameworkAgnosticIR:
    """Creates a sample FrameworkAgnosticIR for User Login."""
    return FrameworkAgnosticIR(
        feature_name="User Authentication",
        summary="User login with email, password verification, and JWT issuance.",
        contracts=[
            DataContract(
                name="UserInDB",
                fields=[
                    DataContractField(name="id", field_type="uuid.UUID"),
                    DataContractField(name="email", field_type="str"),
                    DataContractField(name="hashed_password", field_type="str"),
                ],
                description="Database representation of User",
            ),
            DataContract(
                name="UserLoginRequest",
                fields=[
                    DataContractField(name="email", field_type="str"),
                    DataContractField(name="password", field_type="str"),
                ],
                description="Client login request payload",
            ),
            DataContract(
                name="TokenResponse",
                fields=[
                    DataContractField(name="access_token", field_type="str"),
                    DataContractField(name="token_type", field_type="str"),
                ],
                description="JWT token response",
            ),
        ],
        algorithms=[
            PureAlgorithm(
                name="authenticate_user",
                inputs=["email: str", "password: str"],
                output="TokenResponse",
                steps=[
                    AlgorithmStep(step_number=1, action="query", description="Fetch user from repository by email"),
                    AlgorithmStep(step_number=2, action="verify", description="Verify password hash using bcrypt"),
                    AlgorithmStep(step_number=3, action="sign", description="Encode and issue JWT bearer token"),
                ],
                exceptions_raised=["AuthenticationError"],
            )
        ],
        source_provenance_files=["app/api/auth.py", "app/db/users.py"],
        source_symbol_ids=["app/api/auth.py:login", "app/db/users.py:verify_password"],
    )


def test_planner_synthetic_user_auth() -> None:
    """Verifies deterministic mapping decisions for User Authentication."""
    planner = AdaptationPlanner()
    target_profile = _create_synthetic_target_profile()
    manifest = TargetEvidenceManifest(
        target_root="/workspace/target_app",
        total_files_scanned=10,
        files_indexed_count=10,
        parse_error_count=0,
        declared_dependencies=["fastapi", "sqlalchemy", "pydantic"],
    )
    ir = _create_synthetic_auth_ir()

    plan = planner.plan(ir, target_profile, manifest)

    assert plan.feature_name == "User Authentication"
    assert len(plan.mappings) >= 4

    # 1. Assert REUSE decision for existing User entity
    entity_mappings = [m for m in plan.mappings if m.target_layer == TargetLayer.ENTITY]
    assert len(entity_mappings) == 1
    assert entity_mappings[0].action == ComponentAction.REUSE
    assert entity_mappings[0].target_file_path == "app/entities/user.py"
    assert entity_mappings[0].target_symbol_name == "User"

    # 2. Assert CREATE decisions for DTO schemas
    schema_mappings = [m for m in plan.mappings if m.target_layer == TargetLayer.SCHEMA]
    assert len(schema_mappings) == 2
    for s_map in schema_mappings:
        assert s_map.action == ComponentAction.CREATE
        assert s_map.target_file_path == "app/schemas/user_authentication.py"
    schema_symbols = {s.target_symbol_name for s in schema_mappings}
    assert "UserLoginRequest" in schema_symbols
    assert "TokenResponse" in schema_symbols

    # 3. Assert EXTEND decision for UserRepository
    repo_mappings = [m for m in plan.mappings if m.target_layer == TargetLayer.REPOSITORY_IMPL]
    assert len(repo_mappings) == 1
    assert repo_mappings[0].action == ComponentAction.EXTEND
    assert repo_mappings[0].target_file_path == "app/repositories/user_repo.py"

    # 4. Assert CREATE decision for AuthService
    service_mappings = [m for m in plan.mappings if m.target_layer == TargetLayer.SERVICE]
    assert len(service_mappings) == 1
    assert service_mappings[0].action == ComponentAction.CREATE
    assert service_mappings[0].target_file_path == "app/services/user_authentication_service.py"

    # 5. Assert dependency diffing: passlib and python-jose detected
    assert "passlib[bcrypt]" in plan.new_dependencies
    assert "python-jose[cryptography]" in plan.new_dependencies

    print("✅ test_planner_synthetic_user_auth passed")


def test_planner_langgraph_node_execution() -> None:
    """Verifies plan_adaptation_node executes seamlessly inside LangGraph TranspositionState."""
    target_profile = _create_synthetic_target_profile()
    ir = _create_synthetic_auth_ir()

    dummy_slice = VerticalSlice(
        feature_name="User Authentication",
        entry_points=[
            EntryPoint(
                symbol=CodeSymbol(
                    name="login",
                    qualified_name="login",
                    kind=SymbolKind.ROUTE,
                    file_path="app/api/auth.py",
                    line_start=1,
                    line_end=10,
                    source_code="def login(): pass",
                ),
                entry_type="http_route",
            )
        ],
        symbols=[],
        call_graph=[],
    )

    state: TranspositionState = {
        "source_slice": dummy_slice,
        "target_repo_path": "/workspace/target_app",
        "target_profile": target_profile,
        "target_manifest": None,
        "ir": ir,
        "conventions": None,
        "plan": None,
        "scaffolded_files": [],
        "audit_passed": False,
        "audit_feedback": None,
        "retry_count": 0,
    }

    result = plan_adaptation_node(state)

    assert "plan" in result
    plan = result["plan"]
    assert plan is not None
    assert plan.feature_name == "User Authentication"
    assert len(plan.mappings) >= 4

    print("✅ test_planner_langgraph_node_execution passed")


def test_planner_realworld_fastapi_e2e() -> None:
    """Verifies end-to-end planning using a real Conduit slice and real target profile."""
    from pathlib import Path
    from app.services.deconstructor_service import FeatureDeconstructorService
    from app.transposition.ir_extractor import IRExtractor

    conduit_path = Path("test_fixtures/realworld_fastapi")
    if not conduit_path.exists():
        print("⚠️ Conduit fixture not found, skipping e2e")
        return

    deconstructor = FeatureDeconstructorService()
    vslice, _ = deconstructor.deconstruct_feature(
        repo_path=conduit_path,
        feature_name="User Authentication",
        query="/login",
    )

    ir_extractor = IRExtractor()
    ir = ir_extractor.extract_ir(vslice)

    planner = AdaptationPlanner()
    target_profile = _create_synthetic_target_profile()
    manifest = TargetEvidenceManifest(
        target_root="/workspace/target_app",
        total_files_scanned=10,
        files_indexed_count=10,
        parse_error_count=0,
        declared_dependencies=["fastapi", "sqlalchemy", "pydantic"],
    )

    plan = planner.plan(ir, target_profile, manifest)

    assert plan.feature_name == "User Authentication"
    assert len(plan.mappings) > 0

    # Verify that User entity from Conduit was matched with target User entity
    entity_maps = [m for m in plan.mappings if m.target_layer == TargetLayer.ENTITY]
    assert len(entity_maps) >= 1
    assert any(m.action == ComponentAction.REUSE and m.target_symbol_name == "User" for m in entity_maps)

    # Verify that target services and schemas were scheduled for creation
    assert any(m.action == ComponentAction.CREATE and m.target_layer == TargetLayer.SERVICE for m in plan.mappings)
    assert any(m.action == ComponentAction.CREATE and m.target_layer == TargetLayer.SCHEMA for m in plan.mappings)

    print("✅ test_planner_realworld_fastapi_e2e passed")


def test_planner_capability_map_intelligence() -> None:
    """Verifies that existing target capabilities prevent redundant dependencies."""
    planner = AdaptationPlanner()
    target_profile = _create_synthetic_target_profile()
    ir = _create_synthetic_auth_ir()

    # Case A: Target codebase ALREADY has bcrypt installed in pyproject.toml
    manifest_with_bcrypt = TargetEvidenceManifest(
        target_root="/workspace/target_app",
        total_files_scanned=10,
        files_indexed_count=10,
        parse_error_count=0,
        declared_dependencies=["fastapi", "bcrypt", "pydantic"],
    )
    plan_a = planner.plan(ir, target_profile, manifest_with_bcrypt)

    # Since bcrypt is already installed, passlib[bcrypt] should NOT be added as new dependency!
    assert "passlib[bcrypt]" not in plan_a.new_dependencies
    # But python-jose IS added because target has no token library
    assert "python-jose[cryptography]" in plan_a.new_dependencies

    # Case B: Target codebase ALSO has pyjwt installed
    manifest_with_both = TargetEvidenceManifest(
        target_root="/workspace/target_app",
        total_files_scanned=10,
        files_indexed_count=10,
        parse_error_count=0,
        declared_dependencies=["fastapi", "bcrypt", "pyjwt", "pydantic"],
    )
    plan_b = planner.plan(ir, target_profile, manifest_with_both)

    # Both capabilities are satisfied by existing packages!
    assert len(plan_b.new_dependencies) == 0

    print("✅ test_planner_capability_map_intelligence passed")


if __name__ == "__main__":
    print("\n🚀 RUNNING MASTER ADAPTATION PLANNER VERIFICATION SUITE\n" + "=" * 60)
    test_planner_synthetic_user_auth()
    test_planner_langgraph_node_execution()
    test_planner_realworld_fastapi_e2e()
    test_planner_capability_map_intelligence()
    print("=" * 60)
    print("🎉 ALL ADAPTATION PLANNER TESTS PASSED 100% GREEN!\n")
