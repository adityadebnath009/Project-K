"""
extractor.py - Vertical feature slice extractor.
Performs cycle-safe Breadth-First Search (BFS) reachability traversal
from entry points to extract minimal, self-contained vertical slices.
"""
from collections import deque

from app.schemas.slice import (
    CodeSymbol,
    EntryPoint,
    FunctionCall,
    SymbolKind,
    VerticalSlice,
)
from app.slicing.interfaces import FeatureSlicer
from app.slicing.symbol_table import SymbolTable


class SliceExtractor:
    """
    Extracts a self-contained VerticalSlice from a codebase starting from an entry point.
    Uses BFS graph reachability on the directed call graph.
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
        """
        table = SymbolTable(symbols)
        entry_symbol = table.lookup_by_id(entry_point_id)
        if not entry_symbol:
            raise ValueError(f"Entry point symbol '{entry_point_id}' not found in symbol table")

        # Determine entry point metadata
        entry_type = "http_route" if entry_symbol.kind == SymbolKind.ROUTE else "public_api"
        entry_point_dto = EntryPoint(
            symbol=entry_symbol,
            entry_type=entry_type,
        )

        # Cycle-Safe BFS Reachability Traversal
        visited_ids: set[str] = set()
        queue: deque[str] = deque([entry_point_id])
        reachable_symbols_dict: dict[str, CodeSymbol] = {}

        while queue:
            current_id = queue.popleft()
            if current_id in visited_ids:
                continue
            visited_ids.add(current_id)

            sym = table.lookup_by_id(current_id)
            if sym:
                reachable_symbols_dict[sym.symbol_id] = sym

                # Class Definition Preservation:
                # If this is a method or inner class, also include all ancestor Class symbols
                # so the transplanted code retains its full class hierarchy structure.
                if "." in sym.qualified_name:
                    parts = sym.qualified_name.split(".")
                    num_classes = len(parts) - 1 if sym.kind in (SymbolKind.METHOD, SymbolKind.ROUTE) else len(parts)
                    for i in range(1, num_classes + 1):
                        ancestor_name = ".".join(parts[:i])
                        parent_class = table.find_in_file(sym.file_path, ancestor_name) or table.lookup_by_id(f"{sym.file_path}:{ancestor_name}")
                        if parent_class and parent_class.symbol_id not in reachable_symbols_dict:
                            reachable_symbols_dict[parent_class.symbol_id] = parent_class

                # Enqueue all unvisited downstream callees
                for neighbor_id in forward_graph.get(current_id, set()):
                    if neighbor_id not in visited_ids:
                        queue.append(neighbor_id)

        # Filter call graph edges to only those connecting symbols within this slice
        slice_symbol_ids = set(reachable_symbols_dict.keys())
        filtered_call_edges: list[FunctionCall] = []
        if call_edges:
            for edge in call_edges:
                if edge.caller_symbol_id in slice_symbol_ids:  # noqa: SIM102
                    if edge.resolved_symbol_id in slice_symbol_ids or edge.resolved_symbol_id is None:
                        filtered_call_edges.append(edge)

        # Assemble and return the complete VerticalSlice
        # (total_lines_of_code and files_involved are automatically derived by VerticalSlice invariants)
        return VerticalSlice(
            feature_name=feature_name,
            entry_points=[entry_point_dto],
            symbols=list(reachable_symbols_dict.values()),
            call_graph=filtered_call_edges,
        )