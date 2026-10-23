"""
blueprint.py - Architectural blueprint generator.
Renders an extracted VerticalSlice into interactive Mermaid flowcharts
and comprehensive Markdown architectural specification documents.
"""
import re
from app.schemas.slice import SymbolKind, VerticalSlice


def _sanitize_mermaid_id(symbol_id: str) -> str:
    """Sanitizes symbol ID to be a valid Mermaid node identifier."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", symbol_id)


class BlueprintGenerator:
    """
    Transforms extracted VerticalSlice models into developer-ready architectural blueprints,
    Mermaid call graphs, and structural documentation.
    """

    def generate_mermaid(self, vertical_slice: VerticalSlice) -> str:
        """
        Generates a valid Mermaid flowchart TD diagram from the slice call graph.
        """
        lines = ["flowchart TD"]

        # 1. Define nodes (sorted deterministically by file and line start)
        symbol_map = {s.symbol_id: s for s in vertical_slice.symbols}
        sorted_symbols = sorted(vertical_slice.symbols, key=lambda s: (s.file_path, s.line_start))

        for symbol in sorted_symbols:
            node_id = _sanitize_mermaid_id(symbol.symbol_id)
            label = f"{symbol.qualified_name}"

            if symbol.kind == SymbolKind.ROUTE:
                # Stadium shape for HTTP Routes
                lines.append(f'    {node_id}(["🌐 Route: {label}"])')
            elif symbol.kind == SymbolKind.CLASS:
                # Hexagon / Distinct shape for Classes
                lines.append(f'    {node_id}{{"📦 Class: {label}"}}')
            elif symbol.kind == SymbolKind.METHOD:
                # Standard box for Methods
                lines.append(f'    {node_id}["⚙️ Method: {label}"]')
            else:
                # Rounded box for standalone Functions
                lines.append(f'    {node_id}["⚡ Function: {label}"]')

        # 2. Define edges from call_graph
        valid_symbol_ids = set(symbol_map.keys())
        added_edges: set[tuple[str, str]] = set()

        for edge in vertical_slice.call_graph:
            caller_id = edge.caller_symbol_id
            callee_id = edge.resolved_symbol_id

            if callee_id and caller_id in valid_symbol_ids and callee_id in valid_symbol_ids:
                edge_tuple = (caller_id, callee_id)
                if edge_tuple not in added_edges:
                    caller_node = _sanitize_mermaid_id(caller_id)
                    callee_node = _sanitize_mermaid_id(callee_id)
                    lines.append(f"    {caller_node} --> {callee_node}")
                    added_edges.add(edge_tuple)

        # Style classes for clean readability
        lines.append("")
        lines.append("    classDef routeNode fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#0369a1;")
        lines.append("    classDef classNode fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#92400e;")
        lines.append("    classDef default fill:#f8fafc,stroke:#64748b,stroke-width:1px,color:#334155;")

        for symbol in vertical_slice.symbols:
            node_id = _sanitize_mermaid_id(symbol.symbol_id)
            if symbol.kind == SymbolKind.ROUTE:
                lines.append(f"    class {node_id} routeNode;")
            elif symbol.kind == SymbolKind.CLASS:
                lines.append(f"    class {node_id} classNode;")

        return "\n".join(lines)

    def generate_markdown(self, vertical_slice: VerticalSlice) -> str:
        """
        Generates a full Markdown architectural blueprint document.
        """
        lines = [
            f"# Feature Specification Blueprint: {vertical_slice.feature_name}",
            "",
            "> Architectural deconstruction and vertical slice extracted by **FeatureForge**.",
            "",
            "## 1. Executive Summary",
            "",
            f"- **Target Feature:** `{vertical_slice.feature_name}`",
            f"- **Total Extracted Symbols:** `{len(vertical_slice.symbols)}`",
            f"- **Files Involved ({len(vertical_slice.files_involved)}):**",
        ]

        for file_path in vertical_slice.files_involved:
            lines.append(f"  - `{file_path}`")

        loc = vertical_slice.total_lines_of_code or vertical_slice.calculate_unique_source_lines()
        lines.append(f"- **Covered Source Lines:** `{loc}` lines of production code")
        lines.append("")

        # 2. Entry Points
        if vertical_slice.entry_points:
            lines.append("## 2. Feature Entry Points")
            lines.append("")
            lines.append("| Entry Type | HTTP Method | Route / Coordinate | Source Location |")
            lines.append("| :--- | :--- | :--- | :--- |")
            for ep in vertical_slice.entry_points:
                method = ep.http_method or "N/A"
                route = ep.route_path or ep.symbol.qualified_name
                loc_ref = f"`{ep.symbol.file_path}:{ep.symbol.line_start}`"
                lines.append(f"| `{ep.entry_type}` | `{method}` | `{route}` | {loc_ref} |")
            lines.append("")

        # 3. Call Graph Architecture
        lines.append("## 3. Architecture & Dependency Flow")
        lines.append("")
        lines.append("```mermaid")
        lines.append(self.generate_mermaid(vertical_slice))
        lines.append("```")
        lines.append("")

        # 4. Symbol Catalog
        lines.append("## 4. Extracted Symbol Catalog")
        lines.append("")
        lines.append("| Symbol ID | Kind | Lines | Docstring |")
        lines.append("| :--- | :--- | :--- | :--- |")
        sorted_symbols = sorted(vertical_slice.symbols, key=lambda s: (s.file_path, s.line_start))
        for s in sorted_symbols:
            doc = (s.docstring or "").strip().split("\n")[0] if s.docstring else "-"
            # Escape pipes for markdown table
            doc = doc.replace("|", "\\|")
            lines.append(f"| `{s.symbol_id}` | `{s.kind.value}` | L{s.line_start}-L{s.line_end} | {doc} |")
        lines.append("")

        # 5. Clean Extracted Source Code
        lines.append("## 5. Extracted Source Code")
        lines.append("")
        symbols_by_file: dict[str, list] = {}
        for s in vertical_slice.symbols:
            symbols_by_file.setdefault(s.file_path, []).append(s)

        for file_path, syms in sorted(symbols_by_file.items()):
            lines.append(f"### File: `{file_path}`")
            lines.append("")
            # Sort symbols by starting line
            syms_sorted = sorted(syms, key=lambda sym: sym.line_start)
            for sym in syms_sorted:
                lines.append(f"#### `{sym.qualified_name}` (`{sym.kind.value}` - Lines {sym.line_start} to {sym.line_end})")
                lines.append("```python")
                lines.append(sym.source_code)
                lines.append("```")
                lines.append("")

        return "\n".join(lines)
