"""
app/transposition/target_indexer.py - Phase 7A: Target Codebase Structural Indexer.

Implements Layers 1 & 2 of Target Intelligence:
- Layer 1: Structural Indexing (Symbols, files, imports, calls, manifests, parse errors).
- Layer 2: Evidence Manifest Extraction (Typed relationships: INHERITS, CALLS, DECORATORS).

Extracts ground-truth facts with ZERO framework guesses.
"""
import ast
import tomllib
from pathlib import Path
from dataclasses import dataclass

from app.schemas.slice import CodeSymbol, FunctionCall, ImportStatement
from app.schemas.transposition import TargetEvidenceManifest
from app.slicing.ast_parser import PythonAstParser
from app.slicing.call_graph import CallGraphTracer
from app.slicing.symbol_table import SymbolTable

IGNORED_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "build", "dist", ".pytest_cache"}


@dataclass
class TargetCodebaseIndex:
    """The structural ground-truth index of the target codebase."""
    target_root: Path
    all_symbols: list[CodeSymbol]
    imports_by_file: dict[str, list[ImportStatement]]
    call_edges: list[FunctionCall]
    forward_graph: dict[str, set[str]]
    symbol_table: SymbolTable
    parse_errors: dict[str, str]


class TargetRepositoryIndexer:
    """
    Scans a target repository to extract pure structural facts and
    constructs a TargetEvidenceManifest for the LLM Target Architect.
    """

    def __init__(
        self,
        parser: PythonAstParser | None = None,
        tracer: CallGraphTracer | None = None,
    ) -> None:
        self.parser = parser or PythonAstParser()
        self.tracer = tracer or CallGraphTracer()

    def index_repository(self, target_root: str | Path) -> tuple[TargetCodebaseIndex, TargetEvidenceManifest]:
        """
        Scans, parses, and produces the structural index and evidence manifest.

        Args:
            target_root: Path to the target repository.

        Returns:
            A tuple of (TargetCodebaseIndex, TargetEvidenceManifest).
        """
        root = Path(target_root).resolve()
        if not root.exists() or not root.is_dir():
            raise FileNotFoundError(f"Target repository root does not exist: {root}")

        all_symbols: list[CodeSymbol] = []
        imports_by_file: dict[str, list[ImportStatement]] = {}
        parse_errors: dict[str, str] = {}
        py_files_scanned = 0

        inheritance_map: dict[str, list[str]] = {}
        decorators_by_symbol: dict[str, list[str]] = {}

        # 1. Structural Scan & Parse
        for py_file in root.rglob("*.py"):
            rel_path = str(py_file.relative_to(root))
            rel_parts = py_file.relative_to(root).parts

            # Relative path safety check: only ignore directories within the target root
            if any(part in IGNORED_DIRS for part in rel_parts):
                continue

            py_files_scanned += 1

            try:
                code = py_file.read_text(encoding="utf-8")
                symbols, imports = self.parser.parse_code(code, rel_path)
                all_symbols.extend(symbols)
                imports_by_file[rel_path] = imports

                # Extract AST facts (inheritance & decorators) directly from the tree
                self._extract_ast_facts(code, rel_path, inheritance_map, decorators_by_symbol)

            except Exception as e:
                # Never silently swallow errors; record file and exception details
                parse_errors[rel_path] = f"{type(e).__name__}: {str(e)}"

        # 2. Build Call Graph & Symbol Table
        all_calls, forward_graph = self.tracer.build_call_graph(all_symbols, imports_by_file)
        symbol_table = SymbolTable(all_symbols)

        codebase_index = TargetCodebaseIndex(
            target_root=root,
            all_symbols=all_symbols,
            imports_by_file=imports_by_file,
            call_edges=all_calls,
            forward_graph=forward_graph,
            symbol_table=symbol_table,
            parse_errors=parse_errors,
        )

        # 3. Build Evidence Manifest (Layer 2)
        manifest = self._build_evidence_manifest(
            root=root,
            py_files_scanned=py_files_scanned,
            all_symbols=all_symbols,
            imports_by_file=imports_by_file,
            all_calls=all_calls,
            inheritance_map=inheritance_map,
            decorators_by_symbol=decorators_by_symbol,
            parse_errors=parse_errors,
        )

        return codebase_index, manifest

    def _extract_ast_facts(
        self,
        code: str,
        rel_path: str,
        inheritance_map: dict[str, list[str]],
        decorators_by_symbol: dict[str, list[str]],
    ) -> None:
        """Collects verified AST facts: class base inheritance and function decorators."""
        try:
            tree = ast.parse(code)
        except Exception:
            return

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = []
                for b in node.bases:
                    if isinstance(b, ast.Name):
                        bases.append(b.id)
                    elif isinstance(b, ast.Attribute):
                        bases.append(f"{ast.unparse(b.value)}.{b.attr}")
                inheritance_map[f"{rel_path}:{node.name}"] = bases

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                decorators = [ast.unparse(d) for d in node.decorator_list]
                if decorators:
                    decorators_by_symbol[f"{rel_path}:{node.name}"] = decorators

    def _build_evidence_manifest(
        self,
        root: Path,
        py_files_scanned: int,
        all_symbols: list[CodeSymbol],
        imports_by_file: dict[str, list[ImportStatement]],
        all_calls: list[FunctionCall],
        inheritance_map: dict[str, list[str]],
        decorators_by_symbol: dict[str, list[str]],
        parse_errors: dict[str, str],
    ) -> TargetEvidenceManifest:
        """Constructs the pure factual manifest with zero framework assumptions."""
        # Inspect Manifests (pyproject.toml, requirements.txt, setup.py)
        # Check current root; if not found, check parent directory (e.g. if root is src/ or app/)
        manifest_dirs = [root]
        if not any((root / m).exists() for m in ["pyproject.toml", "requirements.txt", "setup.py"]):
            if (root.parent / ".git").exists() or any((root.parent / m).exists() for m in ["pyproject.toml", "requirements.txt", "setup.py"]):
                manifest_dirs.append(root.parent)

        declared_dependencies: list[str] = []
        for m_dir in manifest_dirs:
            for manifest_name in ["pyproject.toml", "requirements.txt", "setup.py"]:
                m_path = m_dir / manifest_name
                if m_path.exists():
                    declared_dependencies.extend(self._extract_dependencies_from_manifest(m_path))

        # Flatten imports: file -> list of imported module strings
        flattened_imports: dict[str, list[str]] = {
            f: [imp.source_module for imp in imps] for f, imps in imports_by_file.items()
        }

        # Calculate graph resolution metrics
        total_calls = len(all_calls)
        resolved_calls = len([c for c in all_calls if c.resolved_symbol_id is not None])
        unresolved_calls = total_calls - resolved_calls
        resolution_rate = (resolved_calls / total_calls) if total_calls > 0 else 1.0

        return TargetEvidenceManifest(
            target_root=str(root),
            total_files_scanned=py_files_scanned,
            files_indexed_count=py_files_scanned - len(parse_errors),
            parse_error_count=len(parse_errors),
            parse_errors=parse_errors,
            declared_dependencies=sorted(list(set(declared_dependencies))),
            inheritance_map=inheritance_map,
            decorators_by_symbol=decorators_by_symbol,
            imports_by_file=flattened_imports,
            total_call_edges=total_calls,
            resolved_internal_calls=resolved_calls,
            unresolved_calls=unresolved_calls,
            call_resolution_rate=round(resolution_rate, 4),
        )

    def _extract_dependencies_from_manifest(self, m_path: Path) -> list[str]:
        """Extracts declared package dependencies from pyproject.toml, requirements.txt, or setup.py."""
        deps: list[str] = []
        try:
            text = m_path.read_text(encoding="utf-8")
        except Exception:
            return deps

        if m_path.name == "pyproject.toml":
            try:
                data = tomllib.loads(text)
                # 1. PEP 621 dependencies: [project] dependencies = [...]
                project = data.get("project", {})
                if "dependencies" in project and isinstance(project["dependencies"], list):
                    deps.extend([str(d).strip() for d in project["dependencies"] if str(d).strip()])

                # 2. Poetry dependencies: [tool.poetry.dependencies]
                tool_poetry = data.get("tool", {}).get("poetry", {})
                poetry_deps = tool_poetry.get("dependencies", {})
                if isinstance(poetry_deps, dict):
                    for pkg, spec in poetry_deps.items():
                        if pkg.lower() == "python":
                            continue
                        if isinstance(spec, str):
                            deps.append(f"{pkg} {spec}".strip())
                        elif isinstance(spec, dict) and "version" in spec:
                            deps.append(f"{pkg} {spec['version']}".strip())
                        else:
                            deps.append(str(pkg).strip())

                if deps:
                    return deps
            except Exception:
                pass

        # Fallback / requirements.txt / setup.py line parsing
        for line in text.splitlines():
            cleaned = line.strip().split("#")[0].strip()
            if cleaned and not cleaned.startswith("[") and not cleaned.startswith("-"):
                deps.append(cleaned)

        return deps
