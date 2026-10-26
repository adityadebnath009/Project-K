"""
app/test/test_ir_extractor.py
Verification suite for IRExtractor against synthetic and real-world slices.
"""

from pathlib import Path

from app.schemas.slice import CodeSymbol, FunctionCall, SymbolKind, VerticalSlice
from app.services.deconstructor_service import FeatureDeconstructorService
from app.transposition.ir_extractor import IRExtractor

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "test_fixtures"
FASTAPI_REALWORLD_DIR = FIXTURES_DIR / "realworld_fastapi"
HTTPX_DIR = FIXTURES_DIR / "httpx_repo"


def test_ir_extractor_synthetic_slice():
    """Verify IR extraction on an in-memory synthetic slice."""
    sym_model = CodeSymbol(
        name="UserLoginRequest",
        qualified_name="UserLoginRequest",
        kind=SymbolKind.CLASS,
        file_path="app/schemas/auth.py",
        line_start=1,
        line_end=5,
        source_code="class UserLoginRequest:\n    email: str\n    password: str\n",
    )
    sym_route = CodeSymbol(
        name="login",
        qualified_name="login",
        kind=SymbolKind.FUNCTION,
        file_path="app/routes/auth.py",
        line_start=10,
        line_end=15,
        source_code="def login(req: UserLoginRequest):\n    return authenticate(req.email, req.password)\n",
    )
    call = FunctionCall(
        caller_symbol_id=sym_route.symbol_id,
        raw_callee="authenticate",
        resolved_symbol_id="app/services/auth.py:authenticate",
        file_path=sym_route.file_path,
        line_number=11,
    )
    vslice = VerticalSlice(
        feature_name="Simple Login",
        symbols=[sym_model, sym_route],
        call_graph=[call],
    )

    extractor = IRExtractor()
    ir = extractor.extract_ir(vslice)

    assert ir.feature_name == "Simple Login"
    assert len(ir.contracts) >= 1
    contract = next(c for c in ir.contracts if c.name == "UserLoginRequest")
    field_names = [f.name for f in contract.fields]
    assert "email" in field_names
    assert "password" in field_names

    assert len(ir.algorithms) >= 1
    algo = ir.algorithms[0]
    assert len(algo.steps) >= 1
    assert "authenticate" in algo.steps[0].description
    assert ir.source_provenance_files == ["app/routes/auth.py", "app/schemas/auth.py"]


def test_ir_extractor_realworld_fastapi():
    """Verify IR extraction against the real Conduit FastAPI repository."""
    if not FASTAPI_REALWORLD_DIR.exists():
        print("⚠️ FastAPI RealWorld test fixture not found, skipping")
        return

    deconstructor = FeatureDeconstructorService()
    vslice, _ = deconstructor.deconstruct_feature(
        repo_path=FASTAPI_REALWORLD_DIR,
        feature_name="User Login Flow",
        query="/login",
    )

    extractor = IRExtractor()
    ir = extractor.extract_ir(vslice)

    assert ir.feature_name == "User Login Flow"
    assert len(ir.contracts) >= 3

    contract_names = [c.name for c in ir.contracts]
    assert "UserInResponse" in contract_names
    assert "UserWithToken" in contract_names
    assert "UserInDB" in contract_names

    # Check field extraction fidelity
    token_contract = next(c for c in ir.contracts if c.name == "UserWithToken")
    assert any(f.name == "token" and f.field_type == "str" for f in token_contract.fields)

    # Check algorithms
    assert len(ir.algorithms) >= 1
    algo = ir.algorithms[0]
    assert len(algo.steps) >= 10
    step_descriptions = " ".join(s.description for s in algo.steps)
    assert "get_user_by_email" in step_descriptions
    assert "check_password" in step_descriptions

    # Check provenance
    assert "app/api/routes/authentication.py" in ir.source_provenance_files
    assert any("UsersRepository" in sym for sym in ir.source_symbol_ids)


def test_ir_extractor_realworld_httpx():
    """Verify IR extraction against the real HTTPX repository."""
    if not HTTPX_DIR.exists():
        print("⚠️ HTTPX test fixture not found, skipping")
        return

    deconstructor = FeatureDeconstructorService()
    vslice, _ = deconstructor.deconstruct_feature(
        repo_path=HTTPX_DIR,
        feature_name="HTTP GET Request",
        query="get",
    )

    extractor = IRExtractor()
    ir = extractor.extract_ir(vslice)

    assert ir.feature_name == "HTTP GET Request"
    assert len(ir.contracts) > 5
    assert len(ir.algorithms) >= 1
    assert len(ir.algorithms[0].steps) > 50
    assert "httpx/_api.py" in ir.source_provenance_files
    print("✅ test_ir_extractor_realworld_httpx passed")


if __name__ == "__main__":
    test_ir_extractor_synthetic_slice()
    print("✅ test_ir_extractor_synthetic_slice passed")
    test_ir_extractor_realworld_fastapi()
    print("✅ test_ir_extractor_realworld_fastapi passed")
    test_ir_extractor_realworld_httpx()
    print("\n🎉 ALL IR EXTRACTOR TESTS PASSED 100% GREEN!")
