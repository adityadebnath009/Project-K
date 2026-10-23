"""
deconstructor_service.py - High-level Feature Deconstruction Application Orchestrator.
Orchestrates repository scanning, AST symbol parsing, static call graph resolution,
entry point discovery, vertical slice extraction, and architectural blueprint generation.
"""
from pathlib import Path
from typing import Sequence
from app.schemas.slice import CodeSymbol, EntryPoint, ImportStatement, SymbolKind, VerticalSlice
from app.slicing.ast_parser import PythonAstParser
from app.slicing.blueprint import BlueprintGenerator
from app.slicing.call_graph import CallGraphTracer
from app.slicing.extractor import SliceExtractor
from app.slicing.interfaces import CallGraphResolver, EntryPointFinder, FeatureSlicer, SymbolParser
from app.slicing.locator import EntryPointLocator

# Directories that should be skipped during repository scanning
IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    "build",
    "dist",
    ".eggs",
    "tests",
    "test",
}


class FeatureDeconstructorService:
    """
    Facade service orchestrating end-to-end vertical feature extraction.
    Follows Clean Architecture: delegates low-level AST, graph traversal, and blueprint
    rendering to pluggable protocol implementations.
    """

    def __init__(
        self,
        parser: SymbolParser | None = None,
        call_graph_resolver: CallGraphResolver | None = None,
        entry_point_finder: EntryPointFinder | None = None,
        slicer: FeatureSlicer | None = None,
        blueprint_generator: BlueprintGenerator | None = None,
    ) -> None:
        self.parser = parser or PythonAstParser()
        self.call_graph_resolver = call_graph_resolver or CallGraphTracer()
        self.entry_point_finder = entry_point_finder or EntryPointLocator()
        self.slicer = slicer or SliceExtractor()
        self.blueprint_generator = blueprint_generator or BlueprintGenerator()

    def scan_repository(
        self, repo_path: Path | str
    ) -> tuple[list[CodeSymbol], dict[str, list[ImportStatement]]]:
        """
        Recursively scans a repository directory for Python files and parses
        all CodeSymbols and ImportStatements.

        Args:
            repo_path: Directory path of the target repository.

        Returns:
            A tuple of (all parsed symbols, imports_by_file dictionary).
        """
        root = Path(repo_path).resolve()
        if not root.exists() or not root.is_dir():
            raise FileNotFoundError(f"Target repository path does not exist or is not a directory: {root}")

        all_symbols: list[CodeSymbol] = []
        imports_by_file: dict[str, list[ImportStatement]] = {}

        for py_file in root.rglob("*.py"):
            # Skip ignored directories
            if any(part in IGNORED_DIRS for part in py_file.parts):
                continue

            rel_path = str(py_file.relative_to(root))
            try:
                code = py_file.read_text(encoding="utf-8")
                symbols, imports = self.parser.parse_code(code, rel_path)
                all_symbols.extend(symbols)
                imports_by_file[rel_path] = imports
            except Exception:
                # Tolerate unparseable syntax or encoding glitches in legacy repos
                continue

        return all_symbols, imports_by_file

    def list_entry_points(
        self,
        repo_path: Path | str,
        query: str | None = None,
    ) -> list[EntryPoint]:
        """
        Scans a repository and returns all discovered entry points ranked by query relevance.
        """
        symbols, _ = self.scan_repository(repo_path)
        return self.entry_point_finder.find_entry_points(symbols, query=query)

    def deconstruct_feature(
        self,
        repo_path: Path | str,
        feature_name: str,
        query: str | None = None,
        entry_point_id: str | None = None,
    ) -> tuple[VerticalSlice, str]:
        """
        Executes end-to-end deconstruction of a feature from a target codebase.

        Args:
            repo_path: Local path to the cloned repository.
            feature_name: Logical title for the extracted slice (e.g. 'User Authentication').
            query: Natural language or route search query (e.g. 'login', '/users/login').
            entry_point_id: Exact symbol_id override to skip discovery.

        Returns:
            A tuple of:
            - VerticalSlice: The extracted, self-contained slice model.
            - str: Comprehensive Markdown architectural blueprint with Mermaid call graph.
        """
        symbols, imports_by_file = self.scan_repository(repo_path)
        if not symbols:
            raise ValueError(f"No Python symbols could be parsed from repository: {repo_path}")

        # 1. Resolve call graph and forward adjacency
        call_edges, forward_graph = self.call_graph_resolver.build_call_graph(
            symbols=symbols,
            imports_by_file=imports_by_file,
        )

        # 2. Identify the target entry point
        entry_point: EntryPoint | None = None

        if entry_point_id:
            # Explicit coordinate provided
            matched = next((s for s in symbols if s.symbol_id == entry_point_id), None)
            if not matched:
                raise ValueError(f"Specified entry_point_id '{entry_point_id}' was not found in parsed symbols.")
            entry_type = "http_route" if matched.kind == SymbolKind.ROUTE else "public_api"
            entry_point = EntryPoint(symbol=matched, entry_type=entry_type)
        else:
            search_query = query or feature_name
            ranked_entry_points = self.entry_point_finder.find_entry_points(symbols, query=search_query)
            if not ranked_entry_points:
                raise ValueError(
                    f"No entry points found in '{repo_path}' matching query '{search_query}'. "
                    f"Try specifying an explicit entry_point_id."
                )
            entry_point = ranked_entry_points[0]

        # 3. Extract vertical slice via graph reachability
        vertical_slice = self.slicer.extract_slice(
            feature_name=feature_name,
            entry_point_id=entry_point.symbol.symbol_id,
            symbols=symbols,
            forward_graph=forward_graph,
            call_edges=call_edges,
        )

        # Ensure rich entry point metadata is attached
        vertical_slice.entry_points = [entry_point]

        # 4. Generate architectural blueprint document
        blueprint_md = self.blueprint_generator.generate_markdown(vertical_slice)

        return vertical_slice, blueprint_md
