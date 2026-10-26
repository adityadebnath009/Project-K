"""
ast_parser.py - Concrete Python AST parser implementing the SymbolParser protocol.
Uses Python's standard library `ast` module (zero external dependencies).
"""
import ast
from app.schemas.slice import CodeSymbol, ImportStatement, SymbolKind
from app.slicing.interfaces import SymbolParser

ROUTING_DECORATOR_NAMES = {
    "get",
    "post",
    "put",
    "delete",
    "patch",
    "options",
    "head",
    "route",
    "api_route",
    "websocket",
}


def _extract_callee_name(func_node: ast.AST) -> str | None:
    """Recursively reconstructs dot-separated callee expression (e.g. 'self.repo.save')."""
    if isinstance(func_node, ast.Name):
        return func_node.id
    if isinstance(func_node, ast.Attribute):
        value_name = _extract_callee_name(func_node.value)
        return f"{value_name}.{func_node.attr}" if value_name else func_node.attr
    if isinstance(func_node, ast.Call):
        base_name = _extract_callee_name(func_node.func)
        return f"{base_name}()" if base_name else None
    return None


class _CallExtractor(ast.NodeVisitor):
    """
    Visitor that traverses an AST block to extract outgoing call expressions.
    Intentionally halts traversal at nested function or class boundaries
    so nested calls are not falsely attributed to the outer scope.
    """

    def __init__(self) -> None:
        self.calls: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        callee = _extract_callee_name(node.func)
        if callee:
            self.calls.append(callee)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Halt traversal at nested function boundaries to prevent scope leakage
        pass

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        # Halt traversal at nested async function boundaries to prevent scope leakage
        pass

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        # Do not descend into nested classes
        pass


class _AstSymbolVisitor(ast.NodeVisitor):
    """Internal AST visitor that walks a Python module and collects symbols and imports."""

    def __init__(self, source_code: str, file_path: str) -> None:
        self.source_code = source_code
        self.file_path = file_path
        self.source_lines = source_code.splitlines()
        self.symbols: list[CodeSymbol] = []
        self.imports: list[ImportStatement] = []
        self.current_class: str | None = None
        self.current_function: str | None = None

    def _extract_source(self, line_start: int, line_end: int) -> str:
        """Extracts source text slice by 1-indexed line numbers."""
        start_idx = max(0, line_start - 1)
        end_idx = max(start_idx + 1, line_end)
        return "\n".join(self.source_lines[start_idx:end_idx])

    def _is_route(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        """Detects if a function is decorated with a web framework route decorator."""
        for dec in node.decorator_list:
            # Matches @app.get("/..."), @router.post("/...")
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                if dec.func.attr.lower() in ROUTING_DECORATOR_NAMES:
                    return True
            # Matches @app.get (without parentheses)
            elif isinstance(dec, ast.Attribute):
                if dec.attr.lower() in ROUTING_DECORATOR_NAMES:
                    return True
            # Matches @route("/...")
            elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
                if dec.func.id.lower() in ROUTING_DECORATOR_NAMES:
                    return True
        return False

    def _extract_outgoing_calls(self, node: ast.AST) -> list[str]:
        """Extracts all non-nested outgoing call expressions from an AST block."""
        extractor = _CallExtractor()
        for stmt in getattr(node, "body", []):
            extractor.visit(stmt)
        return extractor.calls

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        name = node.name
        qualified_name = f"{self.current_class}.{name}" if self.current_class else name
        raw_start = min([d.lineno for d in node.decorator_list] + [node.lineno])
        line_start = max(1, raw_start)
        line_end = max(line_start, node.end_lineno or line_start)

        docstring = ast.get_docstring(node)
        source_snippet = self._extract_source(line_start, line_end)
        outgoing_calls = self._extract_outgoing_calls(node)

        symbol = CodeSymbol(
            name=name,
            qualified_name=qualified_name,
            kind=SymbolKind.CLASS,
            file_path=self.file_path,
            line_start=line_start,
            line_end=line_end,
            docstring=docstring,
            source_code=source_snippet,
            outgoing_calls=outgoing_calls,
        )
        self.symbols.append(symbol)

        # Push class scope for inner methods/classes
        old_class = self.current_class
        self.current_class = qualified_name
        self.generic_visit(node)
        self.current_class = old_class

    def _handle_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        name = node.name
        qualified_name = f"{self.current_class}.{name}" if self.current_class else name
        raw_start = min([d.lineno for d in node.decorator_list] + [node.lineno])
        line_start = max(1, raw_start)
        line_end = max(line_start, node.end_lineno or line_start)

        # Classify symbol kind
        if self._is_route(node):
            kind = SymbolKind.ROUTE
        elif self.current_class is not None:
            kind = SymbolKind.METHOD
        else:
            kind = SymbolKind.FUNCTION

        docstring = ast.get_docstring(node)
        source_snippet = self._extract_source(line_start, line_end)
        outgoing_calls = self._extract_outgoing_calls(node)

        symbol = CodeSymbol(
            name=name,
            qualified_name=qualified_name,
            kind=kind,
            file_path=self.file_path,
            line_start=line_start,
            line_end=line_end,
            docstring=docstring,
            source_code=source_snippet,
            outgoing_calls=outgoing_calls,
        )
        self.symbols.append(symbol)

        # Descend to pick up any inner functions or classes
        old_function = self.current_function
        self.current_function = qualified_name
        self.generic_visit(node)
        self.current_function = old_function

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._handle_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._handle_function(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        # Capture module-level constants and variables (top-level scope only)
        if self.current_class is None and self.current_function is None:
            line_start = max(1, node.lineno)
            line_end = max(line_start, node.end_lineno or line_start)
            source_snippet = self._extract_source(line_start, line_end)

            names_to_add: list[str] = []
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names_to_add.append(target.id)
                elif isinstance(target, (ast.Tuple, ast.List)):
                    for elt in target.elts:
                        if isinstance(elt, ast.Name):
                            names_to_add.append(elt.id)

            for var_name in names_to_add:
                symbol = CodeSymbol(
                    name=var_name,
                    qualified_name=var_name,
                    kind=SymbolKind.VARIABLE,
                    file_path=self.file_path,
                    line_start=line_start,
                    line_end=line_end,
                    source_code=source_snippet,
                    outgoing_calls=self._extract_outgoing_calls(node),
                )
                self.symbols.append(symbol)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        # Capture annotated module-level variables (e.g. TIMEOUT: int = 30)
        if self.current_class is None and self.current_function is None and isinstance(node.target, ast.Name):
            line_start = max(1, node.lineno)
            line_end = max(line_start, node.end_lineno or line_start)
            source_snippet = self._extract_source(line_start, line_end)
            symbol = CodeSymbol(
                name=node.target.id,
                qualified_name=node.target.id,
                kind=SymbolKind.VARIABLE,
                file_path=self.file_path,
                line_start=line_start,
                line_end=line_end,
                source_code=source_snippet,
                outgoing_calls=self._extract_outgoing_calls(node),
            )
            self.symbols.append(symbol)
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            alias_map = {alias.asname: alias.name} if alias.asname else {}
            stmt = ImportStatement(
                source_module=alias.name,
                imported_names=[alias.name],
                alias_map=alias_map,
                is_from=False,
                line_number=node.lineno,
            )
            self.imports.append(stmt)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        prefix = "." * node.level if node.level else ""
        source_module = prefix + (node.module or "")
        imported_names = [alias.name for alias in node.names]
        alias_map = {alias.asname: alias.name for alias in node.names if alias.asname}

        stmt = ImportStatement(
            source_module=source_module,
            imported_names=imported_names,
            alias_map=alias_map,
            is_from=True,
            line_number=node.lineno,
        )
        self.imports.append(stmt)
        self.generic_visit(node)


class PythonAstParser:
    """
    Standard Python AST parser implementing SymbolParser.
    Parses Python source code strings into CodeSymbol and ImportStatement DTOs.
    """

    def parse_code(self, source_code: str, file_path: str) -> tuple[list[CodeSymbol], list[ImportStatement]]:
        """
        Parses source code into a list of CodeSymbol DTOs and ImportStatement DTOs.

        Args:
            source_code: The raw text of the source file.
            file_path: Relative path of the file.

        Returns:
            A tuple of (extracted symbols, extracted import statements).
        """
        if not source_code or not source_code.strip():
            return [], []

        tree = ast.parse(source_code, filename=file_path)
        visitor = _AstSymbolVisitor(source_code=source_code, file_path=file_path)
        visitor.visit(tree)
        return visitor.symbols, visitor.imports
