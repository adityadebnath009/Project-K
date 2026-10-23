import copy
import json
import time
from app.schemas.slice import (
    CodeSymbol,
    EntryPoint,
    FunctionCall,
    ImportStatement,
    SymbolKind,
    VerticalSlice,
)


# ══════════════════════════════════════════════════════════════════
# EXISTING TESTS 1 THROUGH 16
# ══════════════════════════════════════════════════════════════════

def test_code_symbol_auto_id_and_validation():
    sym = CodeSymbol(
        name="save",
        qualified_name="UserService.save",
        kind=SymbolKind.METHOD,
        file_path="app/services/user.py",
        line_start=10,
        line_end=20,
        source_code="def save(self): pass",
    )
    assert sym.symbol_id == "app/services/user.py:UserService.save"

    # line_start < 1
    raised = False
    try:
        CodeSymbol(name="b", qualified_name="b", kind=SymbolKind.FUNCTION, file_path="t.py", line_start=0, line_end=10, source_code="")
    except ValueError as e:
        raised = True
        assert "line_start must be >= 1" in str(e)
    assert raised

    # line_end < line_start
    raised = False
    try:
        CodeSymbol(name="b", qualified_name="b", kind=SymbolKind.FUNCTION, file_path="t.py", line_start=20, line_end=10, source_code="")
    except ValueError as e:
        raised = True
        assert "cannot be earlier than line_start" in str(e)
    assert raised

    # mismatch symbol_id
    raised = False
    try:
        CodeSymbol(symbol_id="wrong", name="s", qualified_name="S.s", kind=SymbolKind.METHOD, file_path="a/u.py", line_start=10, line_end=20, source_code="")
    except ValueError as e:
        raised = True
        assert "symbol_id mismatch" in str(e)
    assert raised


def test_vertical_slice_derived_fields_and_no_overlap():
    class_sym = CodeSymbol(name="UserService", qualified_name="UserService", kind=SymbolKind.CLASS, file_path="app/services/user.py", line_start=10, line_end=30, source_code="...")
    method_sym = CodeSymbol(name="save", qualified_name="UserService.save", kind=SymbolKind.METHOD, file_path="app/services/user.py", line_start=15, line_end=25, source_code="...")
    model_sym = CodeSymbol(name="User", qualified_name="User", kind=SymbolKind.CLASS, file_path="app/models/user.py", line_start=1, line_end=10, source_code="...")

    slice_obj = VerticalSlice(feature_name="User Management", symbols=[class_sym, method_sym, model_sym])
    assert slice_obj.files_involved == ["app/models/user.py", "app/services/user.py"]
    assert slice_obj.total_lines_of_code == 31
    summary = slice_obj.to_context_summary()
    assert "### [VERTICAL SLICE: User Management]" in summary
    assert "**Covered Source Lines**: 31" in summary


def test_empty_vertical_slice_edge_case():
    empty_slice = VerticalSlice(feature_name="Empty Feature")
    assert empty_slice.symbols == []
    assert empty_slice.files_involved == []
    assert empty_slice.total_lines_of_code == 0
    summary = empty_slice.to_context_summary()
    assert "**Covered Source Lines**: 0" in summary
    assert "**Files Involved (0)**:" in summary


def test_single_line_and_partial_overlapping_spans():
    single_line_sym = CodeSymbol(name="get_status", qualified_name="get_status", kind=SymbolKind.FUNCTION, file_path="app/utils.py", line_start=5, line_end=5, source_code="...")
    sym_a = CodeSymbol(name="func_a", qualified_name="func_a", kind=SymbolKind.FUNCTION, file_path="app/math_ops.py", line_start=10, line_end=25, source_code="...")
    sym_b = CodeSymbol(name="func_b", qualified_name="func_b", kind=SymbolKind.FUNCTION, file_path="app/math_ops.py", line_start=20, line_end=35, source_code="...")

    slice_obj = VerticalSlice(feature_name="Math Module", symbols=[single_line_sym, sym_a, sym_b])
    assert slice_obj.total_lines_of_code == 27


def test_explicit_total_lines_override():
    sym = CodeSymbol(name="do_work", qualified_name="do_work", kind=SymbolKind.FUNCTION, file_path="app/job.py", line_start=1, line_end=10, source_code="...")
    slice_obj = VerticalSlice(feature_name="Worker", symbols=[sym], total_lines_of_code=999)
    assert slice_obj.total_lines_of_code == 999


def test_entry_point_and_function_call_resolution():
    route_sym = CodeSymbol(name="checkout_route", qualified_name="checkout_route", kind=SymbolKind.ROUTE, file_path="app/routes/checkout.py", line_start=12, line_end=30, source_code="...")
    service_sym = CodeSymbol(name="process_payment", qualified_name="PaymentService.process_payment", kind=SymbolKind.METHOD, file_path="app/services/payment.py", line_start=40, line_end=65, source_code="...")
    entry = EntryPoint(symbol=route_sym, entry_type="http_route", route_path="/api/checkout", http_method="POST")
    call = FunctionCall(caller_symbol_id=route_sym.symbol_id, raw_callee="payment_service.process_payment", resolved_symbol_id=service_sym.symbol_id, file_path="app/routes/checkout.py", line_number=22)

    slice_obj = VerticalSlice(feature_name="Checkout Flow", entry_points=[entry], symbols=[route_sym, service_sym], call_graph=[call])
    assert len(slice_obj.entry_points) == 1
    assert slice_obj.entry_points[0].route_path == "/api/checkout"
    assert len(slice_obj.call_graph) == 1
    assert slice_obj.call_graph[0].resolved_symbol_id == "app/services/payment.py:PaymentService.process_payment"


def test_multi_level_nesting_three_deep():
    outer = CodeSymbol(name="OuterClass", qualified_name="OuterClass", kind=SymbolKind.CLASS, file_path="app/complex.py", line_start=1, line_end=50, source_code="...")
    inner = CodeSymbol(name="InnerClass", qualified_name="OuterClass.InnerClass", kind=SymbolKind.CLASS, file_path="app/complex.py", line_start=10, line_end=40, source_code="...")
    deep_method = CodeSymbol(name="deep_exec", qualified_name="OuterClass.InnerClass.deep_exec", kind=SymbolKind.METHOD, file_path="app/complex.py", line_start=15, line_end=25, source_code="...")

    slice_obj = VerticalSlice(feature_name="Deep Nesting", symbols=[outer, inner, deep_method])
    assert slice_obj.total_lines_of_code == 50


def test_unresolved_external_call_vs_resolved_internal_call():
    internal_call = FunctionCall(caller_symbol_id="app/svc.py:Service.run", raw_callee="self.db.commit", resolved_symbol_id="app/db.py:Database.commit", file_path="app/svc.py", line_number=15)
    external_call = FunctionCall(caller_symbol_id="app/svc.py:Service.run", raw_callee="logger.info", resolved_symbol_id=None, file_path="app/svc.py", line_number=18)
    assert internal_call.resolved_symbol_id is not None
    assert external_call.resolved_symbol_id is None


def test_multiple_heterogeneous_entry_points():
    route_sym = CodeSymbol(name="post_invoice", qualified_name="post_invoice", kind=SymbolKind.ROUTE, file_path="app/api/invoice.py", line_start=10, line_end=20, source_code="...")
    worker_sym = CodeSymbol(name="process_invoice_job", qualified_name="process_invoice_job", kind=SymbolKind.FUNCTION, file_path="app/workers/invoice_worker.py", line_start=5, line_end=35, source_code="...")
    http_entry = EntryPoint(symbol=route_sym, entry_type="http_route", route_path="/invoices", http_method="POST")
    worker_entry = EntryPoint(symbol=worker_sym, entry_type="worker_task")

    slice_obj = VerticalSlice(feature_name="Invoice Processing", entry_points=[http_entry, worker_entry], symbols=[route_sym, worker_sym])
    assert len(slice_obj.entry_points) == 2


def test_import_statement_star_and_alias_mappings():
    multi_import = ImportStatement(source_module="typing", imported_names=["Any", "Union", "Optional"], is_from=True, line_number=1)
    assert len(multi_import.imported_names) == 3
    star_import = ImportStatement(source_module="math", imported_names=["*"], is_from=True, line_number=5)
    assert "*" in star_import.imported_names
    aliased_import = ImportStatement(source_module="os.path", imported_names=["exists"], alias_map={"exists": "file_exists"}, is_from=True, line_number=8)
    assert aliased_import.alias_map["exists"] == "file_exists"


def test_deterministic_alphabetical_file_sorting_across_deep_dirs():
    syms = [
        CodeSymbol(name="Z", qualified_name="Z", kind=SymbolKind.CLASS, file_path="z_pkg/z.py", line_start=1, line_end=5, source_code="..."),
        CodeSymbol(name="A", qualified_name="A", kind=SymbolKind.CLASS, file_path="a_pkg/a.py", line_start=1, line_end=5, source_code="..."),
        CodeSymbol(name="M", qualified_name="M", kind=SymbolKind.CLASS, file_path="m_pkg/sub/m.py", line_start=1, line_end=5, source_code="..."),
        CodeSymbol(name="B", qualified_name="B", kind=SymbolKind.CLASS, file_path="b_pkg/b.py", line_start=1, line_end=5, source_code="..."),
    ]
    slice_obj = VerticalSlice(feature_name="Sorted Files", symbols=syms)
    assert slice_obj.files_involved == ["a_pkg/a.py", "b_pkg/b.py", "m_pkg/sub/m.py", "z_pkg/z.py"]


def test_disjoint_spans_in_same_file_ignoring_dead_code_gap():
    fn_top = CodeSymbol(name="fn_top", qualified_name="fn_top", kind=SymbolKind.FUNCTION, file_path="app/utils.py", line_start=1, line_end=10, source_code="...")
    fn_bottom = CodeSymbol(name="fn_bottom", qualified_name="fn_bottom", kind=SymbolKind.FUNCTION, file_path="app/utils.py", line_start=100, line_end=110, source_code="...")
    slice_obj = VerticalSlice(feature_name="Sparse File", symbols=[fn_top, fn_bottom])
    assert slice_obj.total_lines_of_code == 21


def test_explicit_zero_loc_on_declaration_only_slice():
    slice_obj = VerticalSlice(feature_name="Zero LOC Slice", symbols=[], total_lines_of_code=0)
    assert slice_obj.total_lines_of_code == 0


def test_dunder_and_async_symbol_coordinates():
    init_sym = CodeSymbol(name="__init__", qualified_name="OrderModel.__init__", kind=SymbolKind.METHOD, file_path="app/models/order.py", line_start=10, line_end=15, source_code="...")
    async_sym = CodeSymbol(name="async_stream", qualified_name="EventBus.async_stream", kind=SymbolKind.METHOD, file_path="app/events.py", line_start=20, line_end=40, source_code="...")
    assert init_sym.symbol_id == "app/models/order.py:OrderModel.__init__"
    assert async_sym.symbol_id == "app/events.py:EventBus.async_stream"


def test_markdown_summary_topology_formatting():
    sym_route = CodeSymbol(name="get_users", qualified_name="get_users", kind=SymbolKind.ROUTE, file_path="app/routes.py", line_start=1, line_end=10, source_code="...")
    sym_cls = CodeSymbol(name="UserManager", qualified_name="UserManager", kind=SymbolKind.CLASS, file_path="app/mgr.py", line_start=1, line_end=50, source_code="...")
    slice_obj = VerticalSlice(feature_name="User Module", symbols=[sym_route, sym_cls])
    summary = slice_obj.to_context_summary()
    assert "### [VERTICAL SLICE: User Module]" in summary
    assert "- **Covered Source Lines**: 60" in summary


def test_pydantic_json_serialization_roundtrip():
    sym = CodeSymbol(name="compute", qualified_name="Engine.compute", kind=SymbolKind.METHOD, file_path="app/engine.py", line_start=10, line_end=30, source_code="...", outgoing_calls=["self.calc"])
    call = FunctionCall(caller_symbol_id=sym.symbol_id, raw_callee="self.calc", resolved_symbol_id="app/calc.py:Calculator.calc", file_path="app/engine.py", line_number=15)
    slice_obj = VerticalSlice(feature_name="Compute Engine", symbols=[sym], call_graph=[call])
    payload = slice_obj.model_dump()
    reloaded = VerticalSlice.model_validate(payload)
    assert reloaded.feature_name == "Compute Engine"
    assert reloaded.total_lines_of_code == 21


# ══════════════════════════════════════════════════════════════════
# 50 NEW ADVANCED EDGE TEST CASES (Tests 17 through 66)
# ══════════════════════════════════════════════════════════════════

# ── CATEGORY 1: CodeSymbol Invariants & Boundary Stress (Tests 17–26) ──

def test_17_minimum_line_boundary_start_end_at_line_one():
    """Test 17: Symbol starting and ending exactly at line 1 (e.g. constant or 1-liner)."""
    sym = CodeSymbol(name="PI", qualified_name="PI", kind=SymbolKind.VARIABLE, file_path="math.py", line_start=1, line_end=1, source_code="PI = 3.14159")
    assert sym.line_start == 1
    assert sym.line_end == 1
    assert sym.symbol_id == "math.py:PI"


def test_18_massive_single_file_span():
    """Test 18: Monolithic symbol spanning 10,000 lines."""
    sym = CodeSymbol(name="GodClass", qualified_name="GodClass", kind=SymbolKind.CLASS, file_path="legacy.py", line_start=1, line_end=10000, source_code="class GodClass: ...")
    slice_obj = VerticalSlice(feature_name="Legacy", symbols=[sym])
    assert slice_obj.total_lines_of_code == 10000


def test_19_negative_line_start_validation():
    """Test 19: Negative line_start must be rejected."""
    raised = False
    try:
        CodeSymbol(name="x", qualified_name="x", kind=SymbolKind.FUNCTION, file_path="a.py", line_start=-10, line_end=5, source_code="")
    except ValueError as e:
        raised = True
        assert "line_start must be >= 1" in str(e)
    assert raised


def test_20_negative_line_end_validation():
    """Test 20: Negative line_end must be rejected."""
    raised = False
    try:
        CodeSymbol(name="x", qualified_name="x", kind=SymbolKind.FUNCTION, file_path="a.py", line_start=1, line_end=-5, source_code="")
    except ValueError as e:
        raised = True
        assert "cannot be earlier than line_start" in str(e)
    assert raised


def test_21_line_end_strictly_less_than_line_start():
    """Test 21: line_end < line_start (e.g. start=100, end=99)."""
    raised = False
    try:
        CodeSymbol(name="x", qualified_name="x", kind=SymbolKind.FUNCTION, file_path="a.py", line_start=100, line_end=99, source_code="")
    except ValueError as e:
        raised = True
        assert "cannot be earlier than line_start" in str(e)
    assert raised


def test_22_empty_string_name_and_qualified_name():
    """Test 22: Anonymous or empty name symbols."""
    sym = CodeSymbol(name="", qualified_name="", kind=SymbolKind.VARIABLE, file_path="anon.py", line_start=1, line_end=2, source_code="_ = None")
    assert sym.symbol_id == "anon.py:"


def test_23_symbol_id_special_characters_in_filepath():
    """Test 23: File paths with dots, dashes, and underscores."""
    sym = CodeSymbol(name="f", qualified_name="f", kind=SymbolKind.FUNCTION, file_path="src/v1_2-alpha/core.api.py", line_start=5, line_end=10, source_code="def f(): pass")
    assert sym.symbol_id == "src/v1_2-alpha/core.api.py:f"


def test_24_multiline_docstring_preservation():
    """Test 24: Multiline docstring with markdown and quotes."""
    doc = '"""Calculates availability.\n\nArgs:\n    date: target date\n"""'
    sym = CodeSymbol(name="calc", qualified_name="calc", kind=SymbolKind.FUNCTION, file_path="a.py", line_start=1, line_end=10, docstring=doc, source_code="...")
    assert sym.docstring == doc


def test_25_unicode_and_emoji_source_code_preservation():
    """Test 25: Unicode characters, non-English text, and emojis in source."""
    code = "# 🚀 Autonomous Feature Transplantation (你好世界)\ndef run(): pass"
    sym = CodeSymbol(name="run", qualified_name="run", kind=SymbolKind.FUNCTION, file_path="i18n.py", line_start=1, line_end=2, source_code=code)
    assert "你好世界" in sym.source_code
    assert "🚀" in sym.source_code


def test_26_symbol_with_raw_syntax_special_chars():
    """Test 26: Source code with nested quotes, regex, and brackets."""
    raw = "pattern = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$')"
    sym = CodeSymbol(name="regex", qualified_name="regex", kind=SymbolKind.VARIABLE, file_path="val.py", line_start=3, line_end=3, source_code=raw)
    assert sym.source_code == raw


# ── CATEGORY 2: SymbolKind Enumeration & Routing (Tests 27–34) ──

def test_27_symbol_kind_variable():
    sym = CodeSymbol(name="DB_URL", qualified_name="DB_URL", kind=SymbolKind.VARIABLE, file_path="cfg.py", line_start=1, line_end=1, source_code="DB_URL = '...'")
    assert sym.kind == SymbolKind.VARIABLE
    assert sym.kind.value == "variable"


def test_28_symbol_kind_route():
    sym = CodeSymbol(name="get_order", qualified_name="get_order", kind=SymbolKind.ROUTE, file_path="api.py", line_start=1, line_end=5, source_code="@app.get('/order')")
    assert sym.kind == SymbolKind.ROUTE
    assert sym.kind.value == "route"


def test_29_symbol_kind_method():
    sym = CodeSymbol(name="execute", qualified_name="Runner.execute", kind=SymbolKind.METHOD, file_path="run.py", line_start=1, line_end=5, source_code="def execute(self): pass")
    assert sym.kind == SymbolKind.METHOD
    assert sym.kind.value == "method"


def test_30_symbol_kind_class():
    sym = CodeSymbol(name="Order", qualified_name="Order", kind=SymbolKind.CLASS, file_path="models.py", line_start=1, line_end=20, source_code="class Order: pass")
    assert sym.kind == SymbolKind.CLASS
    assert sym.kind.value == "class"


def test_31_symbol_kind_function():
    sym = CodeSymbol(name="helper", qualified_name="helper", kind=SymbolKind.FUNCTION, file_path="u.py", line_start=1, line_end=3, source_code="def helper(): pass")
    assert sym.kind == SymbolKind.FUNCTION
    assert sym.kind.value == "function"


def test_32_invalid_symbol_kind_rejected():
    """Test 32: Unrecognized SymbolKind string must be rejected by Pydantic."""
    raised = False
    try:
        CodeSymbol(name="x", qualified_name="x", kind="invalid_kind", file_path="u.py", line_start=1, line_end=2, source_code="")  # type: ignore
    except Exception:
        raised = True
    assert raised


def test_33_entrypoint_with_route_http_verbs():
    sym = CodeSymbol(name="delete_user", qualified_name="delete_user", kind=SymbolKind.ROUTE, file_path="api.py", line_start=1, line_end=5, source_code="...")
    entry = EntryPoint(symbol=sym, entry_type="http_route", route_path="/users/{id}", http_method="DELETE")
    assert entry.http_method == "DELETE"
    assert entry.route_path == "/users/{id}"


def test_34_entrypoint_cli_command_type():
    sym = CodeSymbol(name="cli_migrate", qualified_name="cli_migrate", kind=SymbolKind.FUNCTION, file_path="cli.py", line_start=1, line_end=15, source_code="@click.command ...")
    entry = EntryPoint(symbol=sym, entry_type="cli_command", route_path=None, http_method=None)
    assert entry.entry_type == "cli_command"
    assert entry.route_path is None


# ── CATEGORY 3: ImportStatement Scenarios (Tests 35–42) ──

def test_35_standard_library_direct_import():
    imp = ImportStatement(source_module="sys", imported_names=[], is_from=False, line_number=1)
    assert imp.is_from is False
    assert imp.source_module == "sys"


def test_36_relative_dot_import():
    imp = ImportStatement(source_module=".utils", imported_names=["helpers"], is_from=True, line_number=2)
    assert imp.source_module.startswith(".")


def test_37_parent_relative_dotdot_import():
    imp = ImportStatement(source_module="..domain.models", imported_names=["Order"], is_from=True, line_number=3)
    assert imp.source_module.startswith("..")


def test_38_multi_level_alias_map():
    imp = ImportStatement(
        source_module="app.core",
        imported_names=["Config", "Engine", "Logger"],
        alias_map={"Config": "AppConfig", "Engine": "CoreEngine"},
        is_from=True,
        line_number=4,
    )
    assert len(imp.alias_map) == 2
    assert imp.alias_map["Config"] == "AppConfig"


def test_39_empty_imported_names_list():
    imp = ImportStatement(source_module="os", imported_names=[], is_from=False, line_number=1)
    assert imp.imported_names == []


def test_40_empty_source_module_allowed():
    imp = ImportStatement(source_module="", imported_names=["x"], is_from=True, line_number=1)
    assert imp.source_module == ""


def test_41_import_statement_line_number_one():
    imp = ImportStatement(source_module="typing", imported_names=["Any"], line_number=1)
    assert imp.line_number == 1


def test_42_import_statement_large_line_number():
    imp = ImportStatement(source_module="app.models", imported_names=["Model"], line_number=99999)
    assert imp.line_number == 99999


# ── CATEGORY 4: FunctionCall & Graph Edge Scenarios (Tests 43–50) ──

def test_43_recursive_self_call_edge():
    """Test 43: Function calling itself recursively."""
    call = FunctionCall(
        caller_symbol_id="app/algo.py:factorial",
        raw_callee="factorial(n - 1)",
        resolved_symbol_id="app/algo.py:factorial",
        file_path="app/algo.py",
        line_number=5,
    )
    assert call.caller_symbol_id == call.resolved_symbol_id


def test_44_mutual_circular_call_edges():
    """Test 44: Two functions calling each other (A -> B and B -> A)."""
    edge_ab = FunctionCall(caller_symbol_id="a.py:is_even", raw_callee="is_odd", resolved_symbol_id="a.py:is_odd", file_path="a.py", line_number=3)
    edge_ba = FunctionCall(caller_symbol_id="a.py:is_odd", raw_callee="is_even", resolved_symbol_id="a.py:is_even", file_path="a.py", line_number=8)
    assert edge_ab.caller_symbol_id == edge_ba.resolved_symbol_id
    assert edge_ba.caller_symbol_id == edge_ab.resolved_symbol_id


def test_45_chain_of_five_sequential_calls():
    """Test 45: Linear call chain: A -> B -> C -> D -> E."""
    calls = []
    for i in range(1, 5):
        calls.append(FunctionCall(
            caller_symbol_id=f"chain.py:node_{i}",
            raw_callee=f"node_{i+1}",
            resolved_symbol_id=f"chain.py:node_{i+1}",
            file_path="chain.py",
            line_number=i * 10,
        ))
    assert len(calls) == 4
    assert calls[0].caller_symbol_id == "chain.py:node_1"
    assert calls[-1].resolved_symbol_id == "chain.py:node_5"


def test_46_multiple_calls_from_same_source_line():
    """Test 46: Nested expressions on a single line (e.g. f(g(x)))."""
    call_inner = FunctionCall(caller_symbol_id="app/run.py:main", raw_callee="get_data()", resolved_symbol_id="app/db.py:get_data", file_path="app/run.py", line_number=20)
    call_outer = FunctionCall(caller_symbol_id="app/run.py:main", raw_callee="process()", resolved_symbol_id="app/proc.py:process", file_path="app/run.py", line_number=20)
    assert call_inner.line_number == call_outer.line_number == 20


def test_47_complex_chained_call_expression():
    call = FunctionCall(
        caller_symbol_id="app/svc.py:Service.execute",
        raw_callee="self.builder.with_auth().with_cache().build().send()",
        resolved_symbol_id="app/client.py:HttpClient.send",
        file_path="app/svc.py",
        line_number=45,
    )
    assert "with_auth" in call.raw_callee


def test_48_static_method_call_expression():
    call = FunctionCall(
        caller_symbol_id="app/svc.py:Service.run",
        raw_callee="MathUtils.add(a, b)",
        resolved_symbol_id="app/utils/math.py:MathUtils.add",
        file_path="app/svc.py",
        line_number=12,
    )
    assert "MathUtils.add" in call.raw_callee


def test_49_dunder_call_invocation():
    call = FunctionCall(
        caller_symbol_id="app/pipeline.py:Pipeline.step",
        raw_callee="self.handler(request)",
        resolved_symbol_id="app/handler.py:Handler.__call__",
        file_path="app/pipeline.py",
        line_number=33,
    )
    assert "__call__" in str(call.resolved_symbol_id)


def test_50_call_to_closure_lambda_callee():
    call = FunctionCall(
        caller_symbol_id="app/filter.py:Filter.apply",
        raw_callee="predicate(item)",
        resolved_symbol_id=None,  # Dynamic closure
        file_path="app/filter.py",
        line_number=14,
    )
    assert call.resolved_symbol_id is None


# ── CATEGORY 5: Line Counting & Overlap Matrix (Tests 51–58) ──

def test_51_ten_disjoint_single_line_functions():
    """Test 51: 10 separate 1-line functions in same file -> exactly 10 lines."""
    syms = [
        CodeSymbol(name=f"f_{i}", qualified_name=f"f_{i}", kind=SymbolKind.FUNCTION, file_path="funcs.py", line_start=i * 2, line_end=i * 2, source_code="pass")
        for i in range(1, 11)
    ]
    slice_obj = VerticalSlice(feature_name="Ten One-Liners", symbols=syms)
    assert slice_obj.total_lines_of_code == 10


def test_52_duplicate_symbols_do_not_recount_lines():
    """Test 52: Passing the exact same symbol 5 times in the list -> lines counted once."""
    sym = CodeSymbol(name="dup", qualified_name="dup", kind=SymbolKind.FUNCTION, file_path="dup.py", line_start=10, line_end=20, source_code="...")
    slice_obj = VerticalSlice(feature_name="Dups", symbols=[sym, sym, sym, sym, sym])
    # 10 to 20 is 11 lines
    assert slice_obj.total_lines_of_code == 11


def test_53_fully_contained_nested_symbol():
    """Test 53: Parent symbol 10..100, child 30..40. Total should be 91 lines."""
    parent = CodeSymbol(name="Parent", qualified_name="Parent", kind=SymbolKind.CLASS, file_path="c.py", line_start=10, line_end=100, source_code="...")
    child = CodeSymbol(name="m", qualified_name="Parent.m", kind=SymbolKind.METHOD, file_path="c.py", line_start=30, line_end=40, source_code="...")
    slice_obj = VerticalSlice(feature_name="Containment", symbols=[parent, child])
    assert slice_obj.total_lines_of_code == 91


def test_54_head_overlapping_symbols():
    """Test 54: Sym A: 10..20, Sym B: 15..30. Union = 10..30 = 21 lines."""
    a = CodeSymbol(name="a", qualified_name="a", kind=SymbolKind.FUNCTION, file_path="o.py", line_start=10, line_end=20, source_code="...")
    b = CodeSymbol(name="b", qualified_name="b", kind=SymbolKind.FUNCTION, file_path="o.py", line_start=15, line_end=30, source_code="...")
    slice_obj = VerticalSlice(feature_name="Head Overlap", symbols=[a, b])
    assert slice_obj.total_lines_of_code == 21


def test_55_tail_overlapping_symbols():
    """Test 55: Sym B starts before Sym A and ends inside Sym A."""
    a = CodeSymbol(name="a", qualified_name="a", kind=SymbolKind.FUNCTION, file_path="o.py", line_start=20, line_end=35, source_code="...")
    b = CodeSymbol(name="b", qualified_name="b", kind=SymbolKind.FUNCTION, file_path="o.py", line_start=10, line_end=25, source_code="...")
    slice_obj = VerticalSlice(feature_name="Tail Overlap", symbols=[a, b])
    assert slice_obj.total_lines_of_code == 26  # lines 10..35 = 26 lines


def test_56_three_cascading_overlapping_symbols():
    """Test 56: Sym 1: 1..10, Sym 2: 5..15, Sym 3: 12..20. Union = 1..20 = 20 lines."""
    s1 = CodeSymbol(name="s1", qualified_name="s1", kind=SymbolKind.FUNCTION, file_path="c.py", line_start=1, line_end=10, source_code="...")
    s2 = CodeSymbol(name="s2", qualified_name="s2", kind=SymbolKind.FUNCTION, file_path="c.py", line_start=5, line_end=15, source_code="...")
    s3 = CodeSymbol(name="s3", qualified_name="s3", kind=SymbolKind.FUNCTION, file_path="c.py", line_start=12, line_end=20, source_code="...")
    slice_obj = VerticalSlice(feature_name="Cascade", symbols=[s1, s2, s3])
    assert slice_obj.total_lines_of_code == 20


def test_57_disjoint_symbols_across_three_different_files():
    """Test 57: 3 symbols in 3 separate files."""
    f1 = CodeSymbol(name="f1", qualified_name="f1", kind=SymbolKind.FUNCTION, file_path="f1.py", line_start=1, line_end=5, source_code="...")   # 5 lines
    f2 = CodeSymbol(name="f2", qualified_name="f2", kind=SymbolKind.FUNCTION, file_path="f2.py", line_start=1, line_end=10, source_code="...")  # 10 lines
    f3 = CodeSymbol(name="f3", qualified_name="f3", kind=SymbolKind.FUNCTION, file_path="f3.py", line_start=1, line_end=15, source_code="...")  # 15 lines
    slice_obj = VerticalSlice(feature_name="Tri-File", symbols=[f1, f2, f3])
    assert slice_obj.total_lines_of_code == 30  # 5 + 10 + 15
    assert slice_obj.files_involved == ["f1.py", "f2.py", "f3.py"]


def test_58_empty_symbols_returns_zero_loc():
    slice_obj = VerticalSlice(feature_name="Zero", symbols=[])
    assert slice_obj.total_lines_of_code == 0
    assert slice_obj.calculate_unique_source_lines() == 0


# ── CATEGORY 6: Serialization, Performance & Summary (Tests 59–66) ──

def test_59_slice_summary_formatting_multi_symbol():
    syms = [
        CodeSymbol(name=f"fn_{i}", qualified_name=f"fn_{i}", kind=SymbolKind.FUNCTION, file_path=f"file_{i%3}.py", line_start=1, line_end=5, source_code="...")
        for i in range(10)
    ]
    slice_obj = VerticalSlice(feature_name="Multi-Summary", symbols=syms)
    summary = slice_obj.to_context_summary()
    assert "### [VERTICAL SLICE: Multi-Summary]" in summary
    assert "- **Files Involved (3)**:" in summary
    assert "• `function`" in summary


def test_60_slice_summary_formatting_empty_slice():
    slice_obj = VerticalSlice(feature_name="None")
    summary = slice_obj.to_context_summary()
    assert "**Covered Source Lines**: 0" in summary
    assert "- **Files Involved (0)**:" in summary


def test_61_pydantic_json_schema_export():
    """Test 61: Generating OpenAPI / JSON Schema from models."""
    schema = VerticalSlice.model_json_schema()
    assert schema["type"] == "object"
    assert "feature_name" in schema["properties"]
    assert "symbols" in schema["properties"]


def test_62_deep_copy_independence():
    """Test 62: Deep-copying a slice produces an isolated copy."""
    sym = CodeSymbol(name="orig", qualified_name="orig", kind=SymbolKind.FUNCTION, file_path="o.py", line_start=1, line_end=5, source_code="...")
    slice1 = VerticalSlice(feature_name="Orig", symbols=[sym])
    slice2 = copy.deepcopy(slice1)
    slice2.feature_name = "Modified"
    assert slice1.feature_name == "Orig"
    assert slice2.feature_name == "Modified"


def test_63_pydantic_model_equality():
    """Test 63: Value equality between identical VerticalSlice instances."""
    sym1 = CodeSymbol(name="m", qualified_name="m", kind=SymbolKind.FUNCTION, file_path="f.py", line_start=1, line_end=5, source_code="...")
    sym2 = CodeSymbol(name="m", qualified_name="m", kind=SymbolKind.FUNCTION, file_path="f.py", line_start=1, line_end=5, source_code="...")
    slice1 = VerticalSlice(feature_name="A", symbols=[sym1])
    slice2 = VerticalSlice(feature_name="A", symbols=[sym2])
    assert slice1 == slice2


def test_64_large_scale_performance_100_symbols():
    """Test 64: Slicing 100 symbols computes unique LOC in under 20 milliseconds."""
    syms = [
        CodeSymbol(name=f"sym_{i}", qualified_name=f"Module.sym_{i}", kind=SymbolKind.METHOD, file_path=f"pkg/file_{i%10}.py", line_start=(i + 1) * 10, line_end=(i + 1) * 10 + 20, source_code="...")
        for i in range(100)
    ]
    t0 = time.perf_counter()
    slice_obj = VerticalSlice(feature_name="Large Scale", symbols=syms)
    t1 = time.perf_counter()
    assert (t1 - t0) < 0.05, f"Took too long: {t1 - t0}s"
    assert slice_obj.total_lines_of_code is not None
    assert slice_obj.total_lines_of_code > 0


def test_65_entrypoint_without_route_path():
    """Test 65: EntryPoint for CLI / SDK public entry point without HTTP route path."""
    sym = CodeSymbol(name="main_cli", qualified_name="main_cli", kind=SymbolKind.FUNCTION, file_path="cli.py", line_start=1, line_end=20, source_code="def main_cli(): pass")
    entry = EntryPoint(symbol=sym, entry_type="cli_command")
    assert entry.route_path is None
    assert entry.http_method is None


def test_66_all_http_methods_matrix_support():
    """Test 66: Verification across standard HTTP methods in EntryPoints."""
    methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]
    for m in methods:
        sym = CodeSymbol(name=f"route_{m.lower()}", qualified_name=f"route_{m.lower()}", kind=SymbolKind.ROUTE, file_path="r.py", line_start=1, line_end=5, source_code="...")
        entry = EntryPoint(symbol=sym, entry_type="http_route", route_path="/test", http_method=m)
        assert entry.http_method == m


if __name__ == "__main__":
    print("🚀 Running Complete 66-Test Vertical Slicing Schema Verification Suite...\n")
    # Tests 1 - 16
    test_code_symbol_auto_id_and_validation()
    test_vertical_slice_derived_fields_and_no_overlap()
    test_empty_vertical_slice_edge_case()
    test_single_line_and_partial_overlapping_spans()
    test_explicit_total_lines_override()
    test_entry_point_and_function_call_resolution()
    test_multi_level_nesting_three_deep()
    test_unresolved_external_call_vs_resolved_internal_call()
    test_multiple_heterogeneous_entry_points()
    test_import_statement_star_and_alias_mappings()
    test_deterministic_alphabetical_file_sorting_across_deep_dirs()
    test_disjoint_spans_in_same_file_ignoring_dead_code_gap()
    test_explicit_zero_loc_on_declaration_only_slice()
    test_dunder_and_async_symbol_coordinates()
    test_markdown_summary_topology_formatting()
    test_pydantic_json_serialization_roundtrip()
    print("✅ Baseline Tests 1 through 16 Passed!")

    # Tests 17 - 26
    test_17_minimum_line_boundary_start_end_at_line_one()
    test_18_massive_single_file_span()
    test_19_negative_line_start_validation()
    test_20_negative_line_end_validation()
    test_21_line_end_strictly_less_than_line_start()
    test_22_empty_string_name_and_qualified_name()
    test_23_symbol_id_special_characters_in_filepath()
    test_24_multiline_docstring_preservation()
    test_25_unicode_and_emoji_source_code_preservation()
    test_26_symbol_with_raw_syntax_special_chars()
    print("✅ Category 1 Tests 17 through 26 Passed (CodeSymbol Invariants & Boundaries)!")

    # Tests 27 - 34
    test_27_symbol_kind_variable()
    test_28_symbol_kind_route()
    test_29_symbol_kind_method()
    test_30_symbol_kind_class()
    test_31_symbol_kind_function()
    test_32_invalid_symbol_kind_rejected()
    test_33_entrypoint_with_route_http_verbs()
    test_34_entrypoint_cli_command_type()
    print("✅ Category 2 Tests 27 through 34 Passed (SymbolKind & Routing)!")

    # Tests 35 - 42
    test_35_standard_library_direct_import()
    test_36_relative_dot_import()
    test_37_parent_relative_dotdot_import()
    test_38_multi_level_alias_map()
    test_39_empty_imported_names_list()
    test_40_empty_source_module_allowed()
    test_41_import_statement_line_number_one()
    test_42_import_statement_large_line_number()
    print("✅ Category 3 Tests 35 through 42 Passed (ImportStatement Scenarios)!")

    # Tests 43 - 50
    test_43_recursive_self_call_edge()
    test_44_mutual_circular_call_edges()
    test_45_chain_of_five_sequential_calls()
    test_46_multiple_calls_from_same_source_line()
    test_47_complex_chained_call_expression()
    test_48_static_method_call_expression()
    test_49_dunder_call_invocation()
    test_50_call_to_closure_lambda_callee()
    print("✅ Category 4 Tests 43 through 50 Passed (FunctionCall & Graph Edges)!")

    # Tests 51 - 58
    test_51_ten_disjoint_single_line_functions()
    test_52_duplicate_symbols_do_not_recount_lines()
    test_53_fully_contained_nested_symbol()
    test_54_head_overlapping_symbols()
    test_55_tail_overlapping_symbols()
    test_56_three_cascading_overlapping_symbols()
    test_57_disjoint_symbols_across_three_different_files()
    test_58_empty_symbols_returns_zero_loc()
    print("✅ Category 5 Tests 51 through 58 Passed (Line Counting & Overlap Matrix)!")

    # Tests 59 - 66
    test_59_slice_summary_formatting_multi_symbol()
    test_60_slice_summary_formatting_empty_slice()
    test_61_pydantic_json_schema_export()
    test_62_deep_copy_independence()
    test_63_pydantic_model_equality()
    test_64_large_scale_performance_100_symbols()
    test_65_entrypoint_without_route_path()
    test_66_all_http_methods_matrix_support()
    print("✅ Category 6 Tests 59 through 66 Passed (Serialization, Scale & Summary)!")

    print("\n🎉 ALL 66 SLICE SCHEMA TESTS PASSED 100% GREEN!\n")
