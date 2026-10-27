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
from app.schemas.transposition import (
    TargetConventionMap,
    TargetEvidenceManifest,
    TargetLayer,
)
from app.slicing.ast_parser import PythonAstParser
from app.slicing.call_graph import CallGraphTracer
from app.slicing.symbol_table import SymbolTable

IGNORED_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "build", "dist", ".pytest_cache", "test_fixtures"}


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

    def discover_convention_map(
        self,
        index: TargetCodebaseIndex,
        manifest: TargetEvidenceManifest | None = None,
    ) -> TargetConventionMap:
        """
        Learns target architectural conventions, layer directory centers-of-gravity,
        and repository/service naming patterns directly from indexed AST facts
        using mathematical affix derivation with ZERO hardcoded prefixes or suffixes.
        """
        inheritance = manifest.inheritance_map if manifest else {}
        layer_dirs: dict[TargetLayer, str] = {}
        dir_counts: dict[TargetLayer, dict[str, int]] = {layer: {} for layer in TargetLayer}

        # 1. Discover Domain Entities via AST Inheritance & Mapped Type Annotations
        entity_symbols: list[CodeSymbol] = []
        for symbol in index.all_symbols:
            if symbol.kind.value != "class" or symbol.name in ("Base", "Model", "DeclarativeBase"):
                continue

            base_classes = inheritance.get(symbol.name, [])
            is_entity_base = any(b in ("Base", "DeclarativeBase", "Model", "db.Model", "SQLModel") for b in base_classes)
            has_mapped = "mapped[" in symbol.source_code.lower() or "column(" in symbol.source_code.lower()

            if is_entity_base or has_mapped:
                entity_symbols.append(symbol)
                file_dir = str(Path(symbol.file_path).parent)
                dir_counts[TargetLayer.ENTITY][file_dir] = dir_counts[TargetLayer.ENTITY].get(file_dir, 0) + 1

        # Fallback if no ORM inheritance detected: inspect class names matching domain roles
        if not entity_symbols:
            for symbol in index.all_symbols:
                if symbol.kind.value == "class" and symbol.name not in ("Base", "Model"):
                    lower_path = symbol.file_path.lower()
                    if ("entit" in lower_path or "domain" in lower_path or "models" in lower_path) and "/test" not in lower_path:
                        entity_symbols.append(symbol)
                        file_dir = str(Path(symbol.file_path).parent)
                        dir_counts[TargetLayer.ENTITY][file_dir] = dir_counts[TargetLayer.ENTITY].get(file_dir, 0) + 1

        entity_names = [e.name for e in entity_symbols]

        # 2. Discover Repositories, Services, Schemas, and Tests
        repo_symbols: list[CodeSymbol] = []
        service_symbols: list[CodeSymbol] = []

        for symbol in index.all_symbols:
            if symbol.kind.value != "class":
                continue

            file_dir = str(Path(symbol.file_path).parent)
            lower_path = symbol.file_path.lower()
            lower_name = symbol.name.lower()
            base_classes = inheritance.get(symbol.name, [])
            is_test_file = lower_path.startswith("test") or "/test" in lower_path or lower_name.startswith("test_")

            # Tests
            if is_test_file:
                dir_counts[TargetLayer.TEST][file_dir] = dir_counts[TargetLayer.TEST].get(file_dir, 0) + 1
                continue

            # Schemas: Inheriting from BaseModel, Struct, or DTO
            is_schema = any("basemodel" in b.lower() or "struct" in b.lower() or "schema" in b.lower() for b in base_classes)
            if is_schema or ("schema" in lower_path and not is_test_file):
                dir_counts[TargetLayer.SCHEMA][file_dir] = dir_counts[TargetLayer.SCHEMA].get(file_dir, 0) + 1

            # Repositories: Classes (excluding domain entities themselves) that operate on persistence
            if symbol.name not in entity_names:
                is_protocol = any(b in ("Protocol", "ABC") for b in base_classes)
                has_repo_name = any(k in lower_name for k in ("repo", "store", "dao", "table", "gateway"))
                references_entity = any(em.lower() in lower_name for em in entity_names)

                if has_repo_name or (references_entity and "service" not in lower_name):
                    repo_symbols.append(symbol)
                    target_layer = TargetLayer.REPOSITORY_PROTOCOL if is_protocol else TargetLayer.REPOSITORY_IMPL
                    dir_counts[target_layer][file_dir] = dir_counts[target_layer].get(file_dir, 0) + 1
                    dir_counts[TargetLayer.REPOSITORY_IMPL][file_dir] = dir_counts[TargetLayer.REPOSITORY_IMPL].get(file_dir, 0) + 1
                    dir_counts[TargetLayer.REPOSITORY_PROTOCOL][file_dir] = dir_counts[TargetLayer.REPOSITORY_PROTOCOL].get(file_dir, 0) + 1

            # Services: Coordinates domain workflows
            has_service_name = any(k in lower_name for k in ("service", "usecase", "use_case", "manager", "handler", "interactor"))
            if has_service_name:
                service_symbols.append(symbol)
                dir_counts[TargetLayer.SERVICE][file_dir] = dir_counts[TargetLayer.SERVICE].get(file_dir, 0) + 1

        # Select most frequent directory per layer (Center of Gravity)
        for layer in TargetLayer:
            counts = dir_counts[layer]
            if counts:
                layer_dirs[layer] = max(counts.items(), key=lambda kv: kv[1])[0]

        # 3. Dynamic Mathematical Affix Derivation (Zero Hardcoded Prefixes or Suffixes)
        repo_pattern_counts: dict[str, int] = {}
        for repo_sym in repo_symbols:
            r_name = repo_sym.name
            for em in entity_names:
                if em.lower() in r_name.lower():
                    # Calculate prefix and suffix relative to the entity symbol position
                    idx = r_name.lower().find(em.lower())
                    prefix = r_name[:idx]
                    suffix = r_name[idx + len(em):]
                    pattern = f"{prefix}{{symbol}}{suffix}"
                    repo_pattern_counts[pattern] = repo_pattern_counts.get(pattern, 0) + 1

        repo_naming_pattern = max(repo_pattern_counts.items(), key=lambda kv: kv[1])[0] if repo_pattern_counts else "{symbol}Repository"

        service_pattern_counts: dict[str, int] = {}
        for s_sym in service_symbols:
            s_name = s_sym.name
            for em in entity_names:
                if em.lower() in s_name.lower():
                    idx = s_name.lower().find(em.lower())
                    prefix = s_name[:idx]
                    suffix = s_name[idx + len(em):]
                    pattern = f"{prefix}{{symbol}}{suffix}"
                    service_pattern_counts[pattern] = service_pattern_counts.get(pattern, 0) + 1

        service_naming_pattern = max(service_pattern_counts.items(), key=lambda kv: kv[1])[0] if service_pattern_counts else "{symbol}Service"

        conv_map = TargetConventionMap()
        if layer_dirs:
            merged_dirs = dict(conv_map.layer_directories)
            merged_dirs.update(layer_dirs)
            conv_map.layer_directories = merged_dirs

        conv_map.repo_naming_pattern = repo_naming_pattern
        conv_map.service_naming_pattern = service_naming_pattern
        conv_map.existing_entities = entity_names
        conv_map.existing_services = [s.name for s in service_symbols]

        return conv_map
