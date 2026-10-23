"""
Unit and edge test suite for app/slicing/ast_parser.py (PythonAstParser).
Verifies:
1. SymbolParser protocol adherence
2. Empty and whitespace edge cases
3. Functions (sync and async)
4. Classes and Methods with scoped qualified names
5. Web routing endpoints detection (@app.get, @router.post, etc.)
6. Non-route decorators preservation (@classmethod, @property)
7. Nested functions call boundary isolation
8. Outgoing calls extraction (direct, dotted, chained)
9. Import statements (standard, aliased, from-import, relative dots)
10. Module-level variables and constants
11. Nested classes and inner methods
12. Multi-line docstring extraction
13. Line number and source code slicing fidelity
14. Syntax error handling
"""
from app.slicing.interfaces import SymbolParser
from app.slicing.ast_parser import PythonAstParser
from app.schemas.slice import SymbolKind


def test_01_protocol_conformance():
    parser = PythonAstParser()
    assert isinstance(parser, SymbolParser)


def test_02_empty_and_whitespace_sources():
    parser = PythonAstParser()
    symbols, imports = parser.parse_code("", "empty.py")
    assert symbols == []
    assert imports == []

    symbols, imports = parser.parse_code("   \n\t  \n   ", "whitespace.py")
    assert symbols == []
    assert imports == []


def test_03_standalone_function():
    code = '''
def calculate_tax(amount: float, rate: float = 0.15) -> float:
    """Calculates sales tax."""
    return amount * rate
'''
    parser = PythonAstParser()
    symbols, imports = parser.parse_code(code, "tax.py")
    assert len(symbols) == 1
    sym = symbols[0]

    assert sym.name == "calculate_tax"
    assert sym.qualified_name == "calculate_tax"
    assert sym.symbol_id == "tax.py:calculate_tax"
    assert sym.kind == SymbolKind.FUNCTION
    assert sym.docstring == "Calculates sales tax."
    assert "return amount * rate" in sym.source_code
    assert sym.line_start == 2
    assert sym.line_end == 4


def test_04_async_function():
    code = '''
async def fetch_user(user_id: int):
    return await db.find(user_id)
'''
    parser = PythonAstParser()
    symbols, imports = parser.parse_code(code, "async_ops.py")
    assert len(symbols) == 1
    assert symbols[0].name == "fetch_user"
    assert symbols[0].kind == SymbolKind.FUNCTION
    assert symbols[0].symbol_id == "async_ops.py:fetch_user"


def test_05_class_and_methods():
    code = '''
class OrderService:
    """Manages order operations."""
    
    def __init__(self, repo):
        self.repo = repo

    def submit_order(self, order_id: str):
        self.repo.save(order_id)
        notify_user(order_id)
'''
    parser = PythonAstParser()
    symbols, imports = parser.parse_code(code, "services/order.py")

    assert len(symbols) == 3
    cls_sym, init_sym, submit_sym = symbols

    # Check Class
    assert cls_sym.name == "OrderService"
    assert cls_sym.qualified_name == "OrderService"
    assert cls_sym.kind == SymbolKind.CLASS
    assert cls_sym.symbol_id == "services/order.py:OrderService"
    assert cls_sym.docstring == "Manages order operations."

    # Check __init__ method
    assert init_sym.name == "__init__"
    assert init_sym.qualified_name == "OrderService.__init__"
    assert init_sym.kind == SymbolKind.METHOD
    assert init_sym.symbol_id == "services/order.py:OrderService.__init__"

    # Check submit_order method
    assert submit_sym.name == "submit_order"
    assert submit_sym.qualified_name == "OrderService.submit_order"
    assert submit_sym.kind == SymbolKind.METHOD
    assert submit_sym.symbol_id == "services/order.py:OrderService.submit_order"
    assert "self.repo.save" in submit_sym.outgoing_calls
    assert "notify_user" in submit_sym.outgoing_calls


def test_06_route_endpoints_detection():
    code = '''
@app.get("/users/{user_id}")
def get_user(user_id: int):
    return repo.get(user_id)

@router.post("/items")
async def create_item(item: dict):
    return service.create(item)

@api.route("/legacy")
def legacy_endpoint():
    pass
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "routes/user_routes.py")

    assert len(symbols) == 3
    for s in symbols:
        assert s.kind == SymbolKind.ROUTE

    assert symbols[0].name == "get_user"
    assert symbols[1].name == "create_item"
    assert symbols[2].name == "legacy_endpoint"


def test_07_non_route_decorators_not_flagged_as_route():
    code = '''
class MathUtil:
    @staticmethod
    def add(a: int, b: int) -> int:
        return a + b

    @classmethod
    def create(cls):
        return cls()

    @property
    def value(self):
        return 42
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "utils/math.py")

    # MathUtil (CLASS), add (METHOD), create (METHOD), value (METHOD)
    assert len(symbols) == 4
    for s in symbols[1:]:
        assert s.kind == SymbolKind.METHOD
        assert s.kind != SymbolKind.ROUTE


def test_08_nested_function_call_isolation():
    code = '''
def outer_orchestrator():
    def inner_worker():
        sub_call()
    direct_call()
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "nested.py")

    assert len(symbols) == 2
    outer_sym = symbols[0]
    inner_sym = symbols[1]

    assert outer_sym.name == "outer_orchestrator"
    assert inner_sym.name == "inner_worker"

    # sub_call should belong to inner_worker, NOT outer_orchestrator
    assert "direct_call" in outer_sym.outgoing_calls
    assert "sub_call" not in outer_sym.outgoing_calls
    assert "sub_call" in inner_sym.outgoing_calls


def test_09_outgoing_call_expressions_types():
    code = '''
def complex_pipeline():
    simple_func()
    module.service.execute()
    self.db.session.commit()
    get_client().fetch()
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "pipeline.py")

    assert len(symbols) == 1
    calls = symbols[0].outgoing_calls
    assert "simple_func" in calls
    assert "module.service.execute" in calls
    assert "self.db.session.commit" in calls
    assert "get_client().fetch" in calls


def test_10_standard_and_aliased_imports():
    code = '''
import os
import sys, math
import numpy as np
'''
    parser = PythonAstParser()
    _, imports = parser.parse_code(code, "imports_std.py")

    assert len(imports) == 4
    assert imports[0].source_module == "os"
    assert imports[0].is_from is False
    assert imports[0].alias_map == {}

    assert imports[1].source_module == "sys"
    assert imports[2].source_module == "math"

    assert imports[3].source_module == "numpy"
    assert imports[3].alias_map == {"np": "numpy"}


def test_11_from_imports_and_relative_dots():
    code = '''
from app.entities.user import User, Profile
from app.services.auth import AuthService as Auth
from .repositories import UserRepository
from ..utils.helpers import format_date
'''
    parser = PythonAstParser()
    _, imports = parser.parse_code(code, "imports_from.py")

    assert len(imports) == 4

    # 1. from app.entities.user import User, Profile
    assert imports[0].source_module == "app.entities.user"
    assert imports[0].imported_names == ["User", "Profile"]
    assert imports[0].is_from is True
    assert imports[0].alias_map == {}

    # 2. Aliased from import
    assert imports[1].source_module == "app.services.auth"
    assert imports[1].imported_names == ["AuthService"]
    assert imports[1].alias_map == {"Auth": "AuthService"}

    # 3. Single dot relative import (.repositories)
    assert imports[2].source_module == ".repositories"
    assert imports[2].imported_names == ["UserRepository"]

    # 4. Double dot relative import (..utils.helpers)
    assert imports[3].source_module == "..utils.helpers"
    assert imports[3].imported_names == ["format_date"]


def test_12_module_level_variables_and_constants():
    code = '''
MAX_CONNECTIONS = 100
DEFAULT_TIMEOUT: int = 30
db_pool = create_pool()

class Unrelated:
    CLASS_VAR = 10
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "constants.py")

    vars_only = [s for s in symbols if s.kind == SymbolKind.VARIABLE]
    assert len(vars_only) == 3
    names = [v.name for v in vars_only]
    assert "MAX_CONNECTIONS" in names
    assert "DEFAULT_TIMEOUT" in names
    assert "db_pool" in names
    # CLASS_VAR inside Unrelated should NOT be collected as a module-level VARIABLE
    assert "CLASS_VAR" not in names


def test_13_nested_classes():
    code = '''
class Tree:
    class Node:
        def get_value(self):
            return 42
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "tree.py")

    assert len(symbols) == 3
    tree_sym, node_sym, method_sym = symbols

    assert tree_sym.qualified_name == "Tree"
    assert node_sym.qualified_name == "Tree.Node"
    assert method_sym.qualified_name == "Tree.Node.get_value"
    assert method_sym.symbol_id == "tree.py:Tree.Node.get_value"


def test_14_syntax_error_propagates():
    code = '''
def broken_syntax(
    print("missing closing paren"
'''
    parser = PythonAstParser()
    syntax_error_raised = False
    try:
        parser.parse_code(code, "broken.py")
    except SyntaxError:
        syntax_error_raised = True
    assert syntax_error_raised, "Expected SyntaxError to be raised for invalid code"


def test_15_source_slicing_fidelity():
    code = '''# Line 1
def first():
    return 1

# Line 5
def second():
    return 2
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "sample.py")

    assert len(symbols) == 2
    first_sym, second_sym = symbols

    assert first_sym.line_start == 2
    assert first_sym.line_end == 3
    assert first_sym.source_code == "def first():\n    return 1"

    assert second_sym.line_start == 6
    assert second_sym.line_end == 7
    assert second_sym.source_code == "def second():\n    return 2"


def test_16_multi_decorator_route_endpoint():
    code = '''
@require_auth
@rate_limit(max_requests=10)
@app.post("/secure/checkout")
@audit_log(event="checkout_initiated")
def secure_checkout(order: dict):
    return process_order(order)
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "checkout.py")
    assert len(symbols) == 1
    assert symbols[0].kind == SymbolKind.ROUTE
    assert symbols[0].name == "secure_checkout"
    assert "process_order" in symbols[0].outgoing_calls


def test_17_multiple_classes_with_identical_method_names():
    code = '''
class SqlUserRepository:
    def save(self, user):
        db.insert(user)

class MongoUserRepository:
    def save(self, user):
        mongo.collection.insert_one(user)
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "repos/users.py")
    assert len(symbols) == 4
    sql_repo, sql_save, mongo_repo, mongo_save = symbols

    assert sql_save.qualified_name == "SqlUserRepository.save"
    assert sql_save.symbol_id == "repos/users.py:SqlUserRepository.save"
    assert "db.insert" in sql_save.outgoing_calls

    assert mongo_save.qualified_name == "MongoUserRepository.save"
    assert mongo_save.symbol_id == "repos/users.py:MongoUserRepository.save"
    assert "mongo.collection.insert_one" in mongo_save.outgoing_calls


def test_18_calls_inside_comprehensions():
    code = '''
def process_items(items):
    clean = [normalize_text(i) for i in items if validate_item(i)]
    lookup = {calc_key(k): transform_val(v) for k, v in items.items()}
    return clean, lookup
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "comp.py")
    assert len(symbols) == 1
    calls = symbols[0].outgoing_calls
    assert "normalize_text" in calls
    assert "validate_item" in calls
    assert "calc_key" in calls
    assert "transform_val" in calls


def test_19_relative_import_without_module_name():
    code = '''
from . import config, utils
from .. import parent_config
'''
    parser = PythonAstParser()
    _, imports = parser.parse_code(code, "relative.py")
    assert len(imports) == 2
    assert imports[0].source_module == "."
    assert imports[0].imported_names == ["config", "utils"]
    assert imports[1].source_module == ".."
    assert imports[1].imported_names == ["parent_config"]


def test_20_star_import():
    code = '''
from math import *
'''
    parser = PythonAstParser()
    _, imports = parser.parse_code(code, "math_star.py")
    assert len(imports) == 1
    assert imports[0].source_module == "math"
    assert imports[0].imported_names == ["*"]
    assert imports[0].is_from is True


def test_21_lambda_calls_do_not_crash():
    code = '''
def calculate():
    result = (lambda x: x * 2)(10)
    fn = lambda y: custom_func(y)
    return result
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "lambda_calc.py")
    assert len(symbols) == 1
    assert "custom_func" in symbols[0].outgoing_calls


def test_22_class_with_class_decorator():
    code = '''
@dataclass
class Customer:
    id: int
    name: str

    def display(self):
        return f"{self.id}: {self.name}"
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "models/customer.py")
    assert len(symbols) == 2
    cls_sym, method_sym = symbols
    assert cls_sym.kind == SymbolKind.CLASS
    assert cls_sym.name == "Customer"
    assert method_sym.kind == SymbolKind.METHOD
    assert method_sym.name == "display"


def test_23_tuple_assignment_variables():
    code = '''
HOST, PORT = "0.0.0.0", 8080
DEBUG = True
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "config.py")
    vars_only = [s for s in symbols if s.kind == SymbolKind.VARIABLE]
    names = [v.name for v in vars_only]
    assert "HOST" in names
    assert "PORT" in names
    assert "DEBUG" in names


def test_24_multi_line_docstring_extraction():
    code = '''
def complex_algorithm(data):
    """
    Executes a three-stage pipeline:
    1. Filter invalid data.
    2. Normalize vectors.
    3. Calculate cosine similarity.
    """
    pass
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "algo.py")
    assert len(symbols) == 1
    doc = symbols[0].docstring
    assert "Executes a three-stage pipeline:" in doc
    assert "Calculate cosine similarity." in doc


def test_25_async_methods_inside_class():
    code = '''
class AsyncWorker:
    async def run(self):
        await self.execute_task()
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "worker.py")
    assert len(symbols) == 2
    method_sym = symbols[1]
    assert method_sym.kind == SymbolKind.METHOD
    assert method_sym.qualified_name == "AsyncWorker.run"
    assert "self.execute_task" in method_sym.outgoing_calls


def test_26_empty_function_and_class_bodies():
    code = '''
class MarkerInterface:
    pass

def noop():
    ...
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "markers.py")
    assert len(symbols) == 2
    assert symbols[0].name == "MarkerInterface"
    assert symbols[0].kind == SymbolKind.CLASS
    assert symbols[1].name == "noop"
    assert symbols[1].kind == SymbolKind.FUNCTION


def test_27_chained_method_invocations():
    code = '''
def fluent_query():
    db.session.query(User).filter(User.active == True).order_by(User.name).all()
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "query.py")
    assert len(symbols) == 1
    calls = symbols[0].outgoing_calls
    # Should capture the calls in the fluent chain
    assert any("query" in c for c in calls)
    assert any("filter" in c for c in calls)
    assert any("order_by" in c for c in calls)
    assert any("all" in c for c in calls)


def test_28_comments_only_file():
    code = '''
# Copyright 2026
# Licensed under Apache 2.0
# Just comments and docstrings
'''
    parser = PythonAstParser()
    symbols, imports = parser.parse_code(code, "comments.py")
    assert symbols == []
    assert imports == []


def test_29_route_without_parentheses():
    code = '''
@app.get
def raw_endpoint():
    return {"status": "ok"}
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "raw_route.py")
    assert len(symbols) == 1
    assert symbols[0].kind == SymbolKind.ROUTE
    assert symbols[0].name == "raw_endpoint"


def test_30_symbol_invariants_pass_on_all_extracted_symbols():
    code = '''
import math

GLOBAL_LIMIT: int = 500

class Analyzer:
    """Class doc."""
    def run(self):
        return math.sqrt(GLOBAL_LIMIT)

@router.delete("/resource/{id}")
def delete_resource(id: int):
    cleanup(id)
'''
    parser = PythonAstParser()
    symbols, imports = parser.parse_code(code, "invariants_check.py")
    assert len(symbols) == 4
    for sym in symbols:
        # Pydantic validator will have verified line_start >= 1, line_end >= line_start,
        # and symbol_id == f"{sym.file_path}:{sym.qualified_name}"
        assert sym.line_start >= 1
        assert sym.line_end >= sym.line_start
        assert sym.symbol_id == f"invariants_check.py:{sym.qualified_name}"


# ============================================================================
# CATEGORY A: Complex Class Invariants & Metaprogramming (Tests 31 to 38)
# ============================================================================

def test_31_single_inheritance_class():
    code = '''
class BaseService:
    pass

class OrderService(BaseService):
    def run(self):
        pass
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "services/order.py")
    assert len(symbols) == 3
    base_sym, order_sym, run_sym = symbols
    assert base_sym.name == "BaseService"
    assert order_sym.name == "OrderService"
    assert run_sym.qualified_name == "OrderService.run"


def test_32_multiple_inheritance_class():
    code = '''
class MixinA: pass
class MixinB: pass
class Composite(MixinA, MixinB):
    def execute(self):
        pass
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "mixins.py")
    assert len(symbols) == 4
    composite = symbols[2]
    assert composite.name == "Composite"
    assert composite.kind == SymbolKind.CLASS


def test_33_metaclass_declaration():
    code = '''
class Meta(type): pass
class Config(metaclass=Meta):
    pass
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "meta.py")
    assert len(symbols) == 2
    assert symbols[0].name == "Meta"
    assert symbols[1].name == "Config"


def test_34_dunder_magic_methods():
    code = '''
class ManagedResource:
    def __init__(self, name):
        self.name = name

    def __enter__(self):
        acquire_lock(self.name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        release_lock(self.name)
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "resource.py")
    assert len(symbols) == 4
    names = [s.name for s in symbols]
    assert "__init__" in names
    assert "__enter__" in names
    assert "__exit__" in names
    enter_sym = [s for s in symbols if s.name == "__enter__"][0]
    assert "acquire_lock" in enter_sym.outgoing_calls


def test_35_property_getter_and_setter():
    code = '''
class Account:
    @property
    def balance(self):
        return get_balance()

    @balance.setter
    def balance(self, val):
        set_balance(val)
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "account.py")
    assert len(symbols) == 3
    for s in symbols[1:]:
        assert s.kind == SymbolKind.METHOD
        assert s.qualified_name == "Account.balance"


def test_36_abstract_methods():
    code = '''
from abc import ABC, abstractmethod

class AbstractRepository(ABC):
    @abstractmethod
    def find_by_id(self, id: int):
        pass
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "repo_base.py")
    assert len(symbols) == 2
    assert symbols[1].kind == SymbolKind.METHOD
    assert symbols[1].qualified_name == "AbstractRepository.find_by_id"


def test_37_three_level_nested_classes():
    code = '''
class Level1:
    class Level2:
        class Level3:
            def deep_act(self):
                return 42
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "nested_deep.py")
    assert len(symbols) == 4
    assert symbols[0].qualified_name == "Level1"
    assert symbols[1].qualified_name == "Level1.Level2"
    assert symbols[2].qualified_name == "Level1.Level2.Level3"
    assert symbols[3].qualified_name == "Level1.Level2.Level3.deep_act"


def test_38_class_inside_function_factory():
    code = '''
def make_handler():
    class LocalHandler:
        def handle(self):
            return 42
    return LocalHandler()
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "factory.py")
    assert len(symbols) == 3
    fn_sym, cls_sym, method_sym = symbols
    assert fn_sym.name == "make_handler"
    assert cls_sym.name == "LocalHandler"
    assert method_sym.name == "handle"


# ============================================================================
# CATEGORY B: Function Signatures & Advanced Arguments (Tests 39 to 46)
# ============================================================================

def test_39_positional_only_parameters():
    code = '''
def pos_only(a, b, /, c):
    return a + b + c
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "pos.py")
    assert len(symbols) == 1
    assert symbols[0].name == "pos_only"
    assert symbols[0].kind == SymbolKind.FUNCTION


def test_40_keyword_only_parameters():
    code = '''
def kw_only(a, *, key=True, val=10):
    return a if key else val
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "kw.py")
    assert len(symbols) == 1
    assert symbols[0].name == "kw_only"


def test_41_variadic_args_and_kwargs():
    code = '''
def var_args(*args, **kwargs):
    log_args(args)
    log_kwargs(kwargs)
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "var.py")
    assert len(symbols) == 1
    calls = symbols[0].outgoing_calls
    assert "log_args" in calls
    assert "log_kwargs" in calls


def test_42_default_arg_with_function_call():
    code = '''
def query_data(timeout=get_timeout(), retries=calc_retries()):
    pass
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "defaults.py")
    assert len(symbols) == 1
    assert symbols[0].name == "query_data"


def test_43_generator_with_yield():
    code = '''
def number_stream():
    yield 1
    yield 2
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "gen.py")
    assert len(symbols) == 1
    assert symbols[0].name == "number_stream"


def test_44_async_generator_with_yield():
    code = '''
async def async_event_stream():
    while has_events():
        yield await fetch_event()
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "agen.py")
    assert len(symbols) == 1
    assert symbols[0].name == "async_event_stream"
    assert "has_events" in symbols[0].outgoing_calls
    assert "fetch_event" in symbols[0].outgoing_calls


def test_45_yield_from_generator():
    code = '''
def delegating_gen():
    yield from child_gen()
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "delegating.py")
    assert len(symbols) == 1
    assert "child_gen" in symbols[0].outgoing_calls


def test_46_complex_generic_type_annotations():
    code = '''
def complex_signature(items: list[dict[str, list[int]]]) -> dict[str, tuple[int, ...]]:
    return transform(items)
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "sig.py")
    assert len(symbols) == 1
    assert symbols[0].name == "complex_signature"
    assert "transform" in symbols[0].outgoing_calls


# ============================================================================
# CATEGORY C: Control Flow & Context Expressions (Tests 47 to 56)
# ============================================================================

def test_47_calls_inside_with_statement():
    code = '''
def db_transaction():
    with open_db() as conn:
        conn.execute()
        commit_tx()
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "tx.py")
    calls = symbols[0].outgoing_calls
    assert "open_db" in calls
    assert "conn.execute" in calls
    assert "commit_tx" in calls


def test_48_calls_inside_async_with():
    code = '''
async def async_session_work():
    async with get_session() as sess:
        await sess.flush()
        notify_flush()
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "async_tx.py")
    calls = symbols[0].outgoing_calls
    assert "get_session" in calls
    assert "sess.flush" in calls
    assert "notify_flush" in calls


def test_49_calls_inside_try_except_else_finally():
    code = '''
def robust_pipeline():
    try:
        step_one()
    except ValueError as e:
        handle_value_error(e)
    else:
        step_two()
    finally:
        cleanup_pipeline()
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "robust.py")
    calls = symbols[0].outgoing_calls
    assert "step_one" in calls
    assert "handle_value_error" in calls
    assert "step_two" in calls
    assert "cleanup_pipeline" in calls


def test_50_calls_inside_for_else():
    code = '''
def search_items(items):
    for item in items:
        if match(item):
            found_action(item)
            break
    else:
        not_found_action()
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "for_else.py")
    calls = symbols[0].outgoing_calls
    assert "match" in calls
    assert "found_action" in calls
    assert "not_found_action" in calls


def test_51_calls_inside_while_loop():
    code = '''
def poll_status():
    while check_status():
        wait_interval()
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "poll.py")
    calls = symbols[0].outgoing_calls
    assert "check_status" in calls
    assert "wait_interval" in calls


def test_52_calls_inside_match_case():
    code = '''
def route_event(event):
    match event.type():
        case "click":
            handle_click(event)
        case "key":
            handle_key(event)
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "pattern.py")
    calls = symbols[0].outgoing_calls
    assert "event.type" in calls
    assert "handle_click" in calls
    assert "handle_key" in calls


def test_53_calls_inside_ternary_expression():
    code = '''
def compute_choice(flag):
    return branch_a() if eval_cond() else branch_b()
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "ternary.py")
    calls = symbols[0].outgoing_calls
    assert "branch_a" in calls
    assert "eval_cond" in calls
    assert "branch_b" in calls


def test_54_calls_inside_assert_statement():
    code = '''
def validate_state(obj):
    assert check_invariant(obj), format_error(obj)
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "asserts.py")
    calls = symbols[0].outgoing_calls
    assert "check_invariant" in calls
    assert "format_error" in calls


def test_55_calls_inside_raise_statement():
    code = '''
def trigger_error():
    raise ServiceException(build_error_details())
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "raise_err.py")
    calls = symbols[0].outgoing_calls
    assert "ServiceException" in calls
    assert "build_error_details" in calls


def test_56_calls_inside_return_statement():
    code = '''
def transform_and_return(raw):
    return finalize(encrypt(sanitize(raw)))
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "nest_ret.py")
    calls = symbols[0].outgoing_calls
    assert "finalize" in calls
    assert "encrypt" in calls
    assert "sanitize" in calls


# ============================================================================
# CATEGORY D: Expression Calls, Dotted Chains & F-Strings (Tests 57 to 64)
# ============================================================================

def test_57_calls_inside_fstrings():
    code = '''
def generate_report(user):
    return f"User {format_name(user)} logged in at {get_timestamp()}"
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "fstring.py")
    calls = symbols[0].outgoing_calls
    assert "format_name" in calls
    assert "get_timestamp" in calls


def test_58_calls_inside_dict_keys_and_values():
    code = '''
def build_map():
    return {gen_key(): compute_val(), "const": fetch_static()}
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "dict_calls.py")
    calls = symbols[0].outgoing_calls
    assert "gen_key" in calls
    assert "compute_val" in calls
    assert "fetch_static" in calls


def test_59_calls_inside_set_literals():
    code = '''
def collect_unique():
    return {calc_a(), calc_b(), calc_c()}
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "set_calls.py")
    calls = symbols[0].outgoing_calls
    assert "calc_a" in calls
    assert "calc_b" in calls
    assert "calc_c" in calls


def test_60_super_method_calls():
    code = '''
class CustomList(list):
    def append(self, item):
        validate(item)
        super().append(item)
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "custom_list.py")
    method_sym = symbols[1]
    calls = method_sym.outgoing_calls
    assert "validate" in calls
    assert "super().append" in calls


def test_61_deep_dotted_call_chain():
    code = '''
def deep_chain():
    cluster.node.storage.volume.attach()
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "deep_dot.py")
    assert "cluster.node.storage.volume.attach" in symbols[0].outgoing_calls


def test_62_calls_with_keyword_arguments():
    code = '''
def invoke_rpc():
    client.call(endpoint=get_url(), timeout=get_timeout(), retry=True)
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "kw_call.py")
    calls = symbols[0].outgoing_calls
    assert "client.call" in calls
    assert "get_url" in calls
    assert "get_timeout" in calls


def test_63_multiple_calls_single_line():
    code = '''
def multi_line_single():
    init(); start(); wait()
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "multi_single.py")
    calls = symbols[0].outgoing_calls
    assert "init" in calls
    assert "start" in calls
    assert "wait" in calls


def test_64_deeply_nested_call_arguments():
    code = '''
def nested_calls():
    first(second(third(fourth())))
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "nested_args.py")
    calls = symbols[0].outgoing_calls
    assert "first" in calls
    assert "second" in calls
    assert "third" in calls
    assert "fourth" in calls


# ============================================================================
# CATEGORY E: Advanced Routing & Web Framework Edge Cases (Tests 65 to 70)
# ============================================================================

def test_65_route_api_route_methods_param():
    code = '''
@app.api_route("/users", methods=["GET", "POST"])
def manage_users():
    pass
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "api_route.py")
    assert len(symbols) == 1
    assert symbols[0].kind == SymbolKind.ROUTE
    assert symbols[0].name == "manage_users"


def test_66_blueprint_and_router_variants():
    code = '''
@bp.route("/auth/login")
def login(): pass

@blueprint.get("/metrics")
def metrics(): pass
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "bp_routes.py")
    assert len(symbols) == 2
    assert symbols[0].kind == SymbolKind.ROUTE
    assert symbols[1].kind == SymbolKind.ROUTE


def test_67_websocket_endpoints():
    code = '''
@app.websocket("/live-feed")
async def live_feed(ws):
    await ws.accept()
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "ws.py")
    assert len(symbols) == 1
    assert symbols[0].kind == SymbolKind.ROUTE
    assert symbols[0].name == "live_feed"


def test_68_http_methods_route_recognition():
    code = '''
@app.put("/items/1")
def update_item(): pass

@app.delete("/items/1")
def delete_item(): pass

@app.patch("/items/1")
def patch_item(): pass

@app.options("/items/1")
def options_item(): pass

@app.head("/items/1")
def head_item(): pass
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "http_verbs.py")
    assert len(symbols) == 5
    for s in symbols:
        assert s.kind == SymbolKind.ROUTE


def test_69_route_method_inside_controller_class():
    code = '''
class OrderController:
    @router.post("/checkout")
    def checkout(self, payload: dict):
        return self.service.process(payload)
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "controller.py")
    assert len(symbols) == 2
    cls_sym, method_sym = symbols
    assert cls_sym.kind == SymbolKind.CLASS
    assert method_sym.kind == SymbolKind.ROUTE
    assert method_sym.qualified_name == "OrderController.checkout"


def test_70_non_routing_decorator_with_args():
    code = '''
@retry(times=3, delay=1.0)
@lru_cache(maxsize=128)
def cached_lookup(key):
    return fetch(key)
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "cached.py")
    assert len(symbols) == 1
    assert symbols[0].kind == SymbolKind.FUNCTION
    assert symbols[0].kind != SymbolKind.ROUTE


# ============================================================================
# CATEGORY F: Module Variables, Annotations & Assignments (Tests 71 to 74)
# ============================================================================

def test_71_chained_multiple_assignment():
    code = '''
ALPHA = BETA = GAMMA = "CONSTANT"
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "chained_assign.py")
    names = [s.name for s in symbols]
    assert "ALPHA" in names
    assert "BETA" in names
    assert "GAMMA" in names


def test_72_annotated_variable_without_value():
    code = '''
CACHE_REGISTRY: dict[str, int]
DATABASE_URL: str = "postgres://..."
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "ann_no_val.py")
    names = [s.name for s in symbols]
    assert "CACHE_REGISTRY" in names
    assert "DATABASE_URL" in names


def test_73_local_variables_in_class_body_vs_module():
    code = '''
GLOBAL_SEED = 12345

class Settings:
    SCHEMA_VERSION = 2
    PAGE_SIZE = 50
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "settings.py")
    # Only GLOBAL_SEED and Settings should be recorded at module level
    vars_only = [s for s in symbols if s.kind == SymbolKind.VARIABLE]
    assert len(vars_only) == 1
    assert vars_only[0].name == "GLOBAL_SEED"


def test_74_function_with_global_and_nonlocal():
    code = '''
GLOBAL_TOTAL = 0

def update_counter():
    global GLOBAL_TOTAL
    GLOBAL_TOTAL = calculate_sum()
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "scope_mutation.py")
    vars_only = [s for s in symbols if s.kind == SymbolKind.VARIABLE]
    # GLOBAL_TOTAL should only be captured once as the module-level variable
    assert len(vars_only) == 1
    assert vars_only[0].name == "GLOBAL_TOTAL"


# ============================================================================
# CATEGORY G: Advanced Imports, Multiline & Relative Syntax (Tests 75 to 78)
# ============================================================================

def test_75_multiline_parenthesized_imports():
    code = '''
from os.path import (
    exists,
    join as path_join,
    dirname,
)
'''
    parser = PythonAstParser()
    _, imports = parser.parse_code(code, "multi_import.py")
    assert len(imports) == 1
    imp = imports[0]
    assert imp.source_module == "os.path"
    assert imp.imported_names == ["exists", "join", "dirname"]
    assert imp.alias_map == {"path_join": "join"}


def test_76_deep_relative_imports():
    code = '''
from ....core.engine import Engine as CoreEngine
from ...common import utils
'''
    parser = PythonAstParser()
    _, imports = parser.parse_code(code, "deep_rel.py")
    assert len(imports) == 2
    assert imports[0].source_module == "....core.engine"
    assert imports[0].alias_map == {"CoreEngine": "Engine"}
    assert imports[1].source_module == "...common"


def test_77_future_annotations_import():
    code = '''
from __future__ import annotations
import typing
'''
    parser = PythonAstParser()
    _, imports = parser.parse_code(code, "future.py")
    assert len(imports) == 2
    assert imports[0].source_module == "__future__"
    assert imports[0].imported_names == ["annotations"]


def test_78_duplicate_and_repeated_imports():
    code = '''
import os
from math import sqrt
import os
from math import sqrt as math_sqrt
'''
    parser = PythonAstParser()
    _, imports = parser.parse_code(code, "dupes.py")
    assert len(imports) == 4
    assert imports[0].source_module == "os"
    assert imports[2].source_module == "os"
    assert imports[3].alias_map == {"math_sqrt": "sqrt"}


# ============================================================================
# CATEGORY H: Docstrings, Comments, Line Boundaries & Simulation (Tests 79 to 80)
# ============================================================================

def test_79_function_with_only_docstring():
    code = '''
def docstring_only():
    """This function has no pass statement; docstring is the only statement."""
'''
    parser = PythonAstParser()
    symbols, _ = parser.parse_code(code, "doc_only.py")
    assert len(symbols) == 1
    assert symbols[0].name == "docstring_only"
    assert "This function has no pass statement" in symbols[0].docstring


def test_80_comprehensive_full_file_simulation():
    code = '''
from __future__ import annotations
from typing import Optional
from app.entities.user import User as UserModel
import logging

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT: int = 60

class BaseManager:
    """Base manager docstring."""
    def setup(self):
        logger.info("Setting up")

class UserManager(BaseManager):
    """Manages user state and transitions."""
    def __init__(self, db_conn):
        self.db = db_conn

    def register_user(self, email: str, role: Optional[str] = None) -> UserModel:
        logger.info(f"Registering user: {email}")
        user = UserModel(email=email, role=role)
        self.db.save(user)
        notify_user(email)
        return user

@app.post("/api/v1/users/register")
async def api_register_user(payload: dict):
    manager = UserManager(get_db())
    return manager.register_user(payload["email"])
'''
    parser = PythonAstParser()
    symbols, imports = parser.parse_code(code, "app/api/users.py")

    # Verify imports
    assert len(imports) == 4
    assert imports[2].source_module == "app.entities.user"
    assert imports[2].alias_map == {"UserModel": "User"}

    # Verify extracted symbols
    names = [s.name for s in symbols]
    assert "logger" in names
    assert "DEFAULT_TIMEOUT" in names
    assert "BaseManager" in names
    assert "setup" in names
    assert "UserManager" in names
    assert "__init__" in names
    assert "register_user" in names
    assert "api_register_user" in names

    # Verify route endpoint
    route_sym = [s for s in symbols if s.name == "api_register_user"][0]
    assert route_sym.kind == SymbolKind.ROUTE
    assert "UserManager" in route_sym.outgoing_calls
    assert "get_db" in route_sym.outgoing_calls

    # Verify method qualified names
    reg_sym = [s for s in symbols if s.name == "register_user"][0]
    assert reg_sym.kind == SymbolKind.METHOD
    assert reg_sym.qualified_name == "UserManager.register_user"
    assert reg_sym.symbol_id == "app/api/users.py:UserManager.register_user"
    assert "logger.info" in reg_sym.outgoing_calls
    assert "UserModel" in reg_sym.outgoing_calls
    assert "self.db.save" in reg_sym.outgoing_calls
    assert "notify_user" in reg_sym.outgoing_calls

    # Verify every single symbol satisfies invariants
    for s in symbols:
        assert s.line_start >= 1
        assert s.line_end >= s.line_start
        assert s.symbol_id == f"app/api/users.py:{s.qualified_name}"


if __name__ == "__main__":
    print("Running PythonAstParser tests...")
    test_01_protocol_conformance()
    test_02_empty_and_whitespace_sources()
    test_03_standalone_function()
    test_04_async_function()
    test_05_class_and_methods()
    test_06_route_endpoints_detection()
    test_07_non_route_decorators_not_flagged_as_route()
    test_08_nested_function_call_isolation()
    test_09_outgoing_call_expressions_types()
    test_10_standard_and_aliased_imports()
    test_11_from_imports_and_relative_dots()
    test_12_module_level_variables_and_constants()
    test_13_nested_classes()
    test_14_syntax_error_propagates()
    test_15_source_slicing_fidelity()
    test_16_multi_decorator_route_endpoint()
    test_17_multiple_classes_with_identical_method_names()
    test_18_calls_inside_comprehensions()
    test_19_relative_import_without_module_name()
    test_20_star_import()
    test_21_lambda_calls_do_not_crash()
    test_22_class_with_class_decorator()
    test_23_tuple_assignment_variables()
    test_24_multi_line_docstring_extraction()
    test_25_async_methods_inside_class()
    test_26_empty_function_and_class_bodies()
    test_27_chained_method_invocations()
    test_28_comments_only_file()
    test_29_route_without_parentheses()
    test_30_symbol_invariants_pass_on_all_extracted_symbols()

    # Category A: Tests 31 to 38
    test_31_single_inheritance_class()
    test_32_multiple_inheritance_class()
    test_33_metaclass_declaration()
    test_34_dunder_magic_methods()
    test_35_property_getter_and_setter()
    test_36_abstract_methods()
    test_37_three_level_nested_classes()
    test_38_class_inside_function_factory()

    # Category B: Tests 39 to 46
    test_39_positional_only_parameters()
    test_40_keyword_only_parameters()
    test_41_variadic_args_and_kwargs()
    test_42_default_arg_with_function_call()
    test_43_generator_with_yield()
    test_44_async_generator_with_yield()
    test_45_yield_from_generator()
    test_46_complex_generic_type_annotations()

    # Category C: Tests 47 to 56
    test_47_calls_inside_with_statement()
    test_48_calls_inside_async_with()
    test_49_calls_inside_try_except_else_finally()
    test_50_calls_inside_for_else()
    test_51_calls_inside_while_loop()
    test_52_calls_inside_match_case()
    test_53_calls_inside_ternary_expression()
    test_54_calls_inside_assert_statement()
    test_55_calls_inside_raise_statement()
    test_56_calls_inside_return_statement()

    # Category D: Tests 57 to 64
    test_57_calls_inside_fstrings()
    test_58_calls_inside_dict_keys_and_values()
    test_59_calls_inside_set_literals()
    test_60_super_method_calls()
    test_61_deep_dotted_call_chain()
    test_62_calls_with_keyword_arguments()
    test_63_multiple_calls_single_line()
    test_64_deeply_nested_call_arguments()

    # Category E: Tests 65 to 70
    test_65_route_api_route_methods_param()
    test_66_blueprint_and_router_variants()
    test_67_websocket_endpoints()
    test_68_http_methods_route_recognition()
    test_69_route_method_inside_controller_class()
    test_70_non_routing_decorator_with_args()

    # Category F: Tests 71 to 74
    test_71_chained_multiple_assignment()
    test_72_annotated_variable_without_value()
    test_73_local_variables_in_class_body_vs_module()
    test_74_function_with_global_and_nonlocal()

    # Category G: Tests 75 to 78
    test_75_multiline_parenthesized_imports()
    test_76_deep_relative_imports()
    test_77_future_annotations_import()
    test_78_duplicate_and_repeated_imports()

    # Category H: Tests 79 to 80
    test_79_function_with_only_docstring()
    test_80_comprehensive_full_file_simulation()

    print("🎉 ALL 80 PythonAstParser test cases passed successfully!")
