"""
test_deconstructor_service.py - Comprehensive verification suite for EntryPointLocator,
BlueprintGenerator, and FeatureDeconstructorService.
Follows the zero-external-dependency runner pattern of the codebase.
"""
from pathlib import Path
import tempfile
from app.schemas.slice import CodeSymbol, FunctionCall, SymbolKind, VerticalSlice
from app.services.deconstructor_service import FeatureDeconstructorService
from app.slicing.blueprint import BlueprintGenerator
from app.slicing.locator import EntryPointLocator

SCRATCH_DIR = Path("/Users/adityadebnath/.gemini/antigravity/brain/b2140001-6cae-49a0-945e-79b0cd5b3541/scratch")
FASTAPI_REALWORLD_DIR = SCRATCH_DIR / "realworld_fastapi"
HTTPX_DIR = SCRATCH_DIR / "httpx_repo"


def test_locator_extracts_route_metadata():
    locator = EntryPointLocator()
    route_symbol = CodeSymbol(
        name="login",
        qualified_name="login",
        kind=SymbolKind.ROUTE,
        file_path="app/api/auth.py",
        line_start=10,
        line_end=20,
        source_code='@router.post("/users/login", response_model=UserResponse)\nasync def login():\n    pass',
    )
    func_symbol = CodeSymbol(
        name="calculate_tax",
        qualified_name="calculate_tax",
        kind=SymbolKind.FUNCTION,
        file_path="app/services/tax.py",
        line_start=1,
        line_end=5,
        source_code="def calculate_tax(amount):\n    return amount * 0.1",
    )
    private_symbol = CodeSymbol(
        name="_internal_helper",
        qualified_name="_internal_helper",
        kind=SymbolKind.FUNCTION,
        file_path="app/services/tax.py",
        line_start=7,
        line_end=9,
        source_code="def _internal_helper():\n    pass",
    )

    eps = locator.find_entry_points([route_symbol, func_symbol, private_symbol])
    # Private functions must be omitted
    assert len(eps) == 2, f"Expected 2 entry points, got {len(eps)}"

    route_ep = eps[0]
    assert route_ep.entry_type == "http_route"
    assert route_ep.route_path == "/users/login"
    assert route_ep.http_method == "POST"

    func_ep = eps[1]
    assert func_ep.entry_type == "public_api"
    assert func_ep.route_path is None
    print("✅ test_locator_extracts_route_metadata passed")


def test_locator_ranking_relevance():
    locator = EntryPointLocator()
    sym_exact = CodeSymbol(
        name="checkout",
        qualified_name="checkout",
        kind=SymbolKind.ROUTE,
        file_path="app/api/cart.py",
        line_start=1,
        line_end=10,
        source_code='@app.post("/checkout")\ndef checkout(): pass',
    )
    sym_substring = CodeSymbol(
        name="pre_checkout_validate",
        qualified_name="pre_checkout_validate",
        kind=SymbolKind.FUNCTION,
        file_path="app/services/cart.py",
        line_start=1,
        line_end=5,
        source_code="def pre_checkout_validate(): pass",
    )
    sym_unrelated = CodeSymbol(
        name="send_email",
        qualified_name="send_email",
        kind=SymbolKind.FUNCTION,
        file_path="app/services/email.py",
        line_start=1,
        line_end=5,
        source_code="def send_email(): pass",
    )

    results = locator.find_entry_points([sym_unrelated, sym_substring, sym_exact], query="checkout")
    assert len(results) == 2, f"Expected 2 results, got {len(results)}"
    assert results[0].symbol.name == "checkout", f"Expected 'checkout', got '{results[0].symbol.name}'"
    assert results[1].symbol.name == "pre_checkout_validate"
    print("✅ test_locator_ranking_relevance passed")


def test_blueprint_generator_mermaid():
    generator = BlueprintGenerator()
    sym1 = CodeSymbol(
        name="login_route",
        qualified_name="login_route",
        kind=SymbolKind.ROUTE,
        file_path="api/auth.py",
        line_start=1,
        line_end=10,
        source_code='@router.post("/login")\ndef login_route(): pass',
    )
    sym2 = CodeSymbol(
        name="authenticate",
        qualified_name="AuthService.authenticate",
        kind=SymbolKind.METHOD,
        file_path="services/auth.py",
        line_start=20,
        line_end=35,
        source_code="def authenticate(self): pass",
    )
    call_edge = FunctionCall(
        caller_symbol_id="api/auth.py:login_route",
        raw_callee="auth_service.authenticate",
        resolved_symbol_id="services/auth.py:AuthService.authenticate",
        file_path="api/auth.py",
        line_number=5,
    )
    vslice = VerticalSlice(
        feature_name="User Login",
        symbols=[sym1, sym2],
        call_graph=[call_edge],
    )

    mermaid = generator.generate_mermaid(vslice)
    assert "flowchart TD" in mermaid
    assert 'api_auth_py_login_route(["🌐 Route: login_route"])' in mermaid
    assert "api_auth_py_login_route --> services_auth_py_AuthService_authenticate" in mermaid
    print("✅ test_blueprint_generator_mermaid passed")


def test_blueprint_generator_markdown():
    generator = BlueprintGenerator()
    sym = CodeSymbol(
        name="login",
        qualified_name="login",
        kind=SymbolKind.ROUTE,
        file_path="api/auth.py",
        line_start=1,
        line_end=5,
        docstring="Authenticates the user and returns a JWT token.",
        source_code='@router.post("/login")\ndef login():\n    return "ok"',
    )
    vslice = VerticalSlice(
        feature_name="Authentication",
        symbols=[sym],
        files_involved=["api/auth.py"],
    )

    md = generator.generate_markdown(vslice)
    assert "# Feature Specification Blueprint: Authentication" in md
    assert "## 1. Executive Summary" in md
    assert "Covered Source Lines" in md
    assert "## 3. Architecture & Dependency Flow" in md
    assert "```mermaid" in md
    assert "Authenticates the user and returns a JWT token." in md
    assert "### File: `api/auth.py`" in md
    assert 'return "ok"' in md
    print("✅ test_blueprint_generator_markdown passed")


def test_deconstructor_invalid_repo_path():
    service = FeatureDeconstructorService()
    try:
        service.scan_repository("/non/existent/directory/xyz123")
        assert False, "Expected FileNotFoundError"
    except FileNotFoundError:
        pass
    print("✅ test_deconstructor_invalid_repo_path passed")


def test_deconstructor_empty_repo():
    service = FeatureDeconstructorService()
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            service.deconstruct_feature(tmpdir, "Test Feature")
            assert False, "Expected ValueError"
        except ValueError as e:
            assert "No Python symbols could be parsed" in str(e)
    print("✅ test_deconstructor_empty_repo passed")


def test_deconstructor_synthetic_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        api_file = tmp_path / "api.py"
        api_file.write_text(
            'from service import OrderService\n\n'
            '@router.post("/orders")\n'
            'def create_order(payload):\n'
            '    svc = OrderService()\n'
            '    return svc.process(payload)\n'
        )
        svc_file = tmp_path / "service.py"
        svc_file.write_text(
            'class OrderService:\n'
            '    def process(self, payload):\n'
            '        return {"status": "created"}\n'
        )

        service = FeatureDeconstructorService()
        vslice, blueprint_md = service.deconstruct_feature(
            repo_path=tmp_path,
            feature_name="Create Order",
            query="orders",
        )

        assert vslice.feature_name == "Create Order"
        assert len(vslice.symbols) >= 2
        assert len(vslice.entry_points) == 1
        assert vslice.entry_points[0].route_path == "/orders"
        assert vslice.entry_points[0].http_method == "POST"

        assert "Create Order" in blueprint_md
        assert "```mermaid" in blueprint_md
        assert "flowchart TD" in blueprint_md
    print("✅ test_deconstructor_synthetic_repo passed")


def test_e2e_deconstruct_fastapi_realworld_login():
    if not FASTAPI_REALWORLD_DIR.exists():
        print("⚠️ Skipping FastAPI RealWorld e2e test (scratch dir not found)")
        return

    service = FeatureDeconstructorService()

    # 1. Test entry point listing
    entry_points = service.list_entry_points(FASTAPI_REALWORLD_DIR, query="login")
    assert len(entry_points) > 0
    top_ep = entry_points[0]
    assert "login" in top_ep.symbol.name.lower()
    assert top_ep.route_path == "/login"
    assert top_ep.http_method == "POST"

    # 2. End-to-End Deconstruction
    vslice, blueprint = service.deconstruct_feature(
        repo_path=FASTAPI_REALWORLD_DIR,
        feature_name="User Login Flow",
        query="/login",
    )

    assert vslice.feature_name == "User Login Flow"
    assert len(vslice.symbols) >= 5, f"Expected >= 5 symbols, got {len(vslice.symbols)}"
    assert len(vslice.files_involved) >= 2
    assert vslice.total_lines_of_code > 50

    symbol_names = [s.name for s in vslice.symbols]
    assert "login" in symbol_names
    assert "get_user_by_email" in symbol_names or "UsersRepository" in symbol_names

    assert "User Login Flow" in blueprint
    assert "```mermaid" in blueprint
    assert "flowchart TD" in blueprint
    print(f"✅ test_e2e_deconstruct_fastapi_realworld_login passed ({len(vslice.symbols)} symbols, {vslice.total_lines_of_code} LOC)")


def test_e2e_deconstruct_httpx_get_pipeline():
    if not HTTPX_DIR.exists():
        print("⚠️ Skipping HTTPX e2e test (scratch dir not found)")
        return

    service = FeatureDeconstructorService()

    vslice, blueprint = service.deconstruct_feature(
        repo_path=HTTPX_DIR,
        feature_name="HTTPX GET Request Pipeline",
        query="get",
    )

    assert vslice.feature_name == "HTTPX GET Request Pipeline"
    assert len(vslice.symbols) > 0
    assert len(vslice.files_involved) > 0
    assert vslice.total_lines_of_code > 0

    assert "HTTPX GET Request Pipeline" in blueprint
    assert "```mermaid" in blueprint
    print(f"✅ test_e2e_deconstruct_httpx_get_pipeline passed ({len(vslice.symbols)} symbols, {vslice.total_lines_of_code} LOC)")


if __name__ == "__main__":
    print("=" * 70)
    print("🚀 RUNNING MASTER DECONSTRUCTOR SERVICE VERIFICATION SUITE")
    print("=" * 70)
    test_locator_extracts_route_metadata()
    test_locator_ranking_relevance()
    test_blueprint_generator_mermaid()
    test_blueprint_generator_markdown()
    test_deconstructor_invalid_repo_path()
    test_deconstructor_empty_repo()
    test_deconstructor_synthetic_repo()
    test_e2e_deconstruct_fastapi_realworld_login()
    test_e2e_deconstruct_httpx_get_pipeline()
    print("=" * 70)
    print("🎉 ALL DECONSTRUCTOR SERVICE & ARCHAEOLOGY TESTS PASSED 100% GREEN!")
    print("=" * 70)
