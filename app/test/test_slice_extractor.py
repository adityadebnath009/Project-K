"""
test_slice_extractor.py - Comprehensive verification suite for SliceExtractor.
Verifies:
1. FeatureSlicer protocol conformance.
2. Missing entry point validation.
3. Isolated single-node entry point slicing.
4. Linear transitive reachability (Route -> Service -> Repo -> Model).
5. Unrelated code pruning (guarantees dead code is not included).
6. Diamond topology deduplication.
7. Circular calls and mutual recursion safety.
8. Parent class definition preservation for reachable methods.
9. Call edge filtering to slice boundaries.
10. Automatic non-overlapping LOC and files_involved derivation.
11. Live Real-World Slice Extraction: FastAPI RealWorld (/api/users/login).
12. Live Real-World Slice Extraction: encode/httpx (httpx.get client pipeline).
"""
from pathlib import Path
from app.schemas.slice import CodeSymbol, EntryPoint, FunctionCall, SymbolKind, VerticalSlice
from app.slicing.interfaces import FeatureSlicer
from app.slicing.extractor import SliceExtractor
from app.slicing.ast_parser import PythonAstParser
from app.slicing.call_graph import CallGraphTracer


def _make_symbol(
    file_path: str,
    name: str,
    qualified_name: str | None = None,
    kind: SymbolKind = SymbolKind.FUNCTION,
    outgoing_calls: list[str] | None = None,
    line_start: int = 1,
    line_end: int = 10,
) -> CodeSymbol:
    q_name = qualified_name or name
    return CodeSymbol(
        symbol_id=f"{file_path}:{q_name}",
        name=name,
        qualified_name=q_name,
        kind=kind,
        file_path=file_path,
        line_start=line_start,
        line_end=line_end,
        source_code=f"def {name}(): pass",
        outgoing_calls=outgoing_calls or [],
    )


def test_01_protocol_conformance():
    extractor = SliceExtractor()
    assert isinstance(extractor, FeatureSlicer)


def test_02_missing_entry_point_raises_error():
    extractor = SliceExtractor()
    sym = _make_symbol("a.py", "foo")
    raised = False
    try:
        extractor.extract_slice("Feature", "non_existent:entry", [sym], {})
    except ValueError as e:
        raised = True
        assert "not found" in str(e)
    assert raised


def test_03_single_leaf_route_slice():
    route = _make_symbol("routes/ping.py", "ping", kind=SymbolKind.ROUTE)
    unrelated = _make_symbol("services/billing.py", "charge")
    extractor = SliceExtractor()
    v_slice = extractor.extract_slice("Healthcheck", route.symbol_id, [route, unrelated], {})
    assert len(v_slice.symbols) == 1
    assert v_slice.symbols[0].symbol_id == route.symbol_id
    assert v_slice.files_involved == ["routes/ping.py"]


def test_04_linear_transitive_reachability_and_pruning():
    route = _make_symbol("routes/order.py", "submit", kind=SymbolKind.ROUTE)
    svc = _make_symbol("services/order.py", "process_order")
    repo = _make_symbol("repos/order.py", "save_order")
    model = _make_symbol("models/order.py", "OrderModel", kind=SymbolKind.CLASS)

    # Unrelated symbols that must be pruned
    unrelated_route = _make_symbol("routes/billing.py", "checkout", kind=SymbolKind.ROUTE)
    unrelated_svc = _make_symbol("services/stripe.py", "charge_card")

    graph = {
        route.symbol_id: {svc.symbol_id},
        svc.symbol_id: {repo.symbol_id},
        repo.symbol_id: {model.symbol_id},
        unrelated_route.symbol_id: {unrelated_svc.symbol_id},
    }
    all_syms = [route, svc, repo, model, unrelated_route, unrelated_svc]

    extractor = SliceExtractor()
    v_slice = extractor.extract_slice("Order Submission", route.symbol_id, all_syms, graph)

    slice_ids = {s.symbol_id for s in v_slice.symbols}
    assert route.symbol_id in slice_ids
    assert svc.symbol_id in slice_ids
    assert repo.symbol_id in slice_ids
    assert model.symbol_id in slice_ids

    # Verify unrelated symbols are completely excluded
    assert unrelated_route.symbol_id not in slice_ids
    assert unrelated_svc.symbol_id not in slice_ids
    assert len(v_slice.symbols) == 4
    assert len(v_slice.files_involved) == 4


def test_05_diamond_topology_deduplication():
    root = _make_symbol("root.py", "start", kind=SymbolKind.ROUTE)
    left = _make_symbol("left.py", "branch_left")
    right = _make_symbol("right.py", "branch_right")
    shared = _make_symbol("shared.py", "shared_db")

    graph = {
        root.symbol_id: {left.symbol_id, right.symbol_id},
        left.symbol_id: {shared.symbol_id},
        right.symbol_id: {shared.symbol_id},
    }
    extractor = SliceExtractor()
    v_slice = extractor.extract_slice("Diamond Feature", root.symbol_id, [root, left, right, shared], graph)

    # shared should only appear ONCE in symbols
    assert len(v_slice.symbols) == 4
    ids = [s.symbol_id for s in v_slice.symbols]
    assert ids.count(shared.symbol_id) == 1


def test_06_cycles_and_mutual_recursion_safety():
    root = _make_symbol("root.py", "entry", kind=SymbolKind.ROUTE)
    node_a = _make_symbol("service.py", "step_a")
    node_b = _make_symbol("service.py", "step_b")

    # Cycle: root -> node_a <-> node_b
    graph = {
        root.symbol_id: {node_a.symbol_id},
        node_a.symbol_id: {node_b.symbol_id},
        node_b.symbol_id: {node_a.symbol_id},
    }
    extractor = SliceExtractor()
    v_slice = extractor.extract_slice("Cyclic Flow", root.symbol_id, [root, node_a, node_b], graph)
    assert len(v_slice.symbols) == 3


def test_07_parent_class_definition_preservation():
    route = _make_symbol("routes/user.py", "get_user", kind=SymbolKind.ROUTE)
    user_repo_cls = _make_symbol("repos/user.py", "UserRepository", kind=SymbolKind.CLASS)
    user_repo_method = _make_symbol("repos/user.py", "find_by_id", "UserRepository.find_by_id", SymbolKind.METHOD)

    graph = {
        route.symbol_id: {user_repo_method.symbol_id}
    }
    extractor = SliceExtractor()
    v_slice = extractor.extract_slice("User Fetch", route.symbol_id, [route, user_repo_cls, user_repo_method], graph)

    slice_ids = {s.symbol_id for s in v_slice.symbols}
    # Even though route only called the method, the parent UserRepository class must be included!
    assert user_repo_method.symbol_id in slice_ids
    assert user_repo_cls.symbol_id in slice_ids
    assert len(v_slice.symbols) == 3


def test_08_call_edges_filtered_to_slice():
    root = _make_symbol("root.py", "entry", kind=SymbolKind.ROUTE)
    callee = _make_symbol("sub.py", "worker")
    unrelated_caller = _make_symbol("other.py", "other_fn")

    graph = {root.symbol_id: {callee.symbol_id}}

    edge_in_slice = FunctionCall(caller_symbol_id=root.symbol_id, raw_callee="worker", resolved_symbol_id=callee.symbol_id, file_path="root.py", line_number=5)
    edge_outside_slice = FunctionCall(caller_symbol_id=unrelated_caller.symbol_id, raw_callee="something", resolved_symbol_id=None, file_path="other.py", line_number=10)

    extractor = SliceExtractor()
    v_slice = extractor.extract_slice("Slice", root.symbol_id, [root, callee, unrelated_caller], graph, [edge_in_slice, edge_outside_slice])

    assert len(v_slice.call_graph) == 1
    assert v_slice.call_graph[0].caller_symbol_id == root.symbol_id


def test_09_automatic_loc_and_files_involved_derivation():
    sym1 = _make_symbol("app/a.py", "fn1", line_start=1, line_end=10)
    sym2 = _make_symbol("app/a.py", "fn2", line_start=5, line_end=15)  # overlaps 5..10
    sym3 = _make_symbol("app/b.py", "fn3", line_start=1, line_end=5)

    graph = {
        sym1.symbol_id: {sym2.symbol_id, sym3.symbol_id}
    }
    extractor = SliceExtractor()
    v_slice = extractor.extract_slice("Derivation Test", sym1.symbol_id, [sym1, sym2, sym3], graph)

    # app/a.py covers lines 1..15 (15 lines). app/b.py covers 1..5 (5 lines). Total = 20 unique lines!
    assert v_slice.total_lines_of_code == 20
    assert v_slice.files_involved == ["app/a.py", "app/b.py"]


def test_10_realworld_github_fastapi_slice_extraction():
    """Extracts a real vertical slice for the User Login feature from fastapi-realworld-example-app."""
    repo_root = Path("/Users/adityadebnath/.gemini/antigravity/brain/b2140001-6cae-49a0-945e-79b0cd5b3541/scratch/realworld_fastapi/app")
    assert repo_root.exists()

    py_files = sorted(list(repo_root.rglob("*.py")))
    parser = PythonAstParser()
    tracer = CallGraphTracer()
    extractor = SliceExtractor()

    all_symbols = []
    imports_by_file = {}
    for f in py_files:
        rel_path = str(f.relative_to(repo_root.parent))
        symbols, imports = parser.parse_code(f.read_text(encoding="utf-8"), rel_path)
        all_symbols.extend(symbols)
        imports_by_file[rel_path] = imports

    all_calls, forward_graph = tracer.build_call_graph(all_symbols, imports_by_file)

    login_route_id = "app/api/routes/authentication.py:login"
    login_slice = extractor.extract_slice(
        feature_name="User Authentication (Conduit Login)",
        entry_point_id=login_route_id,
        symbols=all_symbols,
        forward_graph=forward_graph,
        call_edges=all_calls,
    )

    print(f"\n🎯 RealWorld Sliced Feature: {login_slice.feature_name}")
    print(f"   - Total Symbols in Slice: {len(login_slice.symbols)}")
    print(f"   - Unique Covered Source Lines: {login_slice.total_lines_of_code}")
    print(f"   - Files Involved: {login_slice.files_involved}")

    slice_symbol_ids = {s.symbol_id for s in login_slice.symbols}
    assert login_route_id in slice_symbol_ids
    # UsersRepository should be included
    assert any("UsersRepository" in s_id for s_id in slice_symbol_ids)
    # Articles and Comments routes should be EXCLUDED
    assert not any("articles.py" in s_id for s_id in slice_symbol_ids)
    assert not any("comments.py" in s_id for s_id in slice_symbol_ids)


def test_11_realworld_github_httpx_slice_extraction():
    """Extracts a real vertical slice for the httpx.get() execution pipeline from encode/httpx."""
    httpx_root = Path("/Users/adityadebnath/.gemini/antigravity/brain/b2140001-6cae-49a0-945e-79b0cd5b3541/scratch/httpx_repo/httpx")
    assert httpx_root.exists()

    py_files = sorted(list(httpx_root.rglob("*.py")))
    parser = PythonAstParser()
    tracer = CallGraphTracer()
    extractor = SliceExtractor()

    all_symbols = []
    imports_by_file = {}
    for f in py_files:
        rel_path = str(f.relative_to(httpx_root.parent))
        symbols, imports = parser.parse_code(f.read_text(encoding="utf-8"), rel_path)
        all_symbols.extend(symbols)
        imports_by_file[rel_path] = imports

    all_calls, forward_graph = tracer.build_call_graph(all_symbols, imports_by_file)

    get_api_id = "httpx/_api.py:get"
    httpx_slice = extractor.extract_slice(
        feature_name="HTTPX GET Request Pipeline",
        entry_point_id=get_api_id,
        symbols=all_symbols,
        forward_graph=forward_graph,
        call_edges=all_calls,
    )

    print(f"\n🎯 HTTPX Sliced Feature: {httpx_slice.feature_name}")
    print(f"   - Total Symbols in Slice: {len(httpx_slice.symbols)}")
    print(f"   - Unique Covered Source Lines: {httpx_slice.total_lines_of_code}")
    print(f"   - Files Involved: {httpx_slice.files_involved}")

    slice_symbol_ids = {s.symbol_id for s in httpx_slice.symbols}
    assert get_api_id in slice_symbol_ids
    assert "httpx/_api.py:request" in slice_symbol_ids
    assert len(httpx_slice.symbols) >= 2


if __name__ == "__main__":
    print("Running SliceExtractor Verification Suite...")
    test_01_protocol_conformance()
    test_02_missing_entry_point_raises_error()
    test_03_single_leaf_route_slice()
    test_04_linear_transitive_reachability_and_pruning()
    test_05_diamond_topology_deduplication()
    test_06_cycles_and_mutual_recursion_safety()
    test_07_parent_class_definition_preservation()
    test_08_call_edges_filtered_to_slice()
    test_09_automatic_loc_and_files_involved_derivation()
    test_10_realworld_github_fastapi_slice_extraction()
    test_11_realworld_github_httpx_slice_extraction()
    print("🎉 ALL SliceExtractor test cases passed successfully!")
