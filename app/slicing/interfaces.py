"""
interfaces.py - Abstract protocol definitions for code parsing and slicing.
Clean Architecture Persistence / Infrastructure abstraction layer.
"""
from typing import Protocol, runtime_checkable
from app.schemas.slice import CodeSymbol, EntryPoint, FunctionCall, ImportStatement, VerticalSlice


@runtime_checkable
class SymbolParser(Protocol):
    """
    Abstract interface for AST/syntax parsers.
    Decouples source language AST parsing from downstream CallGraphTracer and Slicer.
    """

    def parse_code(self, source_code: str, file_path: str) -> tuple[list[CodeSymbol], list[ImportStatement]]:
        """
        Parses source code into a list of CodeSymbol DTOs and ImportStatement DTOs.

        Args:
            source_code: The raw text of the source file.
            file_path: Relative path of the file (used for unique symbol_id coordination).

        Returns:
            A tuple of (extracted symbols, extracted import statements).
        """
        ...


@runtime_checkable
class CallGraphResolver(Protocol):
    """
    Abstract interface for call graph construction and symbol resolution.
    Decouples syntax parsing from dependency graph traversal.
    """

    def build_call_graph(
        self,
        symbols: list[CodeSymbol],
        imports_by_file: dict[str, list[ImportStatement]],
    ) -> tuple[list[FunctionCall], dict[str, set[str]]]:
        """
        Builds the resolved function call edges and forward adjacency graph.

        Args:
            symbols: All parsed CodeSymbol DTOs across the repository.
            imports_by_file: Mapping of file_path -> list of ImportStatement DTOs in that file.

        Returns:
            A tuple of:
            - list[FunctionCall]: All call edges with resolved_symbol_id populated when found.
            - dict[str, set[str]]: Directed adjacency graph (caller_symbol_id -> set of callee_symbol_ids).
        """
        ...


@runtime_checkable
class EntryPointFinder(Protocol):
    """
    Abstract interface for locating entry point routes and public APIs.
    """

    def find_entry_points(
        self,
        symbols: list[CodeSymbol],
        query: str | None = None,
    ) -> list[EntryPoint]:
        """
        Finds and ranks entry points across code symbols matching an optional query.
        """
        ...


@runtime_checkable
class FeatureSlicer(Protocol):
    """
    Abstract interface for vertical feature slice extraction.
    Performs reachability traversal from entry points and packages the minimal slice.
    """

    def extract_slice(
        self,
        feature_name: str,
        entry_point_id: str,
        symbols: list[CodeSymbol],
        forward_graph: dict[str, set[str]],
        call_edges: list[FunctionCall] | None = None,
    ) -> VerticalSlice:
        """
        Extracts a minimal self-contained VerticalSlice starting from an entry point.

        Args:
            feature_name: Logical name of the feature (e.g. 'User Login').
            entry_point_id: Canonical symbol_id of the entry route (e.g. 'app/api/auth.py:login').
            symbols: All parsed CodeSymbol DTOs across the repository.
            forward_graph: Directed adjacency list (caller_symbol_id -> set of callee_symbol_ids).
            call_edges: Optional full list of FunctionCall edges to filter.

        Returns:
            A minimal, self-contained VerticalSlice DTO.
        """
        ...
