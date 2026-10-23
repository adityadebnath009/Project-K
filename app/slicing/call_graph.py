"""
call_graph.py - Builds the directed dependency graph and resolves symbol calls.
Implements the CallGraphResolver protocol using SymbolTable and a 4-stage waterfall.
"""
from collections import defaultdict
from app.schemas.slice import CodeSymbol, FunctionCall, ImportStatement, SymbolKind
from app.slicing.interfaces import CallGraphResolver
from app.slicing.symbol_table import SymbolTable


class CallGraphTracer:
    """
    Constructs a directed call graph across repository symbols.
    Resolves raw syntactic calls to canonical symbol_id coordinates.
    """

    def build_call_graph(
        self,
        symbols: list[CodeSymbol],
        imports_by_file: dict[str, list[ImportStatement]],
    ) -> tuple[list[FunctionCall], dict[str, set[str]]]:
        """
        Builds the resolved function call edges and forward adjacency graph.

        Returns:
            - list[FunctionCall]: Detailed call edges.
            - dict[str, set[str]]: Adjacency list (caller_symbol_id -> set of callee_symbol_ids).
        """
        table = SymbolTable(symbols)
        all_calls: list[FunctionCall] = []
        forward_graph: dict[str, set[str]] = defaultdict(set)

        for caller in symbols:
            # Classes and pure variables don't initiate runtime call edges directly
            if caller.kind == SymbolKind.VARIABLE:
                continue

            file_imports = imports_by_file.get(caller.file_path, [])

            for raw_callee in caller.outgoing_calls:
                resolved_id = self._resolve_callee(
                    caller=caller,
                    raw_callee=raw_callee,
                    file_imports=file_imports,
                    table=table,
                )

                call_edge = FunctionCall(
                    caller_symbol_id=caller.symbol_id,
                    raw_callee=raw_callee,
                    resolved_symbol_id=resolved_id,
                    file_path=caller.file_path,
                    line_number=caller.line_start,
                )
                all_calls.append(call_edge)

                if resolved_id:
                    forward_graph[caller.symbol_id].add(resolved_id)

        return all_calls, dict(forward_graph)

    def _resolve_callee(
        self,
        caller: CodeSymbol,
        raw_callee: str,
        file_imports: list[ImportStatement],
        table: SymbolTable,
    ) -> str | None:
        """Resolves a raw callee string to a canonical symbol_id using the 4-stage waterfall."""
        clean_callee = raw_callee.replace("()", "")

        # -------------------------------------------------------------
        # STAGE 1: Local Scope (Same Class or Same File)
        # -------------------------------------------------------------
        # 1a. Call on 'self' within a class (e.g. self.calculate or self._helper)
        if clean_callee.startswith("self.") and "." in caller.qualified_name:
            caller_class = caller.qualified_name.rsplit(".", 1)[0]
            method_name = clean_callee.split(".", 1)[1]
            local_method = table.find_in_class(caller_class, method_name)
            if not local_method and "." in caller_class:
                # Check enclosing class if nested
                outer_class = caller_class.split(".")[0]
                local_method = table.find_in_class(outer_class, method_name)
            if local_method:
                return local_method.symbol_id

        # 1b. Direct call in the same file (e.g. validate_order)
        if "." not in clean_callee:
            local_sym = table.find_in_file(caller.file_path, clean_callee)
            if local_sym:
                return local_sym.symbol_id

        # 1c. Call on a class defined in the same file (e.g. Svc.run or OrderService.calculate)
        if "." in clean_callee and not clean_callee.startswith("self."):
            prefix, attr = clean_callee.split(".", 1)
            class_in_file = table.find_in_file(caller.file_path, prefix)
            if class_in_file and class_in_file.kind == SymbolKind.CLASS:
                method_in_class = table.find_in_class(prefix, attr) or table.lookup_by_id(f"{caller.file_path}:{prefix}.{attr}")
                if method_in_class:
                    return method_in_class.symbol_id

        # -------------------------------------------------------------
        # STAGE 2: Import-Aware Scope (from X import Y or import X)
        # -------------------------------------------------------------
        for imp in file_imports:
            # 2a. Direct imported module name (import setup_app -> setup_app())
            if not imp.is_from:
                if clean_callee == imp.source_module:
                    syms = table.find_by_name(clean_callee)
                    if syms:
                        return syms[0].symbol_id
                # 2b. Module attribute call (import auth_module -> auth_module.verify())
                if clean_callee.startswith(f"{imp.source_module}."):
                    fn_name = clean_callee.split(".", 1)[1]
                    mod_path = imp.source_module.replace(".", "/")
                    matching_syms = [s for s in table.find_by_name(fn_name) if mod_path in s.file_path]
                    if matching_syms:
                        return matching_syms[0].symbol_id
                    by_name = table.find_by_name(fn_name)
                    if by_name:
                        return by_name[0].symbol_id

            if imp.is_from:
                for name in imp.imported_names:
                    # Direct function call: from auth import hash_pwd -> hash_pwd()
                    if clean_callee == name:
                        syms = [s for s in table.find_by_name(name) if imp.source_module.replace(".", "/") in s.file_path]
                        if syms:
                            return syms[0].symbol_id
                        by_name = table.find_by_name(name)
                        if by_name:
                            return by_name[0].symbol_id

        # Method call on imported class (e.g. self.discount.calculate() or DiscountEngine.calculate())
        if "." in clean_callee:
            parts = clean_callee.split(".")
            method_part = parts[-1]
            receiver = parts[-2] if len(parts) >= 2 else ""

            # Pass 2a: High-confidence affinity match (receiver name aligns with imported class or alias)
            if receiver and receiver != "self":
                for imp in file_imports:
                    if imp.is_from:
                        for name in imp.imported_names:
                            # Receiver substring matches class name or alias
                            is_match = (
                                receiver.lower() in name.lower()
                                or name.lower().startswith(receiver.lower())
                                or imp.alias_map.get(receiver) == name
                            )
                            if is_match:
                                class_method = table.find_in_class(name, method_part)
                                if class_method:
                                    return class_method.symbol_id

            # Pass 2b: Fallback to any imported class implementing the method
            for imp in file_imports:
                if imp.is_from:
                    for name in imp.imported_names:
                        class_method = table.find_in_class(name, method_part)
                        if class_method:
                            return class_method.symbol_id

        # -------------------------------------------------------------
        # STAGE 3: Aliases (import X as Y or from X import Y as Z)
        # -------------------------------------------------------------
        for imp in file_imports:
            for alias, original in imp.alias_map.items():
                if clean_callee == alias:
                    syms = table.find_by_name(original)
                    if syms:
                        return syms[0].symbol_id
                if clean_callee.startswith(f"{alias}."):
                    suffix = clean_callee.split(".", 1)[1]
                    mod_path = imp.source_module.replace(".", "/")
                    matching = [s for s in table.find_by_name(suffix) if mod_path in s.file_path]
                    if matching:
                        return matching[0].symbol_id
                    syms = table.find_by_name(suffix)
                    if syms:
                        return syms[0].symbol_id

        # -------------------------------------------------------------
        # STAGE 4: Fallback to exact symbol matching in the index
        # -------------------------------------------------------------
        if "." not in clean_callee:
            matches = table.find_by_name(clean_callee)
            if len(matches) == 1:
                return matches[0].symbol_id

        return None