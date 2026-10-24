"""
app/test/test_target_indexer_100.py - Master 100-Test Verification Suite for Phase 7A.
Tests TargetRepositoryIndexer, TargetCodebaseIndex, and TargetEvidenceManifest.
Zero external test runners required. Executes deterministically in milliseconds.
"""
import os
import shutil
import tempfile
from pathlib import Path

from app.transposition.target_indexer import (
   
    TargetRepositoryIndexer,
)


# Helper to build ephemeral test repositories
def _create_temp_repo(files: dict[str, str]) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="test_repo_7a_"))
    for rel_path, content in files.items():
        file_path = temp_dir / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
    return temp_dir


# ==============================================================================
# CATEGORY 1: Filesystem Discovery & Relative Path Boundaries (Tests 1 to 15)
# ==============================================================================

def test_01_single_file_indexing():
    repo = _create_temp_repo({"main.py": "def run(): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, manifest = indexer.index_repository(repo)
        assert len(idx.all_symbols) == 1
        assert manifest.total_files_scanned == 1
        assert manifest.files_indexed_count == 1
    finally:
        shutil.rmtree(repo)

def test_02_deeply_nested_files():
    repo = _create_temp_repo({"a/b/c/d/e/deep.py": "class Deep: pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, manifest = indexer.index_repository(repo)
        assert len(idx.all_symbols) == 1
        assert "a/b/c/d/e/deep.py:Deep" in [s.symbol_id for s in idx.all_symbols]
    finally:
        shutil.rmtree(repo)

def test_03_relative_git_dir_ignored():
    repo = _create_temp_repo({".git/hooks/pre-commit.py": "print('git')", "app.py": "x = 1"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, manifest = indexer.index_repository(repo)
        assert manifest.total_files_scanned == 1
        assert not any(".git" in s.file_path for s in idx.all_symbols)
    finally:
        shutil.rmtree(repo)

def test_04_relative_venv_ignored():
    repo = _create_temp_repo({".venv/lib/python/pkg.py": "x = 1", "server.py": "y = 2"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, manifest = indexer.index_repository(repo)
        assert manifest.total_files_scanned == 1
        assert not any(".venv" in s.file_path for s in idx.all_symbols)
    finally:
        shutil.rmtree(repo)

def test_05_ancestor_dir_name_collision_safe():
    # If the ancestor path has '.venv' or '.git', it must NOT filter out the target repo's own files!
    base_temp = Path(tempfile.mkdtemp(prefix="temp_.venv_ancestor_"))
    repo = base_temp / "target_repo"
    repo.mkdir(parents=True)
    (repo / "service.py").write_text("class MyService: pass", encoding="utf-8")
    try:
        indexer = TargetRepositoryIndexer()
        idx, manifest = indexer.index_repository(repo)
        assert manifest.total_files_scanned == 1
        assert len(idx.all_symbols) == 1
    finally:
        shutil.rmtree(base_temp)

def test_06_node_modules_ignored():
    repo = _create_temp_repo({"node_modules/script.py": "bad = 1", "main.py": "good = 1"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.total_files_scanned == 1
    finally:
        shutil.rmtree(repo)

def test_07_pycache_and_pytest_cache_ignored():
    repo = _create_temp_repo({"__pycache__/byte.py": "x = 1", ".pytest_cache/cache.py": "y = 1", "run.py": "z = 1"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.total_files_scanned == 1
    finally:
        shutil.rmtree(repo)

def test_08_non_existent_directory_raises():
    indexer = TargetRepositoryIndexer()
    try:
        indexer.index_repository("/non/existent/path/999999")
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        pass

def test_09_file_passed_instead_of_dir_raises():
    repo = _create_temp_repo({"file.txt": "hello"})
    try:
        indexer = TargetRepositoryIndexer()
        try:
            indexer.index_repository(repo / "file.txt")
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError:
            pass
    finally:
        shutil.rmtree(repo)

def test_10_empty_directory_handled():
    repo = _create_temp_repo({})
    try:
        indexer = TargetRepositoryIndexer()
        idx, manifest = indexer.index_repository(repo)
        assert manifest.total_files_scanned == 0
        assert manifest.files_indexed_count == 0
        assert len(idx.all_symbols) == 0
    finally:
        shutil.rmtree(repo)

def test_11_zero_py_files_handled():
    repo = _create_temp_repo({"readme.md": "# Docs", "config.json": "{}"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.total_files_scanned == 0
    finally:
        shutil.rmtree(repo)

def test_12_non_python_files_skipped_cleanly():
    repo = _create_temp_repo({"app.py": "a = 1", "data.csv": "1,2,3", "image.png": "PNG"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.total_files_scanned == 1
    finally:
        shutil.rmtree(repo)

def test_13_files_with_multiple_dots():
    repo = _create_temp_repo({"service.spec.impl.py": "def test_me(): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, manifest = indexer.index_repository(repo)
        assert manifest.total_files_scanned == 1
        assert "service.spec.impl.py:test_me" in [s.symbol_id for s in idx.all_symbols]
    finally:
        shutil.rmtree(repo)

def test_14_build_and_dist_dirs_ignored():
    repo = _create_temp_repo({"build/b.py": "b = 1", "dist/d.py": "d = 1", "ok.py": "ok = 1"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.total_files_scanned == 1
    finally:
        shutil.rmtree(repo)

def test_15_venv_directory_without_dot_ignored():
    repo = _create_temp_repo({"venv/site-packages/p.py": "x = 1", "app.py": "y = 1"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.total_files_scanned == 1
    finally:
        shutil.rmtree(repo)


# ==============================================================================
# CATEGORY 2: Parse Error Handling & Indexing Coverage (Tests 16 to 30)
# ==============================================================================

def test_16_syntax_error_file_recorded_in_parse_errors():
    repo = _create_temp_repo({"bad.py": "def broken_syntax( pass", "good.py": "def ok(): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, manifest = indexer.index_repository(repo)
        assert "bad.py" in manifest.parse_errors
        assert "SyntaxError" in manifest.parse_errors["bad.py"]
        assert manifest.parse_error_count == 1
        assert manifest.files_indexed_count == 1
    finally:
        shutil.rmtree(repo)

def test_17_valid_files_indexed_despite_corrupted_sibling():
    repo = _create_temp_repo({"a.py": "def f1(): pass", "b_bad.py": "for i in :", "c.py": "def f2(): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, manifest = indexer.index_repository(repo)
        assert len(idx.all_symbols) == 2
        assert manifest.parse_error_count == 1
        assert manifest.files_indexed_count == 2
    finally:
        shutil.rmtree(repo)

def test_18_all_corrupted_files_repo_handled():
    repo = _create_temp_repo({"err1.py": "class (:", "err2.py": "def :"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, manifest = indexer.index_repository(repo)
        assert manifest.parse_error_count == 2
        assert manifest.files_indexed_count == 0
        assert len(idx.all_symbols) == 0
    finally:
        shutil.rmtree(repo)

def test_19_empty_python_file_parses_without_error():
    repo = _create_temp_repo({"empty.py": ""})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.parse_error_count == 0
        assert manifest.files_indexed_count == 1
    finally:
        shutil.rmtree(repo)

def test_20_comment_only_python_file():
    repo = _create_temp_repo({"comments.py": "# Only comments\n# Line 2\n"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.parse_error_count == 0
        assert manifest.files_indexed_count == 1
    finally:
        shutil.rmtree(repo)

def test_21_docstring_only_file():
    repo = _create_temp_repo({"doc.py": '"""Module docstring only."""'})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.parse_error_count == 0
    finally:
        shutil.rmtree(repo)

def test_22_indentation_error_logged():
    repo = _create_temp_repo({"indent_err.py": "def f():\nprint('bad indent')"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert "indent_err.py" in manifest.parse_errors
        assert "IndentationError" in manifest.parse_errors["indent_err.py"]
    finally:
        shutil.rmtree(repo)

def test_23_unicode_strings_and_comments_parse_fine():
    repo = _create_temp_repo({"unicode.py": "# こんにちは 世界\nmsg = '🚀 FeatureForge 🌟'"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, manifest = indexer.index_repository(repo)
        assert manifest.parse_error_count == 0
        assert len(idx.all_symbols) == 1
    finally:
        shutil.rmtree(repo)

def test_24_crlf_windows_newlines_handled():
    repo = _create_temp_repo({"win.py": "def win():\r\n    return 42\r\n"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, manifest = indexer.index_repository(repo)
        assert manifest.parse_error_count == 0
        assert len(idx.all_symbols) == 1
    finally:
        shutil.rmtree(repo)

def test_25_extremely_long_source_line():
    repo = _create_temp_repo({"long.py": "long_str = '" + "x" * 10000 + "'"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.parse_error_count == 0
    finally:
        shutil.rmtree(repo)

def test_26_index_coverage_rate_formula():
    repo = _create_temp_repo({"ok1.py": "x=1", "ok2.py": "x=2", "ok3.py": "x=3", "bad.py": "def :"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.total_files_scanned == 4
        assert manifest.files_indexed_count == 3
        assert manifest.parse_error_count == 1
    finally:
        shutil.rmtree(repo)

def test_27_multiple_syntax_errors_recorded_uniquely():
    repo = _create_temp_repo({"errA.py": "1 = x", "errB.py": "def (:"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert len(manifest.parse_errors) == 2
        assert "errA.py" in manifest.parse_errors
        assert "errB.py" in manifest.parse_errors
    finally:
        shutil.rmtree(repo)

def test_28_corrupted_ast_in_subfolder():
    repo = _create_temp_repo({"sub/dir/bad.py": "class :"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert "sub/dir/bad.py" in manifest.parse_errors
    finally:
        shutil.rmtree(repo)

def test_29_parse_error_details_string():
    repo = _create_temp_repo({"syntax.py": "if True"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert "syntax.py" in manifest.parse_errors
        assert len(manifest.parse_errors["syntax.py"]) > 5
    finally:
        shutil.rmtree(repo)

def test_30_all_clean_files_zero_parse_errors():
    repo = _create_temp_repo({"a.py": "a=1", "b.py": "b=2"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.parse_error_count == 0
        assert manifest.parse_errors == {}
    finally:
        shutil.rmtree(repo)


# ==============================================================================
# CATEGORY 3: Manifest & Dependency Fact Extraction (Tests 31 to 45)
# ==============================================================================

def test_31_pyproject_toml_dependencies_extracted():
    repo = _create_temp_repo({
        "pyproject.toml": "dependencies = [\n    'fastapi>=0.100',\n    'sqlalchemy>=2.0'\n]",
        "app.py": "x = 1"
    })
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert any("fastapi" in d for d in manifest.declared_dependencies)
        assert any("sqlalchemy" in d for d in manifest.declared_dependencies)
    finally:
        shutil.rmtree(repo)

def test_32_requirements_txt_dependencies_extracted():
    repo = _create_temp_repo({
        "requirements.txt": "pydantic==2.5.0\npsycopg-binary==3.1.18\n",
        "main.py": "x = 1"
    })
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert "pydantic==2.5.0" in manifest.declared_dependencies
        assert "psycopg-binary==3.1.18" in manifest.declared_dependencies
    finally:
        shutil.rmtree(repo)

def test_33_requirements_txt_comments_stripped():
    repo = _create_temp_repo({
        "requirements.txt": "# This is a comment\nrequests>=2.0.0 # inline comment\n",
        "app.py": "x = 1"
    })
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert any("requests" in d for d in manifest.declared_dependencies)
        assert not any("#" in d for d in manifest.declared_dependencies)
    finally:
        shutil.rmtree(repo)

def test_34_requirements_flags_ignored():
    repo = _create_temp_repo({
        "requirements.txt": "-r base.txt\n-i https://pypi.org/simple\nalembic>=1.12\n",
        "app.py": "x = 1"
    })
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert any("alembic" in d for d in manifest.declared_dependencies)
        assert not any(d.startswith("-") for d in manifest.declared_dependencies)
    finally:
        shutil.rmtree(repo)

def test_35_setup_py_dependencies():
    repo = _create_temp_repo({
        "setup.py": "install_requires=[\n'httpx>=0.25.0'\n]",
        "client.py": "x = 1"
    })
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert any("httpx" in d for d in manifest.declared_dependencies)
    finally:
        shutil.rmtree(repo)

def test_36_missing_manifest_returns_empty_list():
    repo = _create_temp_repo({"app.py": "x = 1"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.declared_dependencies == []
    finally:
        shutil.rmtree(repo)

def test_37_dependencies_sorted_and_deduplicated():
    repo = _create_temp_repo({
        "requirements.txt": "b_pkg\na_pkg\nb_pkg\n",
        "main.py": "x = 1"
    })
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.declared_dependencies == ["a_pkg", "b_pkg"]
    finally:
        shutil.rmtree(repo)

def test_38_empty_manifest_file():
    repo = _create_temp_repo({"requirements.txt": "", "app.py": "x = 1"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.declared_dependencies == []
    finally:
        shutil.rmtree(repo)

def test_39_manifest_whitespace_stripped():
    repo = _create_temp_repo({
        "requirements.txt": "   redis>=4.0   \n\n\n   celery>=5.0   \n",
        "app.py": "x = 1"
    })
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert "redis>=4.0" in manifest.declared_dependencies
        assert "celery>=5.0" in manifest.declared_dependencies
    finally:
        shutil.rmtree(repo)

def test_40_both_pyproject_and_requirements_merged():
    repo = _create_temp_repo({
        "pyproject.toml": "'uvicorn>=0.20'",
        "requirements.txt": "fastapi>=0.100\n",
        "main.py": "x = 1"
    })
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert any("uvicorn" in d for d in manifest.declared_dependencies)
        assert any("fastapi" in d for d in manifest.declared_dependencies)
    finally:
        shutil.rmtree(repo)

def test_41_corrupted_manifest_skipped_gracefully():
    repo = _create_temp_repo({"requirements.txt": "\x00\x00\x00", "app.py": "x = 1"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        # Should not crash
        assert isinstance(manifest.declared_dependencies, list)
    finally:
        shutil.rmtree(repo)

def test_42_manifest_with_section_headers_ignored():
    repo = _create_temp_repo({
        "pyproject.toml": "[tool.poetry.dependencies]\npython = '^3.11'\ntiktoken = '^0.5'\n",
        "app.py": "x = 1"
    })
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert not any(d.startswith("[") for d in manifest.declared_dependencies)
        assert any("tiktoken" in d for d in manifest.declared_dependencies)
    finally:
        shutil.rmtree(repo)

def test_43_manifest_with_version_specifiers():
    repo = _create_temp_repo({"requirements.txt": "torch>=2.0,<3.0\n", "main.py": "x = 1"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert "torch>=2.0,<3.0" in manifest.declared_dependencies
    finally:
        shutil.rmtree(repo)

def test_44_manifest_with_extra_brackets():
    repo = _create_temp_repo({"requirements.txt": "psycopg[binary]>=3.0\n", "main.py": "x = 1"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert "psycopg[binary]>=3.0" in manifest.declared_dependencies
    finally:
        shutil.rmtree(repo)

def test_45_manifest_empty_lines_only():
    repo = _create_temp_repo({"requirements.txt": "\n\n   \n\n", "app.py": "x = 1"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.declared_dependencies == []
    finally:
        shutil.rmtree(repo)


# ==============================================================================
# CATEGORY 4: AST Inheritance & Class Hierarchy Facts (Tests 46 to 60)
# ==============================================================================

def test_46_single_base_inheritance():
    repo = _create_temp_repo({"models.py": "class User(Base): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.inheritance_map.get("models.py:User") == ["Base"]
    finally:
        shutil.rmtree(repo)

def test_47_multiple_base_inheritance():
    repo = _create_temp_repo({"worker.py": "class TaskWorker(BaseWorker, LoggingMixin): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.inheritance_map.get("worker.py:TaskWorker") == ["BaseWorker", "LoggingMixin"]
    finally:
        shutil.rmtree(repo)

def test_48_class_without_base():
    repo = _create_temp_repo({"util.py": "class SimpleHelper: pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.inheritance_map.get("util.py:SimpleHelper") == []
    finally:
        shutil.rmtree(repo)

def test_49_attribute_base_unparsed():
    repo = _create_temp_repo({"db.py": "class Entity(orm.DeclarativeBase): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.inheritance_map.get("db.py:Entity") == ["orm.DeclarativeBase"]
    finally:
        shutil.rmtree(repo)

def test_50_multi_part_attribute_base():
    repo = _create_temp_repo({"db.py": "class Record(sqlalchemy.orm.Base): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.inheritance_map.get("db.py:Record") == ["sqlalchemy.orm.Base"]
    finally:
        shutil.rmtree(repo)

def test_51_multiple_classes_in_same_file():
    repo = _create_temp_repo({"entities.py": "class User(Base): pass\nclass Order(Base): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.inheritance_map.get("entities.py:User") == ["Base"]
        assert manifest.inheritance_map.get("entities.py:Order") == ["Base"]
    finally:
        shutil.rmtree(repo)

def test_52_nested_class_inheritance():
    repo = _create_temp_repo({"outer.py": "class Outer:\n    class Inner(BaseInner): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert "Outer" in [k.split(":")[-1] for k in manifest.inheritance_map]
        assert "Inner" in [k.split(":")[-1] for k in manifest.inheritance_map]
    finally:
        shutil.rmtree(repo)

def test_53_protocol_inheritance():
    repo = _create_temp_repo({"interfaces.py": "class UserRepository(Protocol): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.inheritance_map.get("interfaces.py:UserRepository") == ["Protocol"]
    finally:
        shutil.rmtree(repo)

def test_54_abc_inheritance():
    repo = _create_temp_repo({"base.py": "class AbstractService(ABC): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.inheritance_map.get("base.py:AbstractService") == ["ABC"]
    finally:
        shutil.rmtree(repo)

def test_55_pydantic_base_model_inheritance():
    repo = _create_temp_repo({"dto.py": "class UserDTO(BaseModel): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.inheritance_map.get("dto.py:UserDTO") == ["BaseModel"]
    finally:
        shutil.rmtree(repo)

def test_56_built_in_dict_inheritance():
    repo = _create_temp_repo({"custom.py": "class CustomMap(dict): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.inheritance_map.get("custom.py:CustomMap") == ["dict"]
    finally:
        shutil.rmtree(repo)

def test_57_built_in_exception_inheritance():
    repo = _create_temp_repo({"err.py": "class NotFoundError(Exception): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.inheritance_map.get("err.py:NotFoundError") == ["Exception"]
    finally:
        shutil.rmtree(repo)

def test_58_subclass_inheriting_sibling_class():
    repo = _create_temp_repo({"hierarchy.py": "class Parent: pass\nclass Child(Parent): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.inheritance_map.get("hierarchy.py:Parent") == []
        assert manifest.inheritance_map.get("hierarchy.py:Child") == ["Parent"]
    finally:
        shutil.rmtree(repo)

def test_59_class_name_with_underscores():
    repo = _create_temp_repo({"internal.py": "class _PrivateHelper(Base): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.inheritance_map.get("internal.py:_PrivateHelper") == ["Base"]
    finally:
        shutil.rmtree(repo)

def test_60_three_level_class_hierarchy():
    repo = _create_temp_repo({"chain.py": "class A: pass\nclass B(A): pass\nclass C(B): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.inheritance_map.get("chain.py:A") == []
        assert manifest.inheritance_map.get("chain.py:B") == ["A"]
        assert manifest.inheritance_map.get("chain.py:C") == ["B"]
    finally:
        shutil.rmtree(repo)


# ==============================================================================
# CATEGORY 5: AST Decorators & Behavioral Annotations (Tests 61 to 75)
# ==============================================================================

def test_61_property_decorator():
    repo = _create_temp_repo({"model.py": "class User:\n    @property\n    def full_name(self): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert "property" in manifest.decorators_by_symbol.get("model.py:full_name", [])
    finally:
        shutil.rmtree(repo)

def test_62_staticmethod_decorator():
    repo = _create_temp_repo({"util.py": "class Calc:\n    @staticmethod\n    def add(a, b): return a + b"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert "staticmethod" in manifest.decorators_by_symbol.get("util.py:add", [])
    finally:
        shutil.rmtree(repo)

def test_63_classmethod_decorator():
    repo = _create_temp_repo({"factory.py": "class Builder:\n    @classmethod\n    def build(cls): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert "classmethod" in manifest.decorators_by_symbol.get("factory.py:build", [])
    finally:
        shutil.rmtree(repo)

def test_64_fastapi_route_decorator_call():
    repo = _create_temp_repo({"routes.py": "@router.post('/login')\ndef login(): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        decs = manifest.decorators_by_symbol.get("routes.py:login", [])
        assert any("router.post" in d for d in decs)
    finally:
        shutil.rmtree(repo)

def test_65_route_decorator_with_response_model():
    repo = _create_temp_repo({"api.py": "@app.get('/users', response_model=list[User])\ndef get_users(): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        decs = manifest.decorators_by_symbol.get("api.py:get_users", [])
        assert any("app.get" in d and "response_model" in d for d in decs)
    finally:
        shutil.rmtree(repo)

def test_66_class_decorator_dataclass():
    repo = _create_temp_repo({"state.py": "@dataclass\nclass Config: host: str"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert "dataclass" in manifest.decorators_by_symbol.get("state.py:Config", [])
    finally:
        shutil.rmtree(repo)

def test_67_class_decorator_with_arguments():
    repo = _create_temp_repo({"frozen.py": "@dataclass(frozen=True)\nclass Immutable: id: int"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        decs = manifest.decorators_by_symbol.get("frozen.py:Immutable", [])
        assert any("dataclass" in d and "frozen=True" in d for d in decs)
    finally:
        shutil.rmtree(repo)

def test_68_stacked_multiple_decorators():
    repo = _create_temp_repo({"stacked.py": "class S:\n    @auth_required\n    @cache(ttl=60)\n    def fetch(self): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        decs = manifest.decorators_by_symbol.get("stacked.py:fetch", [])
        assert len(decs) == 2
        assert "auth_required" in decs
        assert any("cache" in d for d in decs)
    finally:
        shutil.rmtree(repo)

def test_69_async_function_decorator():
    repo = _create_temp_repo({"async_f.py": "@timing_middleware\nasync def process(): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert "timing_middleware" in manifest.decorators_by_symbol.get("async_f.py:process", [])
    finally:
        shutil.rmtree(repo)

def test_70_flask_route_decorator():
    repo = _create_temp_repo({"flask_app.py": "@app.route('/health', methods=['GET'])\ndef health(): return 'ok'"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        decs = manifest.decorators_by_symbol.get("flask_app.py:health", [])
        assert any("app.route" in d for d in decs)
    finally:
        shutil.rmtree(repo)

def test_71_custom_transactional_decorator():
    repo = _create_temp_repo({"service.py": "@transactional(isolation='SERIALIZABLE')\ndef update_balance(): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        decs = manifest.decorators_by_symbol.get("service.py:update_balance", [])
        assert any("transactional" in d and "SERIALIZABLE" in d for d in decs)
    finally:
        shutil.rmtree(repo)

def test_72_decorator_without_parentheses():
    repo = _create_temp_repo({"clean.py": "@pure\ndef calculate(): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert "pure" in manifest.decorators_by_symbol.get("clean.py:calculate", [])
    finally:
        shutil.rmtree(repo)

def test_73_decorator_on_nested_function():
    repo = _create_temp_repo({"nest.py": "def outer():\n    @memoize\n    def inner(): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert "memoize" in manifest.decorators_by_symbol.get("nest.py:inner", [])
    finally:
        shutil.rmtree(repo)

def test_74_function_without_decorators_omitted():
    repo = _create_temp_repo({"plain.py": "def plain_func(): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert "plain.py:plain_func" not in manifest.decorators_by_symbol
    finally:
        shutil.rmtree(repo)

def test_75_pydantic_validator_decorator():
    repo = _create_temp_repo({"schema.py": "class Model:\n    @field_validator('email')\n    def check_email(cls, v): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        decs = manifest.decorators_by_symbol.get("schema.py:check_email", [])
        assert any("field_validator" in d for d in decs)
    finally:
        shutil.rmtree(repo)


# ==============================================================================
# CATEGORY 6: Import Relationships & Module Mapping (Tests 76 to 85)
# ==============================================================================

def test_76_standard_import():
    repo = _create_temp_repo({"main.py": "import math\nx = math.sqrt(4)"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert "math" in manifest.imports_by_file.get("main.py", [])
    finally:
        shutil.rmtree(repo)

def test_77_from_import():
    repo = _create_temp_repo({"main.py": "from os import path\nx = path.exists('/')"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert "os" in manifest.imports_by_file.get("main.py", [])
    finally:
        shutil.rmtree(repo)

def test_78_aliased_import():
    repo = _create_temp_repo({"main.py": "import numpy as np"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert "numpy" in manifest.imports_by_file.get("main.py", [])
    finally:
        shutil.rmtree(repo)

def test_79_relative_single_dot_import():
    repo = _create_temp_repo({"pkg/a.py": "from .b import worker", "pkg/b.py": "worker = 1"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        # Should record the module without crash
        assert len(manifest.imports_by_file.get("pkg/a.py", [])) >= 1
    finally:
        shutil.rmtree(repo)

def test_80_relative_double_dot_import():
    repo = _create_temp_repo({"pkg/sub/a.py": "from ..common import util", "pkg/common.py": "util = 1"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert len(manifest.imports_by_file.get("pkg/sub/a.py", [])) >= 1
    finally:
        shutil.rmtree(repo)

def test_81_multi_from_import():
    repo = _create_temp_repo({"app.py": "from typing import Any, Optional, Union"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert "typing" in manifest.imports_by_file.get("app.py", [])
    finally:
        shutil.rmtree(repo)

def test_82_star_import():
    repo = _create_temp_repo({"app.py": "from math import *"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert "math" in manifest.imports_by_file.get("app.py", [])
    finally:
        shutil.rmtree(repo)

def test_83_local_import_inside_function():
    repo = _create_temp_repo({"lazy.py": "def load():\n    import json\n    return json.dumps({})"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert "json" in manifest.imports_by_file.get("lazy.py", [])
    finally:
        shutil.rmtree(repo)

def test_84_circular_imports_safe():
    repo = _create_temp_repo({"a.py": "import b\nx = 1", "b.py": "import a\ny = 2"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert "b" in manifest.imports_by_file.get("a.py", [])
        assert "a" in manifest.imports_by_file.get("b.py", [])
    finally:
        shutil.rmtree(repo)

def test_85_no_imports_file():
    repo = _create_temp_repo({"pure.py": "x = 42\ndef compute(): return x * 2"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.imports_by_file.get("pure.py") == []
    finally:
        shutil.rmtree(repo)


# ==============================================================================
# CATEGORY 7: Call Graph Topology & Resolution Metrics (Tests 86 to 95)
# ==============================================================================

def test_86_intra_file_function_call_resolved():
    repo = _create_temp_repo({"calc.py": "def add(a, b): return a + b\ndef run(): return add(1, 2)"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, manifest = indexer.index_repository(repo)
        assert manifest.resolved_internal_calls >= 1
        assert manifest.call_resolution_rate > 0.0
    finally:
        shutil.rmtree(repo)

def test_87_cross_file_call_resolved():
    repo = _create_temp_repo({
        "service.py": "from repo import get_data\ndef process(): return get_data()",
        "repo.py": "def get_data(): return 123"
    })
    try:
        indexer = TargetRepositoryIndexer()
        idx, manifest = indexer.index_repository(repo)
        assert manifest.resolved_internal_calls >= 1
    finally:
        shutil.rmtree(repo)

def test_88_external_call_marked_unresolved():
    repo = _create_temp_repo({"net.py": "import requests\ndef fetch(): return requests.get('https://example.com')"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.unresolved_calls >= 1
    finally:
        shutil.rmtree(repo)

def test_89_standard_lib_call_marked_unresolved():
    repo = _create_temp_repo({"calc.py": "import math\ndef calc(x): return math.sqrt(x)"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.unresolved_calls >= 1
    finally:
        shutil.rmtree(repo)

def test_90_zero_calls_resolution_rate_is_one():
    repo = _create_temp_repo({"const.py": "X = 1\nY = 2"})
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.total_call_edges == 0
        assert manifest.call_resolution_rate == 1.0
    finally:
        shutil.rmtree(repo)

def test_91_forward_graph_contains_resolved_callees():
    repo = _create_temp_repo({
        "a.py": "from b import helper\ndef entry(): helper()",
        "b.py": "def helper(): pass"
    })
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        assert "a.py:entry" in idx.forward_graph
        assert "b.py:helper" in idx.forward_graph["a.py:entry"]
    finally:
        shutil.rmtree(repo)

def test_92_self_recursive_call_topology():
    repo = _create_temp_repo({"fact.py": "def fact(n):\n    if n <= 1: return 1\n    return n * fact(n - 1)"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, manifest = indexer.index_repository(repo)
        assert manifest.total_call_edges >= 1
        assert "fact.py:fact" in idx.forward_graph
    finally:
        shutil.rmtree(repo)

def test_93_mutual_recursion_call_topology():
    repo = _create_temp_repo({"even_odd.py": "def is_even(n):\n    return True if n == 0 else is_odd(n-1)\ndef is_odd(n):\n    return False if n == 0 else is_even(n-1)"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, manifest = indexer.index_repository(repo)
        assert manifest.resolved_internal_calls >= 2
    finally:
        shutil.rmtree(repo)

def test_94_symbol_table_fast_id_lookup():
    repo = _create_temp_repo({"auth.py": "class AuthService:\n    def login(self): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        found = idx.symbol_table.lookup_by_id("auth.py:AuthService.login")
        assert found is not None
        assert found.name == "login"
    finally:
        shutil.rmtree(repo)

def test_95_symbol_table_class_methods_lookup():
    repo = _create_temp_repo({"user.py": "class User:\n    def save(self): pass\n    def delete(self): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        save_m = idx.symbol_table.find_in_class("User", "save")
        del_m = idx.symbol_table.find_in_class("User", "delete")
        assert save_m is not None and del_m is not None
        assert save_m.name == "save"
        assert del_m.name == "delete"
    finally:
        shutil.rmtree(repo)


# ==============================================================================
# CATEGORY 8: Architectural Patterns & Live Repository Audits (Tests 96 to 100)
# ==============================================================================

def test_96_clean_architecture_simulation():
    repo = _create_temp_repo({
        "entities/user.py": "class User(Base): pass",
        "repositories/interfaces.py": "class UserRepository(Protocol):\n    def get_user(self): pass",
        "repositories/postgres_user.py": "class PostgresUserRepository(UserRepository):\n    def get_user(self): pass",
        "services/user_service.py": "class UserService:\n    def __init__(self, repo: UserRepository): self.repo = repo\n    def run(self): self.repo.get_user()",
        "pyproject.toml": "dependencies = ['sqlalchemy>=2.0', 'pydantic>=2.0']"
    })
    try:
        indexer = TargetRepositoryIndexer()
        idx, manifest = indexer.index_repository(repo)
        assert manifest.total_files_scanned == 4
        assert manifest.files_indexed_count == 4
        assert any("sqlalchemy" in d for d in manifest.declared_dependencies)
        assert manifest.inheritance_map.get("entities/user.py:User") == ["Base"]
        assert manifest.inheritance_map.get("repositories/interfaces.py:UserRepository") == ["Protocol"]
    finally:
        shutil.rmtree(repo)

def test_97_django_style_architecture_simulation():
    repo = _create_temp_repo({
        "myapp/models.py": "class Post(models.Model): pass",
        "myapp/views.py": "def post_list(request): return render(request, 'index.html')",
        "myapp/urls.py": "urlpatterns = [path('posts/', post_list)]",
        "requirements.txt": "django>=4.2\npsycopg2-binary>=2.9\n"
    })
    try:
        indexer = TargetRepositoryIndexer()
        _, manifest = indexer.index_repository(repo)
        assert manifest.total_files_scanned == 3
        assert any("django" in d for d in manifest.declared_dependencies)
        assert manifest.inheritance_map.get("myapp/models.py:Post") == ["models.Model"]
    finally:
        shutil.rmtree(repo)

def test_98_flat_architecture_simulation():
    repo = _create_temp_repo({
        "database.py": "class Database: pass",
        "server.py": "class Server: pass",
        "utils.py": "def helper(): pass"
    })
    try:
        indexer = TargetRepositoryIndexer()
        idx, manifest = indexer.index_repository(repo)
        assert manifest.total_files_scanned == 3
        assert manifest.files_indexed_count == 3
        assert len(idx.all_symbols) == 3
    finally:
        shutil.rmtree(repo)

def test_99_scale_stress_test_50_files():
    files = {f"pkg/module_{i}.py": f"class Model_{i}(Base):\n    def calc(self): return {i}" for i in range(50)}
    files["requirements.txt"] = "pydantic>=2.0\n"
    repo = _create_temp_repo(files)
    try:
        indexer = TargetRepositoryIndexer()
        idx, manifest = indexer.index_repository(repo)
        assert manifest.total_files_scanned == 50
        assert manifest.files_indexed_count == 50
        assert len(idx.all_symbols) >= 100
        assert len(manifest.inheritance_map) == 50
    finally:
        shutil.rmtree(repo)

def test_100_live_repository_audit():
    # Audits our own actual project codebase: /Users/adityadebnath/Projects/ai_redemption/app
    this_repo_app = Path(__file__).resolve().parent.parent
    indexer = TargetRepositoryIndexer()
    idx, manifest = indexer.index_repository(this_repo_app)
    
    print("\n" + "=" * 80)
    print("🏛️ LIVE REPOSITORY AUDIT: /Users/adityadebnath/Projects/ai_redemption/app")
    print("=" * 80)
    print(f"📁 Files Scanned: {manifest.total_files_scanned}")
    print(f"✅ Files Indexed: {manifest.files_indexed_count}")
    print(f"❌ Parse Errors: {manifest.parse_error_count}")
    print(f"📊 Extracted Symbols: {len(idx.all_symbols)}")
    print(f"🕸️ Total Call Edges: {manifest.total_call_edges}")
    print(f"🎯 Resolved Internal Calls: {manifest.resolved_internal_calls}")
    print(f"📈 Call Resolution Rate: {manifest.call_resolution_rate * 100:.2f}%")
    print(f"📦 Declared Dependencies ({len(manifest.declared_dependencies)}): {manifest.declared_dependencies[:5]}...")
    print("=" * 80)

    assert manifest.total_files_scanned > 20
    assert manifest.files_indexed_count > 20
    assert manifest.parse_error_count == 0
    assert len(idx.all_symbols) > 50


# ==============================================================================
# Master Test Runner (100 Tests)
# ==============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("🚀 RUNNING MASTER 100-TEST VERIFICATION SUITE: Phase 7A Target Intelligence")
    print("=" * 80)

    tests = [globals()[f"test_{i:02d}_{name}"] for i in range(1, 101) for name in [k.split(f"test_{i:02d}_")[-1] for k in globals() if k.startswith(f"test_{i:02d}_")]]
    
    passed = 0
    for idx, test_fn in enumerate(tests, 1):
        try:
            test_fn()
            passed += 1
            if idx % 10 == 0:
                print(f"  ✅ Completed Tests 1 to {idx}...")
        except Exception as e:
            print(f"  ❌ FAILED Test {idx} ({test_fn.__name__}): {e}")
            raise e

    print("=" * 80)
    print(f"🎉 ALL {passed}/100 TARGET REPOSITORY INTELLIGENCE TESTS PASSED 100% GREEN!")
    print("=" * 80)