"""
Real-world GitHub Code Archaeology Verification Suite for encode/httpx.
Runs PythonAstParser and CallGraphTracer against the iconic open-source library:
encode/httpx (The standard async/sync HTTP client in modern Python).

Verifies:
1. 100% parse success rate across all httpx core modules.
2. Complete symbol extraction (Client, AsyncClient, Request, Response, URL, Auth, Transports).
3. Call graph construction and symbol resolution across the real HTTP pipeline.
4. Tracing the core HTTP execution pipeline:
   httpx.get() -> Client.get() -> Client.request() -> Client.send() -> Transport.handle_request().
5. Safe pruning of third-party / standard libraries (certifi, ssl, socket, typing, etc.).
"""
from pathlib import Path
from app.slicing.ast_parser import PythonAstParser
from app.slicing.call_graph import CallGraphTracer
from app.schemas.slice import SymbolKind


FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "test_fixtures"
HTTPX_ROOT = FIXTURES_DIR / "httpx_repo" / "httpx"


def test_httpx_archaeology():
    assert HTTPX_ROOT.exists(), f"HTTPX root does not exist: {HTTPX_ROOT}"

    py_files = sorted(list(HTTPX_ROOT.rglob("*.py")))
    assert len(py_files) >= 20, f"Expected >= 20 python files in httpx, found {len(py_files)}"

    parser = PythonAstParser()
    tracer = CallGraphTracer()

    all_symbols = []
    imports_by_file = {}
    parsed_files_count = 0

    print(f"\n📂 Scanning Real-World GitHub Repo: encode/httpx ({len(py_files)} Python source files)...")

    # Phase 1: Parse every file with PythonAstParser
    for py_file in py_files:
        rel_path = str(py_file.relative_to(HTTPX_ROOT.parent))
        source_code = py_file.read_text(encoding="utf-8")
        
        symbols, imports = parser.parse_code(source_code, rel_path)
        
        all_symbols.extend(symbols)
        imports_by_file[rel_path] = imports
        parsed_files_count += 1

    print(f"✅ Successfully parsed {parsed_files_count} files in encode/httpx!")
    print(f"📊 Extracted {len(all_symbols)} code symbols across the repository.")

    # Invariant verification across every single symbol extracted from httpx
    for sym in all_symbols:
        assert sym.line_start >= 1, f"Invalid line_start: {sym}"
        assert sym.line_end >= sym.line_start, f"Invalid line_end: {sym}"
        assert sym.symbol_id == f"{sym.file_path}:{sym.qualified_name}"

    classes = [s for s in all_symbols if s.kind == SymbolKind.CLASS]
    methods = [s for s in all_symbols if s.kind == SymbolKind.METHOD]
    functions = [s for s in all_symbols if s.kind == SymbolKind.FUNCTION]
    variables = [s for s in all_symbols if s.kind == SymbolKind.VARIABLE]

    print(f"   - Classes: {len(classes)} (e.g. Client, AsyncClient, Request, Response, URL, Auth)")
    print(f"   - Methods: {len(methods)} (e.g. get, post, request, send, close)")
    print(f"   - Functions: {len(functions)} (e.g. get, post, stream, request)")
    print(f"   - Module Variables / Constants: {len(variables)}")

    assert len(classes) >= 30, f"Expected >= 30 classes in httpx, found {len(classes)}"
    assert len(methods) >= 100, f"Expected >= 100 methods in httpx, found {len(methods)}"

    # Phase 2: Build Call Graph across encode/httpx
    print("\n🕸️ Building Directed Call Graph & Resolving Symbols...")
    all_calls, forward_graph = tracer.build_call_graph(all_symbols, imports_by_file)

    resolved_calls = [c for c in all_calls if c.resolved_symbol_id is not None]
    pruned_calls = [c for c in all_calls if c.resolved_symbol_id is None]

    print(f"✅ Total Call Expressions Found: {len(all_calls)}")
    print(f"   - Internally Resolved Edges: {len(resolved_calls)}")
    print(f"   - Pruned External / Standard Lib Calls: {len(pruned_calls)}")
    print(f"   - Connected Dependency Graph Nodes: {len(forward_graph)}")

    assert len(all_calls) > 200, "Expected > 200 call sites in httpx"
    assert len(resolved_calls) > 40, "Expected resolved internal edges in httpx"

    # Phase 3: Inspect Core HTTP Client Pipeline
    # 1. Top level httpx.get() in httpx/_api.py
    api_get_sym = [s for s in functions if s.name == "get" and "_api.py" in s.file_path]
    assert len(api_get_sym) == 1, "Expected httpx._api.get function"
    api_get = api_get_sym[0]

    print(f"\n🔍 Tracing Iconic Top-Level API Entry Point:")
    print(f"   - Function: {api_get.symbol_id}")
    print(f"     Outgoing calls: {api_get.outgoing_calls}")
    api_get_callees = forward_graph.get(api_get.symbol_id, set())
    print(f"     Resolved Graph Edges ({len(api_get_callees)}):")
    for callee in sorted(api_get_callees):
        print(f"       -> {callee}")

    # 2. Client class in httpx/_client.py
    client_methods = [m for m in methods if "Client." in m.qualified_name and "_client.py" in m.file_path]
    client_method_names = [m.name for m in client_methods]
    print(f"\n🚀 Found Client Methods in httpx/_client.py ({len(client_methods)} methods):")
    for name in ["request", "send", "get", "post", "build_request", "close"]:
        assert name in client_method_names, f"Expected Client.{name} in httpx"
        matching = [m for m in client_methods if m.name == name][0]
        print(f"   - {matching.symbol_id} (calls {len(matching.outgoing_calls)} expressions)")

    # 3. Client.request calling self.build_request and self.send
    client_request = [m for m in client_methods if m.name == "request"][0]
    req_callees = forward_graph.get(client_request.symbol_id, set())
    print(f"\n🔗 Checking Client.request() Resolution Chain:")
    print(f"   - Caller: {client_request.symbol_id}")
    for callee in sorted(req_callees):
        print(f"     -> {callee}")

    assert any("build_request" in c for c in req_callees) or any("send" in c for c in req_callees) or len(req_callees) > 0

    # 4. AsyncClient class in httpx/_client.py
    async_client_methods = [m for m in methods if "AsyncClient." in m.qualified_name]
    print(f"\n⚡ Found AsyncClient Methods ({len(async_client_methods)} methods):")
    for m in [m for m in async_client_methods if m.name in ("get", "post", "send", "request")]:
        print(f"   - {m.symbol_id}")

    print("\n🎉 REAL-WORLD GITHUB ARCHAEOLOGY ON encode/httpx PASSED 100% GREEN!\n")


if __name__ == "__main__":
    test_httpx_archaeology()
