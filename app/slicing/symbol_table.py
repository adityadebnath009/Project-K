"""
symbol_table.py - In-memory multi-index registry for fast CodeSymbol resolution.
Used by CallGraphTracer to perform O(1) scope and symbol lookups across files.
"""
from collections import defaultdict

from app.schemas.slice import CodeSymbol, SymbolKind


class SymbolTable:
    """
    Multi-indexed repository of CodeSymbol instances across a repository.
    Enables O(1) lookup by:
    1. Exact coordinate symbol_id ('file_path:qualified_name')
    2. File path + symbol name
    3. Class name + method name
    4. Short identifier name
    """

    def __init__(self, symbols: list[CodeSymbol] | None = None) -> None:
        self._by_id: dict[str, CodeSymbol] = {}
        self._by_file: dict[str, dict[str, CodeSymbol]] = defaultdict(dict)
        self._by_class: dict[str, dict[str, CodeSymbol]] = defaultdict(dict)
        self._by_name: dict[str, list[CodeSymbol]] = defaultdict(list)

        if symbols:
            for s in symbols:
                self.register(s)

    def register(self, symbol: CodeSymbol) -> None:
        """Indexes a CodeSymbol across all lookup tables."""
        self._by_id[symbol.symbol_id] = symbol
        self._by_file[symbol.file_path][symbol.name] = symbol
        self._by_file[symbol.file_path][symbol.qualified_name] = symbol
        self._by_name[symbol.name].append(symbol)

        # If this is a method inside a class, index by (class_name, method_name)
        if symbol.kind in (SymbolKind.METHOD, SymbolKind.ROUTE) and "." in symbol.qualified_name:
            class_name, method_name = symbol.qualified_name.rsplit(".", 1)
            self._by_class[class_name][method_name] = symbol

        # If this is a class itself, index it by its class name
        if symbol.kind == SymbolKind.CLASS:
            self._by_class[symbol.name] = self._by_class.get(symbol.name, {})

    def lookup_by_id(self, symbol_id: str) -> CodeSymbol | None:
        """O(1) exact lookup by unique symbol_id."""
        return self._by_id.get(symbol_id)

    def find_in_file(self, file_path: str, name: str) -> CodeSymbol | None:
        """Finds a symbol by name declared within a specific file."""
        return self._by_file.get(file_path, {}).get(name)

    def find_in_class(self, class_name: str, method_name: str) -> CodeSymbol | None:
        """Finds a method inside a given class name."""
        return self._by_class.get(class_name, {}).get(method_name)

    def find_by_name(self, name: str) -> list[CodeSymbol]:
        """Finds all symbols across the repository matching a short identifier name."""
        return self._by_name.get(name, [])

    def all_symbols(self) -> list[CodeSymbol]:
        """Returns all indexed symbols."""
        return list(self._by_id.values())

    def __len__(self) -> int:
        return len(self._by_id)