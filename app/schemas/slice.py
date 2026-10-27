from enum import Enum
from pydantic import BaseModel, Field, model_validator


class SymbolKind(str, Enum):
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    ROUTE = "route"
    VARIABLE = "variable"


class ImportStatement(BaseModel):
    """Represents an import statement in a source file."""
    source_module: str = Field(description="The module being imported from (e.g. 'app.services.calendar')")
    imported_names: list[str] = Field(default_factory=list, description="Specific names imported (e.g. ['SlotEngine'])")
    alias_map: dict[str, str] = Field(default_factory=dict, description="Alias mappings, e.g. {'Engine': 'SlotEngine'}")
    is_from: bool = Field(default=True, description="True if 'from x import y', False if 'import x'")
    line_number: int = Field(default=1)


class FunctionCall(BaseModel):
    """
    A directed edge in the call graph: caller invokes callee.
    Uses resolved_symbol_id to prevent name collisions across files/classes.
    """
    caller_symbol_id: str = Field(description="Unique ID of caller (e.g. 'app/services/order.py:OrderService.submit')")
    raw_callee: str = Field(description="Raw call expression in text (e.g. 'self.engine.calculate')")
    resolved_symbol_id: str | None = Field(
        default=None,
        description="Resolved unique symbol ID (e.g. 'app/services/engine.py:DiscountEngine.calculate')",
    )
    file_path: str = Field(description="Source file where the call occurs")
    line_number: int = Field(default=1)


class CodeSymbol(BaseModel):
    """
    A parsed unit of source code (Class, Function, Method).
    Identified uniquely by its symbol_id ('file_path:qualified_name').
    """
    symbol_id: str = Field(
        default="",
        description="Unique coordinate: 'file_path:qualified_name' (e.g. 'app/services/user.py:UserService.save')",
    )
    name: str = Field(description="Short identifier name (e.g. 'save')")
    qualified_name: str = Field(description="Class-scoped name (e.g. 'UserService.save')")
    kind: SymbolKind = Field(description="The kind of symbol")
    file_path: str = Field(description="Relative path of the source file")
    line_start: int = Field(description="Starting line number in source (>= 1)")
    line_end: int = Field(description="Ending line number in source")
    docstring: str | None = Field(default=None, description="Extracted docstring or documentation")
    source_code: str = Field(description="The exact raw source text of this symbol")
    outgoing_calls: list[str] = Field(
        default_factory=list,
        description="Raw syntactical call expressions found inside this symbol body before resolution",
    )

    @model_validator(mode="after")
    def validate_invariants(self) -> "CodeSymbol":
        # 1. Enforce line-range validity
        if self.line_start < 1:
            raise ValueError(f"line_start must be >= 1, got {self.line_start}")
        if self.line_end < self.line_start:
            raise ValueError(f"line_end ({self.line_end}) cannot be earlier than line_start ({self.line_start})")

        # 2. Guarantee consistent symbol_id convention: 'file_path:qualified_name'
        expected_id = f"{self.file_path}:{self.qualified_name}"
        if not self.symbol_id:
            self.symbol_id = expected_id
        elif self.symbol_id != expected_id:
            raise ValueError(f"symbol_id mismatch: expected '{expected_id}', got '{self.symbol_id}'")

        return self


class EntryPoint(BaseModel):
    """The root entry point where the feature execution begins."""
    symbol: CodeSymbol = Field(description="The underlying code symbol")
    entry_type: str = Field(default="http_route", description="Type: 'http_route', 'cli_command', or 'public_api'")
    route_path: str | None = Field(default=None, description="HTTP path if this is a route (e.g. '/api/v1/slots')")
    http_method: str | None = Field(default=None, description="HTTP method (e.g. 'POST', 'GET')")



class VerticalSlice(BaseModel):
    """
    The extracted vertical slice.
    Contains ONLY the code symbols and dependencies needed for the feature.
    """
    feature_name: str = Field(description="User-given or inferred name of the feature")
    entry_points: list[EntryPoint] = Field(default_factory=list, description="Entry points initiating this feature")
    symbols: list[CodeSymbol] = Field(default_factory=list, description="All connected functions, classes, and models")
    call_graph: list[FunctionCall] = Field(
        default_factory=list,
        description="The authoritative resolved directed graph edges",
    )
    files_involved: list[str] = Field(
        default_factory=list,
        description="Set of source files touched by this slice (auto-derived if omitted)",
    )
    total_lines_of_code: int | None = Field(
        default=None,
        description="Total unique covered source lines across all symbols (derived when None)",
    )


    @model_validator(mode="after")
    def sync_derived_fields(self) -> "VerticalSlice":
        # 1. Derive files_involved from symbols if omitted or empty
        if not self.files_involved and self.symbols:
            self.files_involved = sorted({s.file_path for s in self.symbols})

        # 2. Derive unique covered source lines when None
        if self.total_lines_of_code is None:
            self.calculate_unique_source_lines()

        return self

    def calculate_unique_source_lines(self) -> int:
        """Calculates total unique covered lines, preventing nested symbols from double-counting."""
        unique_lines: set[tuple[str, int]] = set()
        for s in self.symbols:
            for line_no in range(s.line_start, s.line_end + 1):
                unique_lines.add((s.file_path, line_no))
        self.total_lines_of_code = len(unique_lines)
        return self.total_lines_of_code

    def to_context_summary(self) -> str:
        """Renders the vertical slice into a concise markdown summary for prompts."""
        lines = [f"### [VERTICAL SLICE: {self.feature_name}]"]
        lines.append(f"- **Files Involved ({len(self.files_involved)})**: {', '.join(self.files_involved)}")
        lines.append(f"- **Covered Source Lines**: {self.total_lines_of_code or 0}")
        lines.append(f"- **Symbols ({len(self.symbols)})**:")
        for s in self.symbols:
            lines.append(f"  • `{s.kind.value}` **{s.symbol_id}** (L{s.line_start}-L{s.line_end})")
        return "\n".join(lines)