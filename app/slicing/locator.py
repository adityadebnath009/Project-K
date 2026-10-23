"""
locator.py - Entry point discovery and ranking.
Implements the EntryPointFinder protocol to locate HTTP routes, CLI commands,
and public entry-point functions across codebases.
"""
import re
from typing import Sequence
from app.schemas.slice import CodeSymbol, EntryPoint, SymbolKind
from app.slicing.interfaces import EntryPointFinder

# Regex pattern to extract HTTP method and path from standard route decorators
# Handles @router.post("/users/login"), @app.get('/items'), @route("/data", methods=["POST"])
_ROUTE_DECORATOR_PATTERN = re.compile(
    r"@[\w\.]*?(get|post|put|delete|patch|options|head|route|api_route|websocket|websocket_route)\s*\(\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
_HTTP_METHOD_PATTERN = re.compile(
    r"methods\s*=\s*\[\s*['\"]([a-zA-Z]+)['\"]",
    re.IGNORECASE,
)


class EntryPointLocator(EntryPointFinder):
    """
    Finds and ranks entry points across parsed code symbols.
    Identifies HTTP routes (FastAPI, Flask, Starlette) and public functions/methods.
    """

    def find_entry_points(
        self,
        symbols: Sequence[CodeSymbol],
        query: str | None = None,
    ) -> list[EntryPoint]:
        """
        Locates entry points from a collection of code symbols, ranked by query relevance.

        Args:
            symbols: Parsed CodeSymbol DTOs.
            query: Optional search term (e.g. 'login', '/users/login', 'create_user').

        Returns:
            List of EntryPoint DTOs ordered by relevance score descending.
        """
        candidates: list[EntryPoint] = []

        for symbol in symbols:
            # 1. Routes are primary candidates
            if symbol.kind == SymbolKind.ROUTE:
                route_path, http_method = self._extract_route_metadata(symbol.source_code)
                candidates.append(
                    EntryPoint(
                        symbol=symbol,
                        entry_type="http_route",
                        route_path=route_path,
                        http_method=http_method,
                    )
                )
            # 2. Public functions (non-private, top-level) are secondary entry points
            elif symbol.kind == SymbolKind.FUNCTION and not symbol.name.startswith("_"):
                entry_type = "cli_command" if "@" in symbol.source_code and "command" in symbol.source_code.lower() else "public_api"
                candidates.append(
                    EntryPoint(
                        symbol=symbol,
                        entry_type=entry_type,
                        route_path=None,
                        http_method=None,
                    )
                )

        if not query or not query.strip():
            # When no query is given, sort routes first, then public APIs by file and line
            return sorted(
                candidates,
                key=lambda ep: (
                    0 if ep.entry_type == "http_route" else 1,
                    ep.symbol.file_path,
                    ep.symbol.line_start,
                ),
            )

        # Rank candidates by relevance score against the query
        scored_candidates: list[tuple[float, EntryPoint]] = []
        normalized_query = query.strip().lower()

        for candidate in candidates:
            score = self._compute_relevance_score(candidate, normalized_query)
            if score > 0.0:
                scored_candidates.append((score, candidate))

        # Sort by score descending, then symbol_id ascending for deterministic output
        scored_candidates.sort(key=lambda item: (-item[0], item[1].symbol.symbol_id))
        return [candidate for _, candidate in scored_candidates]

    def _extract_route_metadata(self, source_code: str) -> tuple[str | None, str | None]:
        """Extracts route path and HTTP method from decorator syntax."""
        match = _ROUTE_DECORATOR_PATTERN.search(source_code)
        if not match:
            return None, None

        raw_method, path = match.group(1).upper(), match.group(2)
        if raw_method in {"ROUTE", "API_ROUTE"}:
            # Check for explicit methods=['POST'] argument
            method_match = _HTTP_METHOD_PATTERN.search(source_code)
            http_method = method_match.group(1).upper() if method_match else "GET"
        else:
            http_method = raw_method

        return path, http_method

    def _compute_relevance_score(self, entry_point: EntryPoint, query: str) -> float:
        """
        Calculates a relevance score for ranking entry points against a user query.
        """
        score = 0.0
        symbol = entry_point.symbol
        name_lower = symbol.name.lower()
        path_lower = (entry_point.route_path or "").lower()
        qualified_lower = symbol.qualified_name.lower()
        file_lower = symbol.file_path.lower()
        doc_lower = (symbol.docstring or "").lower()

        # Exact matches
        if name_lower == query:
            score += 100.0
        elif path_lower == query or path_lower.strip("/") == query.strip("/"):
            score += 95.0

        # Substring in name
        if query in name_lower:
            score += 60.0
        # Substring in route path
        if path_lower and query in path_lower:
            score += 55.0
        # Substring in qualified name
        if query in qualified_lower:
            score += 30.0
        # Substring in file path
        if query in file_lower:
            score += 20.0
        # Substring in docstring
        if doc_lower and query in doc_lower:
            score += 15.0

        # Routes receive a domain bonus
        if entry_point.entry_type == "http_route" and score > 0:
            score += 10.0

        return score
