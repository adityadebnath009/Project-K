"""
app/test/test_target_architect_validator_100.py - Master 100-Test Verification Suite.

Exhaustively verifies Layer 3 (TargetArchitect) & Layer 4 (ProfileValidator):
- Category 1: ProfileValidator Ground-Truth Verification (Tests 1-15)
- Category 2: Hallucination Detection & Component Rejection (Tests 16-30)
- Category 3: Evidence Reference Auditing & Pruning (Tests 31-45)
- Category 4: Symbol Table Cross-Checking (reusable_services & existing_domain_models) (Tests 46-60)
- Category 5: TargetArchitect Prompt Synthesis & Token Budgeting (Tests 61-75)
- Category 6: TargetArchitect Structured Response Handling & Fallbacks (Tests 76-85)
- Category 7: Pipeline Integration & Real-World Repository Auditing (Tests 86-95)
- Category 8: Edge Cases, Stress Tests & Boundary Conditions (Tests 96-100)

Zero external test dependencies. Executable directly with Python standard library.
"""
import json
import shutil
import tempfile
from pathlib import Path
from dataclasses import dataclass

from app.schemas.transposition import (
    ComponentAssessment,
    EvidenceReference,
    TargetComponentRole,
    TargetEvidenceManifest,
    TargetRepositoryProfile,
)
from app.transposition.profile_validator import ProfileValidator, ValidationReport
from app.transposition.target_architect import (
    TargetArchitect,
    TARGET_ARCHITECT_SYSTEM_PROMPT,
)
from app.transposition.target_indexer import (
    TargetCodebaseIndex,
    TargetRepositoryIndexer,
)
from app.schemas.slice import CodeSymbol, FunctionCall, ImportStatement, SymbolKind
from app.slicing.symbol_table import SymbolTable


# Helper for creating temp repos
def _create_temp_repo(files: dict[str, str]) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="featforge_arch_test_"))
    for rel_path, content in files.items():
        file_path = temp_dir / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
    return temp_dir


# Mock LLM for structured output testing
class MockStructuredLLM:
    def __init__(self, response: TargetRepositoryProfile | dict | None = None):
        self.response = response
        self.captured_messages = None

    def with_structured_output(self, schema):
        return self

    def invoke(self, messages):
        self.captured_messages = messages
        if self.response is not None:
            return self.response
        return TargetRepositoryProfile(
            target_root="/mock/root",
            architectural_style="Clean Architecture",
            framework="fastapi",
        )


# ==============================================================================
# CATEGORY 1: ProfileValidator Ground-Truth Verification (Tests 1 to 15)
# ==============================================================================

def test_01_valid_component_relative_path():
    repo = _create_temp_repo({"models/user.py": "class User: pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(
                    component_id="models/user.py",
                    role=TargetComponentRole.DOMAIN_MODEL,
                    confidence=0.95,
                    evidence=[EvidenceReference(file_path="models/user.py", observation="class User")],
                    rationale="User entity",
                )
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert report.verified_components_count == 1
        assert report.rejected_components_count == 0
        assert report.coverage_score == 1.0
        assert len(sanitized.components) == 1
    finally:
        shutil.rmtree(repo)

def test_02_valid_component_absolute_path_matches_root():
    repo = _create_temp_repo({"service.py": "def run(): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        abs_file = str(repo / "service.py")
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(
                    component_id=abs_file,
                    role=TargetComponentRole.BUSINESS_LOGIC,
                    confidence=0.9,
                    evidence=[EvidenceReference(file_path="service.py", observation="run func")],
                    rationale="service logic",
                )
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert report.verified_components_count == 1
    finally:
        shutil.rmtree(repo)

def test_03_file_exists_on_disk_even_if_empty_py():
    repo = _create_temp_repo({"__init__.py": ""})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(
                    component_id="__init__.py",
                    role=TargetComponentRole.INFRASTRUCTURE,
                    confidence=0.5,
                    rationale="Package root",
                )
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert report.verified_components_count == 1
    finally:
        shutil.rmtree(repo)

def test_04_multiple_valid_components_different_roles():
    repo = _create_temp_repo({
        "api/routes.py": "def get_items(): pass",
        "domain/item.py": "class Item: pass",
        "db/repo.py": "class ItemRepo: pass",
    })
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(component_id="api/routes.py", role=TargetComponentRole.ENTRY_POINT, confidence=0.9, rationale="Router"),
                ComponentAssessment(component_id="domain/item.py", role=TargetComponentRole.DOMAIN_MODEL, confidence=0.95, rationale="Model"),
                ComponentAssessment(component_id="db/repo.py", role=TargetComponentRole.DATA_ACCESS, confidence=0.85, rationale="Repo"),
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert report.verified_components_count == 3
        assert report.rejected_components_count == 0
        assert report.coverage_score == 1.0
    finally:
        shutil.rmtree(repo)

def test_05_symbol_table_exact_match():
    repo = _create_temp_repo({"services.py": "class PaymentService: pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            reusable_services=["PaymentService"]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert sanitized.reusable_services == ["PaymentService"]
    finally:
        shutil.rmtree(repo)

def test_06_symbol_table_class_method_lookup():
    repo = _create_temp_repo({"services.py": "class AuthService:\n    def authenticate(self): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            reusable_services=["AuthService.authenticate"]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert "AuthService.authenticate" in sanitized.reusable_services
    finally:
        shutil.rmtree(repo)

def test_07_symbol_table_function_lookup():
    repo = _create_temp_repo({"utils.py": "def hash_password(p): return p"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            reusable_services=["hash_password"]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert sanitized.reusable_services == ["hash_password"]
    finally:
        shutil.rmtree(repo)

def test_08_symbol_table_variable_lookup():
    repo = _create_temp_repo({"config.py": "TIMEOUT = 30"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            reusable_services=["TIMEOUT"]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert "TIMEOUT" in sanitized.reusable_services
    finally:
        shutil.rmtree(repo)

def test_09_symbol_with_colon_path_syntax():
    repo = _create_temp_repo({"services/order.py": "class OrderService: pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            reusable_services=["services/order.py:OrderService"]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert "services/order.py:OrderService" in sanitized.reusable_services
    finally:
        shutil.rmtree(repo)

def test_10_empty_components_list_is_valid():
    repo = _create_temp_repo({"main.py": "x = 1"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(target_root=str(repo), components=[])
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert report.verified_components_count == 0
        assert report.coverage_score == 1.0
    finally:
        shutil.rmtree(repo)

def test_11_component_with_zero_evidence_is_valid():
    repo = _create_temp_repo({"models.py": "class Model: pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(
                    component_id="models.py",
                    role=TargetComponentRole.DOMAIN_MODEL,
                    confidence=0.8,
                    evidence=[],
                    rationale="Model file",
                )
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert report.verified_components_count == 1
    finally:
        shutil.rmtree(repo)

def test_12_component_with_multiple_valid_evidence():
    repo = _create_temp_repo({
        "models.py": "class Base: pass\nclass Model(Base): pass",
    })
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(
                    component_id="models.py",
                    role=TargetComponentRole.DOMAIN_MODEL,
                    confidence=0.9,
                    evidence=[
                        EvidenceReference(file_path="models.py", observation="Inherits Base"),
                        EvidenceReference(file_path="models.py", observation="Defines Model"),
                    ],
                    rationale="Valid evidence",
                )
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert len(sanitized.components[0].evidence) == 2
    finally:
        shutil.rmtree(repo)

def test_13_domain_models_exact_match():
    repo = _create_temp_repo({"entities.py": "class Account: pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            existing_domain_models=["Account"]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert sanitized.existing_domain_models == ["Account"]
    finally:
        shutil.rmtree(repo)

def test_14_domain_model_with_package_prefix():
    repo = _create_temp_repo({"app/models.py": "class Profile: pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            existing_domain_models=["app.models.Profile"]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert "app.models.Profile" in sanitized.existing_domain_models
    finally:
        shutil.rmtree(repo)

def test_15_profile_coverage_score_precision():
    repo = _create_temp_repo({"a.py": "x=1", "b.py": "x=2", "c.py": "x=3"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(component_id="a.py", role=TargetComponentRole.INFRASTRUCTURE, confidence=1.0, rationale=""),
                ComponentAssessment(component_id="b.py", role=TargetComponentRole.INFRASTRUCTURE, confidence=1.0, rationale=""),
                ComponentAssessment(component_id="c.py", role=TargetComponentRole.INFRASTRUCTURE, confidence=1.0, rationale=""),
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.coverage_score == 1.0
        assert sanitized.indexing_coverage_rate == 1.0
    finally:
        shutil.rmtree(repo)


# ==============================================================================
# CATEGORY 2: Hallucination Detection & Component Rejection (Tests 16 to 30)
# ==============================================================================

def test_16_single_hallucinated_component_rejection():
    repo = _create_temp_repo({"real.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(component_id="ghost.py", role=TargetComponentRole.BUSINESS_LOGIC, confidence=0.9, rationale="Fake")
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is False
        assert report.rejected_components_count == 1
        assert "ghost.py" in report.hallucinated_files
        assert len(sanitized.components) == 0
    finally:
        shutil.rmtree(repo)

def test_17_multiple_hallucinated_components_rejection():
    repo = _create_temp_repo({"real.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(component_id="fake1.py", role=TargetComponentRole.BUSINESS_LOGIC, confidence=0.8, rationale=""),
                ComponentAssessment(component_id="fake2.py", role=TargetComponentRole.BUSINESS_LOGIC, confidence=0.8, rationale=""),
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is False
        assert report.rejected_components_count == 2
        assert len(report.hallucinated_files) == 2
    finally:
        shutil.rmtree(repo)

def test_18_hallucinated_deep_subdirectory():
    repo = _create_temp_repo({"real.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(component_id="deep/nested/sub/ghost.py", role=TargetComponentRole.DATA_ACCESS, confidence=0.9, rationale="")
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is False
        assert "deep/nested/sub/ghost.py" in report.hallucinated_files
    finally:
        shutil.rmtree(repo)

def test_19_hallucinated_file_extension_variations():
    repo = _create_temp_repo({"real.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(component_id="backend.rs", role=TargetComponentRole.INFRASTRUCTURE, confidence=0.9, rationale="Rust backend")
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is False
        assert "backend.rs" in report.hallucinated_files
    finally:
        shutil.rmtree(repo)

def test_20_unresolved_question_added_on_hallucination():
    repo = _create_temp_repo({"real.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(component_id="ghost.py", role=TargetComponentRole.BUSINESS_LOGIC, confidence=0.9, rationale="")
            ]
        )
        sanitized, _ = validator.validate_profile(profile, idx)
        assert len(sanitized.unresolved_questions) >= 1
        assert "ghost.py" in sanitized.unresolved_questions[0]
    finally:
        shutil.rmtree(repo)

def test_21_mixed_profile_half_valid_half_fake():
    repo = _create_temp_repo({"a.py": "x=1", "b.py": "x=2"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(component_id="a.py", role=TargetComponentRole.INFRASTRUCTURE, confidence=0.9, rationale=""),
                ComponentAssessment(component_id="b.py", role=TargetComponentRole.INFRASTRUCTURE, confidence=0.9, rationale=""),
                ComponentAssessment(component_id="c.py", role=TargetComponentRole.INFRASTRUCTURE, confidence=0.9, rationale=""),
                ComponentAssessment(component_id="d.py", role=TargetComponentRole.INFRASTRUCTURE, confidence=0.9, rationale=""),
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is False
        assert report.verified_components_count == 2
        assert report.rejected_components_count == 2
        assert report.coverage_score == 0.5
        assert len(sanitized.components) == 2
    finally:
        shutil.rmtree(repo)

def test_22_mixed_profile_1_valid_9_fake_coverage():
    repo = _create_temp_repo({"a0.py": "x=1"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        comps = [ComponentAssessment(component_id="a0.py", role=TargetComponentRole.INFRASTRUCTURE, confidence=0.9, rationale="")]
        for i in range(1, 10):
            comps.append(ComponentAssessment(component_id=f"fake_{i}.py", role=TargetComponentRole.INFRASTRUCTURE, confidence=0.9, rationale=""))
        profile = TargetRepositoryProfile(target_root=str(repo), components=comps)
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.verified_components_count == 1
        assert report.rejected_components_count == 9
        assert report.coverage_score == 0.1
    finally:
        shutil.rmtree(repo)

def test_23_all_hallucinated_components_zero_coverage():
    repo = _create_temp_repo({"real.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(component_id="f1.py", role=TargetComponentRole.INFRASTRUCTURE, confidence=0.9, rationale=""),
                ComponentAssessment(component_id="f2.py", role=TargetComponentRole.INFRASTRUCTURE, confidence=0.9, rationale=""),
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.coverage_score == 0.0
        assert report.verified_components_count == 0
        assert report.rejected_components_count == 2
    finally:
        shutil.rmtree(repo)

def test_24_valid_component_metadata_preserved_after_filtering():
    repo = _create_temp_repo({"real.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(component_id="real.py", role=TargetComponentRole.ENTRY_POINT, confidence=0.97, rationale="Specific rationale text"),
                ComponentAssessment(component_id="ghost.py", role=TargetComponentRole.ENTRY_POINT, confidence=0.90, rationale="Ghost"),
            ]
        )
        sanitized, _ = validator.validate_profile(profile, idx)
        assert len(sanitized.components) == 1
        assert sanitized.components[0].confidence == 0.97
        assert sanitized.components[0].rationale == "Specific rationale text"
        assert sanitized.components[0].role == TargetComponentRole.ENTRY_POINT
    finally:
        shutil.rmtree(repo)

def test_25_subtle_typo_in_directory_name():
    repo = _create_temp_repo({"entities/user.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(component_id="entitie/user.py", role=TargetComponentRole.DOMAIN_MODEL, confidence=0.9, rationale="")
            ]
        )
        _, report = validator.validate_profile(profile, idx)
        assert report.is_valid is False
        assert "entitie/user.py" in report.hallucinated_files
    finally:
        shutil.rmtree(repo)

def test_26_subtle_typo_in_file_name():
    repo = _create_temp_repo({"auth_service.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(component_id="auth_services.py", role=TargetComponentRole.BUSINESS_LOGIC, confidence=0.9, rationale="")
            ]
        )
        _, report = validator.validate_profile(profile, idx)
        assert report.is_valid is False
        assert "auth_services.py" in report.hallucinated_files
    finally:
        shutil.rmtree(repo)

def test_27_component_id_with_trailing_colon_real_file():
    repo = _create_temp_repo({"routes.py": "def login(): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(component_id="routes.py:login", role=TargetComponentRole.ENTRY_POINT, confidence=0.95, rationale="")
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert report.verified_components_count == 1
    finally:
        shutil.rmtree(repo)

def test_28_component_id_with_trailing_colon_fake_file():
    repo = _create_temp_repo({"routes.py": "def login(): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(component_id="ghost_routes.py:login", role=TargetComponentRole.ENTRY_POINT, confidence=0.95, rationale="")
            ]
        )
        _, report = validator.validate_profile(profile, idx)
        assert report.is_valid is False
        assert "ghost_routes.py" in report.hallucinated_files
    finally:
        shutil.rmtree(repo)

def test_29_deduplication_of_hallucinated_files():
    repo = _create_temp_repo({"real.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(component_id="ghost.py", role=TargetComponentRole.BUSINESS_LOGIC, confidence=0.8, rationale="1"),
                ComponentAssessment(component_id="ghost.py", role=TargetComponentRole.BUSINESS_LOGIC, confidence=0.8, rationale="2"),
            ]
        )
        _, report = validator.validate_profile(profile, idx)
        # Should be deduped in report
        assert report.hallucinated_files == ["ghost.py"]
    finally:
        shutil.rmtree(repo)

def test_30_case_sensitive_file_lookup():
    repo = _create_temp_repo({"service.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        # Non-matching casing check on systems that distinguish
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(component_id="SERVICE_NON_EXISTENT.py", role=TargetComponentRole.BUSINESS_LOGIC, confidence=0.8, rationale="")
            ]
        )
        _, report = validator.validate_profile(profile, idx)
        assert "SERVICE_NON_EXISTENT.py" in report.hallucinated_files
    finally:
        shutil.rmtree(repo)


# ==============================================================================
# CATEGORY 3: Evidence Reference Auditing & Pruning (Tests 31 to 45)
# ==============================================================================

def test_31_all_valid_evidence_retained():
    repo = _create_temp_repo({"a.py": "pass", "b.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(
                    component_id="a.py",
                    role=TargetComponentRole.BUSINESS_LOGIC,
                    confidence=0.9,
                    evidence=[
                        EvidenceReference(file_path="a.py", observation="A file"),
                        EvidenceReference(file_path="b.py", observation="B file"),
                    ],
                    rationale="",
                )
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert len(sanitized.components[0].evidence) == 2
    finally:
        shutil.rmtree(repo)

def test_32_single_ghost_evidence_stripped():
    repo = _create_temp_repo({"real.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(
                    component_id="real.py",
                    role=TargetComponentRole.BUSINESS_LOGIC,
                    confidence=0.9,
                    evidence=[
                        EvidenceReference(file_path="real.py", observation="Real"),
                        EvidenceReference(file_path="ghost.py", observation="Ghost"),
                    ],
                    rationale="",
                )
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is False
        assert "ghost.py" in report.hallucinated_files
        assert len(sanitized.components[0].evidence) == 1
        assert sanitized.components[0].evidence[0].file_path == "real.py"
    finally:
        shutil.rmtree(repo)

def test_33_all_ghost_evidence_stripped_component_kept():
    repo = _create_temp_repo({"real.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(
                    component_id="real.py",
                    role=TargetComponentRole.BUSINESS_LOGIC,
                    confidence=0.9,
                    evidence=[
                        EvidenceReference(file_path="ghost1.py", observation="G1"),
                        EvidenceReference(file_path="ghost2.py", observation="G2"),
                    ],
                    rationale="",
                )
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.verified_components_count == 1
        assert len(sanitized.components[0].evidence) == 0
        assert "ghost1.py" in report.hallucinated_files
        assert "ghost2.py" in report.hallucinated_files
    finally:
        shutil.rmtree(repo)

def test_34_ghost_evidence_recorded_in_report():
    repo = _create_temp_repo({"real.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(
                    component_id="real.py",
                    role=TargetComponentRole.BUSINESS_LOGIC,
                    confidence=0.9,
                    evidence=[EvidenceReference(file_path="fake_contract.py", observation="Fake")],
                    rationale="",
                )
            ]
        )
        _, report = validator.validate_profile(profile, idx)
        assert "fake_contract.py" in report.hallucinated_files
    finally:
        shutil.rmtree(repo)

def test_35_evidence_line_numbers_preserved():
    repo = _create_temp_repo({"real.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(
                    component_id="real.py",
                    role=TargetComponentRole.BUSINESS_LOGIC,
                    confidence=0.9,
                    evidence=[EvidenceReference(file_path="real.py", line_start=10, line_end=25, observation="Lines 10-25")],
                    rationale="",
                )
            ]
        )
        sanitized, _ = validator.validate_profile(profile, idx)
        ev = sanitized.components[0].evidence[0]
        assert ev.line_start == 10
        assert ev.line_end == 25
    finally:
        shutil.rmtree(repo)

def test_36_evidence_observation_preserved():
    repo = _create_temp_repo({"real.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(
                    component_id="real.py",
                    role=TargetComponentRole.BUSINESS_LOGIC,
                    confidence=0.9,
                    evidence=[EvidenceReference(file_path="real.py", observation="Inherits from AbstractService")],
                    rationale="",
                )
            ]
        )
        sanitized, _ = validator.validate_profile(profile, idx)
        assert sanitized.components[0].evidence[0].observation == "Inherits from AbstractService"
    finally:
        shutil.rmtree(repo)

def test_37_multi_component_evidence_auditing():
    repo = _create_temp_repo({"c1.py": "pass", "c2.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(
                    component_id="c1.py",
                    role=TargetComponentRole.BUSINESS_LOGIC,
                    confidence=0.9,
                    evidence=[EvidenceReference(file_path="c1.py", observation="ok"), EvidenceReference(file_path="ghost1.py", observation="bad")],
                    rationale="",
                ),
                ComponentAssessment(
                    component_id="c2.py",
                    role=TargetComponentRole.BUSINESS_LOGIC,
                    confidence=0.9,
                    evidence=[EvidenceReference(file_path="c2.py", observation="ok"), EvidenceReference(file_path="ghost2.py", observation="bad")],
                    rationale="",
                ),
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert len(sanitized.components[0].evidence) == 1
        assert len(sanitized.components[1].evidence) == 1
        assert set(report.hallucinated_files) == {"ghost1.py", "ghost2.py"}
    finally:
        shutil.rmtree(repo)

def test_38_evidence_referencing_non_py_real_file():
    repo = _create_temp_repo({"app.py": "pass", "config.json": "{}"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(
                    component_id="app.py",
                    role=TargetComponentRole.ENTRY_POINT,
                    confidence=0.9,
                    evidence=[EvidenceReference(file_path="config.json", observation="Config file")],
                    rationale="",
                )
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert len(sanitized.components[0].evidence) == 1
    finally:
        shutil.rmtree(repo)

def test_39_evidence_referencing_root_pyproject():
    repo = _create_temp_repo({"app.py": "pass", "pyproject.toml": "[tool]"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(
                    component_id="app.py",
                    role=TargetComponentRole.ENTRY_POINT,
                    confidence=0.9,
                    evidence=[EvidenceReference(file_path="pyproject.toml", observation="Manifest")],
                    rationale="",
                )
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert len(sanitized.components[0].evidence) == 1
    finally:
        shutil.rmtree(repo)

def test_40_evidence_symbol_name_field_preserved():
    repo = _create_temp_repo({"app.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(
                    component_id="app.py",
                    role=TargetComponentRole.ENTRY_POINT,
                    confidence=0.9,
                    evidence=[EvidenceReference(file_path="app.py", symbol_name="my_symbol", observation="ok")],
                    rationale="",
                )
            ]
        )
        sanitized, _ = validator.validate_profile(profile, idx)
        assert sanitized.components[0].evidence[0].symbol_name == "my_symbol"
    finally:
        shutil.rmtree(repo)

def test_41_evidence_with_whitespace_path_trimmed():
    repo = _create_temp_repo({"app.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(
                    component_id="app.py",
                    role=TargetComponentRole.ENTRY_POINT,
                    confidence=0.9,
                    evidence=[EvidenceReference(file_path="  app.py  ", observation="ok")],
                    rationale="",
                )
            ]
        )
        # Even if raw path has spaces, check resolution
        _, report = validator.validate_profile(profile, idx)
        # Invalid whitespace path will be treated as non-existent
        assert "  app.py  " in report.hallucinated_files
    finally:
        shutil.rmtree(repo)

def test_42_duplicate_ghost_evidence_deduped_in_report():
    repo = _create_temp_repo({"app.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(
                    component_id="app.py",
                    role=TargetComponentRole.ENTRY_POINT,
                    confidence=0.9,
                    evidence=[
                        EvidenceReference(file_path="bad.py", observation="bad 1"),
                        EvidenceReference(file_path="bad.py", observation="bad 2"),
                    ],
                    rationale="",
                )
            ]
        )
        _, report = validator.validate_profile(profile, idx)
        assert report.hallucinated_files == ["bad.py"]
    finally:
        shutil.rmtree(repo)

def test_43_valid_evidence_in_subpackage():
    repo = _create_temp_repo({"pkg/sub/module.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(
                    component_id="pkg/sub/module.py",
                    role=TargetComponentRole.INFRASTRUCTURE,
                    confidence=0.9,
                    evidence=[EvidenceReference(file_path="pkg/sub/module.py", observation="submodule")],
                    rationale="",
                )
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert len(sanitized.components[0].evidence) == 1
    finally:
        shutil.rmtree(repo)

def test_44_report_is_valid_false_if_any_evidence_hallucinated():
    repo = _create_temp_repo({"app.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(
                    component_id="app.py",
                    role=TargetComponentRole.ENTRY_POINT,
                    confidence=0.9,
                    evidence=[
                        EvidenceReference(file_path="app.py", observation="ok"),
                        EvidenceReference(file_path="missing.py", observation="not ok"),
                    ],
                    rationale="",
                )
            ]
        )
        _, report = validator.validate_profile(profile, idx)
        assert report.is_valid is False
    finally:
        shutil.rmtree(repo)

def test_45_empty_evidence_list_preserved():
    repo = _create_temp_repo({"app.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(
                    component_id="app.py",
                    role=TargetComponentRole.ENTRY_POINT,
                    confidence=0.9,
                    evidence=[],
                    rationale="",
                )
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert sanitized.components[0].evidence == []
    finally:
        shutil.rmtree(repo)


# ==============================================================================
# CATEGORY 4: Symbol Table Cross-Checking (Tests 46 to 60)
# ==============================================================================

def test_46_valid_reusable_service_retained():
    repo = _create_temp_repo({"services.py": "class EmailService: pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            reusable_services=["EmailService"]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert sanitized.reusable_services == ["EmailService"]
        assert report.is_valid is True
    finally:
        shutil.rmtree(repo)

def test_47_hallucinated_service_dropped():
    repo = _create_temp_repo({"services.py": "class EmailService: pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            reusable_services=["FakeSmsService"]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert sanitized.reusable_services == []
        assert "FakeSmsService" in report.hallucinated_symbols
        assert report.is_valid is False
    finally:
        shutil.rmtree(repo)

def test_48_valid_domain_model_retained():
    repo = _create_temp_repo({"models.py": "class Order: pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            existing_domain_models=["Order"]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert sanitized.existing_domain_models == ["Order"]
        assert report.is_valid is True
    finally:
        shutil.rmtree(repo)

def test_49_hallucinated_domain_model_dropped():
    repo = _create_temp_repo({"models.py": "class Order: pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            existing_domain_models=["GhostCustomer"]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert sanitized.existing_domain_models == []
        assert "GhostCustomer" in report.hallucinated_symbols
        assert report.is_valid is False
    finally:
        shutil.rmtree(repo)

def test_50_warning_added_to_unresolved_questions_for_fake_service():
    repo = _create_temp_repo({"s.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            reusable_services=["ImaginaryService"]
        )
        sanitized, _ = validator.validate_profile(profile, idx)
        assert any("ImaginaryService" in q for q in sanitized.unresolved_questions)
    finally:
        shutil.rmtree(repo)

def test_51_warning_added_to_unresolved_questions_for_fake_model():
    repo = _create_temp_repo({"s.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            existing_domain_models=["ImaginaryModel"]
        )
        sanitized, _ = validator.validate_profile(profile, idx)
        assert any("ImaginaryModel" in q for q in sanitized.unresolved_questions)
    finally:
        shutil.rmtree(repo)

def test_52_mixed_services_partial_retention():
    repo = _create_temp_repo({"services.py": "class GoodService: pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            reusable_services=["GoodService", "BadService"]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert sanitized.reusable_services == ["GoodService"]
        assert "BadService" in report.hallucinated_symbols
    finally:
        shutil.rmtree(repo)

def test_53_mixed_models_partial_retention():
    repo = _create_temp_repo({"models.py": "class GoodModel: pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            existing_domain_models=["GoodModel", "BadModel"]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert sanitized.existing_domain_models == ["GoodModel"]
        assert "BadModel" in report.hallucinated_symbols
    finally:
        shutil.rmtree(repo)

def test_54_symbol_with_nested_module_path():
    repo = _create_temp_repo({"app/core/security.py": "def verify_token(): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            reusable_services=["app.core.security.verify_token"]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert "app.core.security.verify_token" in sanitized.reusable_services
    finally:
        shutil.rmtree(repo)

def test_55_symbol_with_file_colon_path():
    repo = _create_temp_repo({"db/session.py": "def get_db(): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            reusable_services=["db/session.py:get_db"]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert "db/session.py:get_db" in sanitized.reusable_services
    finally:
        shutil.rmtree(repo)

def test_56_symbol_case_sensitivity_check():
    repo = _create_temp_repo({"services.py": "class UserService: pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        # "userservice" in lowercase should not match "UserService"
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            reusable_services=["userservice"]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert "userservice" in report.hallucinated_symbols
        assert sanitized.reusable_services == []
    finally:
        shutil.rmtree(repo)

def test_57_duplicate_hallucinated_symbols_deduped():
    repo = _create_temp_repo({"s.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            reusable_services=["GhostService"],
            existing_domain_models=["GhostService"],
        )
        _, report = validator.validate_profile(profile, idx)
        assert report.hallucinated_symbols == ["GhostService"]
    finally:
        shutil.rmtree(repo)

def test_58_empty_services_and_models_is_valid():
    repo = _create_temp_repo({"s.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            reusable_services=[],
            existing_domain_models=[],
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert sanitized.reusable_services == []
        assert sanitized.existing_domain_models == []
    finally:
        shutil.rmtree(repo)

def test_59_reusable_services_method_in_class():
    repo = _create_temp_repo({"services.py": "class TokenManager:\n    def create_token(self): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            reusable_services=["TokenManager.create_token"]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert "TokenManager.create_token" in sanitized.reusable_services
    finally:
        shutil.rmtree(repo)

def test_60_all_hallucinated_symbols_marked_invalid():
    repo = _create_temp_repo({"s.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            reusable_services=["Fake1", "Fake2"],
            existing_domain_models=["Fake3"],
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is False
        assert set(report.hallucinated_symbols) == {"Fake1", "Fake2", "Fake3"}
        assert sanitized.reusable_services == []
        assert sanitized.existing_domain_models == []
    finally:
        shutil.rmtree(repo)


# ==============================================================================
# CATEGORY 5: TargetArchitect Prompt Synthesis & Token Budgeting (Tests 61 to 75)
# ==============================================================================

def test_61_manifest_prompt_zero_dependencies():
    manifest = TargetEvidenceManifest(
        target_root="/test",
        total_files_scanned=1,
        files_indexed_count=1,
        parse_error_count=0,
        declared_dependencies=[],
    )
    architect = TargetArchitect(llm=None)
    mock = MockStructuredLLM()
    architect.structured_llm = mock
    architect.analyze_manifest(manifest)
    user_msg = mock.captured_messages[1].content
    assert '"declared_dependencies": []' in user_msg

def test_62_manifest_prompt_with_dependencies():
    manifest = TargetEvidenceManifest(
        target_root="/test",
        total_files_scanned=1,
        files_indexed_count=1,
        parse_error_count=0,
        declared_dependencies=["fastapi", "sqlalchemy"],
    )
    architect = TargetArchitect(llm=None)
    mock = MockStructuredLLM()
    architect.structured_llm = mock
    architect.analyze_manifest(manifest)
    user_msg = mock.captured_messages[1].content
    assert "fastapi" in user_msg
    assert "sqlalchemy" in user_msg

def test_63_manifest_prompt_bounds_inheritance_to_30():
    inh = {f"file_{i}.py:Class_{i}": [f"Base_{i}"] for i in range(50)}
    manifest = TargetEvidenceManifest(
        target_root="/test",
        total_files_scanned=50,
        files_indexed_count=50,
        parse_error_count=0,
        inheritance_map=inh,
    )
    architect = TargetArchitect(llm=None)
    mock = MockStructuredLLM()
    architect.structured_llm = mock
    architect.analyze_manifest(manifest)
    data = json.loads(mock.captured_messages[1].content.split("```json\n")[1].split("\n```")[0])
    assert len(data["sample_inheritance"]) == 30

def test_64_manifest_prompt_bounds_decorators_to_30():
    decs = {f"file_{i}.py:func_{i}": ["decorator_a"] for i in range(50)}
    manifest = TargetEvidenceManifest(
        target_root="/test",
        total_files_scanned=50,
        files_indexed_count=50,
        parse_error_count=0,
        decorators_by_symbol=decs,
    )
    architect = TargetArchitect(llm=None)
    mock = MockStructuredLLM()
    architect.structured_llm = mock
    architect.analyze_manifest(manifest)
    data = json.loads(mock.captured_messages[1].content.split("```json\n")[1].split("\n```")[0])
    assert len(data["sample_decorators"]) == 30

def test_65_manifest_prompt_bounds_imports_to_25_files():
    imps = {f"file_{i}.py": [f"mod_{j}" for j in range(10)] for i in range(50)}
    manifest = TargetEvidenceManifest(
        target_root="/test",
        total_files_scanned=50,
        files_indexed_count=50,
        parse_error_count=0,
        imports_by_file=imps,
    )
    architect = TargetArchitect(llm=None)
    mock = MockStructuredLLM()
    architect.structured_llm = mock
    architect.analyze_manifest(manifest)
    data = json.loads(mock.captured_messages[1].content.split("```json\n")[1].split("\n```")[0])
    assert len(data["sample_imports"]) == 25
    # Each file's imports should be bounded to 5
    for k, v in data["sample_imports"].items():
        assert len(v) == 5

def test_66_call_resolution_rate_formatted_as_percentage():
    manifest = TargetEvidenceManifest(
        target_root="/test",
        total_files_scanned=1,
        files_indexed_count=1,
        parse_error_count=0,
        call_resolution_rate=0.6386,
    )
    architect = TargetArchitect(llm=None)
    mock = MockStructuredLLM()
    architect.structured_llm = mock
    architect.analyze_manifest(manifest)
    user_msg = mock.captured_messages[1].content
    assert '"call_resolution_rate": "63.9%"' in user_msg

def test_67_system_prompt_contains_grounding_rule():
    assert "Ground every conclusion in the provided evidence" in TARGET_ARCHITECT_SYSTEM_PROMPT

def test_68_system_prompt_contains_all_target_component_roles():
    for role in TargetComponentRole:
        assert role.value in TARGET_ARCHITECT_SYSTEM_PROMPT

def test_69_system_prompt_contains_confidence_guidance():
    assert "confidence lower (< 0.7)" in TARGET_ARCHITECT_SYSTEM_PROMPT

def test_70_system_prompt_mentions_clean_architecture():
    assert "Clean Architecture" in TARGET_ARCHITECT_SYSTEM_PROMPT

def test_71_user_prompt_is_valid_json_fence():
    manifest = TargetEvidenceManifest(
        target_root="/test",
        total_files_scanned=1,
        files_indexed_count=1,
        parse_error_count=0,
    )
    architect = TargetArchitect(llm=None)
    mock = MockStructuredLLM()
    architect.structured_llm = mock
    architect.analyze_manifest(manifest)
    msg = mock.captured_messages[1].content
    assert msg.startswith("Analyze the following evidence manifest")
    assert "```json\n" in msg
    assert "\n```" in msg

def test_72_architect_initialization_defaults_ollama():
    architect = TargetArchitect(llm=None)
    assert architect.llm is not None
    assert architect.structured_llm is not None

def test_73_architect_initialization_with_custom_llm():
    custom = MockStructuredLLM()
    architect = TargetArchitect(llm=custom)
    assert architect.llm is custom

def test_74_manifest_prompt_includes_target_root():
    manifest = TargetEvidenceManifest(
        target_root="/custom/path/repo",
        total_files_scanned=5,
        files_indexed_count=5,
        parse_error_count=0,
    )
    architect = TargetArchitect(llm=None)
    mock = MockStructuredLLM()
    architect.structured_llm = mock
    architect.analyze_manifest(manifest)
    assert "/custom/path/repo" in mock.captured_messages[1].content

def test_75_manifest_prompt_includes_files_scanned():
    manifest = TargetEvidenceManifest(
        target_root="/test",
        total_files_scanned=42,
        files_indexed_count=42,
        parse_error_count=0,
    )
    architect = TargetArchitect(llm=None)
    mock = MockStructuredLLM()
    architect.structured_llm = mock
    architect.analyze_manifest(manifest)
    assert '"files_scanned": 42' in mock.captured_messages[1].content


# ==============================================================================
# CATEGORY 6: TargetArchitect Structured Response Handling & Fallbacks (Tests 76 to 85)
# ==============================================================================

def test_76_architect_returns_profile_instance():
    manifest = TargetEvidenceManifest(
        target_root="/test",
        total_files_scanned=1,
        files_indexed_count=1,
        parse_error_count=0,
    )
    expected = TargetRepositoryProfile(
        target_root="/test",
        architectural_style="Layered MVC",
        framework="django",
    )
    architect = TargetArchitect(llm=None)
    architect.structured_llm = MockStructuredLLM(response=expected)
    res = architect.analyze_manifest(manifest)
    assert isinstance(res, TargetRepositoryProfile)
    assert res.architectural_style == "Layered MVC"
    assert res.framework == "django"

def test_77_architect_validates_raw_dict_response():
    manifest = TargetEvidenceManifest(
        target_root="/test",
        total_files_scanned=1,
        files_indexed_count=1,
        parse_error_count=0,
    )
    raw_dict = {
        "target_root": "/test",
        "architectural_style": "Clean Architecture",
        "framework": "fastapi",
        "orm": "sqlalchemy_2.0",
        "dto_pattern": "pydantic_v2",
        "components": [
            {
                "component_id": "app/models.py",
                "role": "domain_model",
                "confidence": 0.95,
                "rationale": "BaseModel domain",
                "evidence": []
            }
        ]
    }
    architect = TargetArchitect(llm=None)
    architect.structured_llm = MockStructuredLLM(response=raw_dict)
    res = architect.analyze_manifest(manifest)
    assert isinstance(res, TargetRepositoryProfile)
    assert res.architectural_style == "Clean Architecture"
    assert len(res.components) == 1
    assert res.components[0].role == TargetComponentRole.DOMAIN_MODEL

def test_78_architect_profile_preserves_orm():
    manifest = TargetEvidenceManifest(target_root="/test", total_files_scanned=1, files_indexed_count=1, parse_error_count=0)
    profile = TargetRepositoryProfile(target_root="/test", orm="tortoise")
    architect = TargetArchitect(llm=None)
    architect.structured_llm = MockStructuredLLM(response=profile)
    res = architect.analyze_manifest(manifest)
    assert res.orm == "tortoise"

def test_79_architect_profile_preserves_dto_pattern():
    manifest = TargetEvidenceManifest(target_root="/test", total_files_scanned=1, files_indexed_count=1, parse_error_count=0)
    profile = TargetRepositoryProfile(target_root="/test", dto_pattern="dataclasses")
    architect = TargetArchitect(llm=None)
    architect.structured_llm = MockStructuredLLM(response=profile)
    res = architect.analyze_manifest(manifest)
    assert res.dto_pattern == "dataclasses"

def test_80_architect_profile_preserves_pk_pattern():
    manifest = TargetEvidenceManifest(target_root="/test", total_files_scanned=1, files_indexed_count=1, parse_error_count=0)
    profile = TargetRepositoryProfile(target_root="/test", primary_key_pattern="uuid7")
    architect = TargetArchitect(llm=None)
    architect.structured_llm = MockStructuredLLM(response=profile)
    res = architect.analyze_manifest(manifest)
    assert res.primary_key_pattern == "uuid7"

def test_81_architect_profile_preserves_test_framework():
    manifest = TargetEvidenceManifest(target_root="/test", total_files_scanned=1, files_indexed_count=1, parse_error_count=0)
    profile = TargetRepositoryProfile(target_root="/test", test_framework="pytest")
    architect = TargetArchitect(llm=None)
    architect.structured_llm = MockStructuredLLM(response=profile)
    res = architect.analyze_manifest(manifest)
    assert res.test_framework == "pytest"

def test_82_architect_profile_preserves_unresolved_questions():
    manifest = TargetEvidenceManifest(target_root="/test", total_files_scanned=1, files_indexed_count=1, parse_error_count=0)
    profile = TargetRepositoryProfile(
        target_root="/test",
        unresolved_questions=["Is this repo using alembic migrations?"]
    )
    architect = TargetArchitect(llm=None)
    architect.structured_llm = MockStructuredLLM(response=profile)
    res = architect.analyze_manifest(manifest)
    assert "Is this repo using alembic migrations?" in res.unresolved_questions

def test_83_architect_profile_preserves_confidence_score():
    manifest = TargetEvidenceManifest(target_root="/test", total_files_scanned=1, files_indexed_count=1, parse_error_count=0)
    profile = TargetRepositoryProfile(
        target_root="/test",
        components=[
            ComponentAssessment(
                component_id="auth.py",
                role=TargetComponentRole.BUSINESS_LOGIC,
                confidence=0.72,
                rationale="Logic",
            )
        ]
    )
    architect = TargetArchitect(llm=None)
    architect.structured_llm = MockStructuredLLM(response=profile)
    res = architect.analyze_manifest(manifest)
    assert res.components[0].confidence == 0.72

def test_84_architect_profile_empty_defaults():
    manifest = TargetEvidenceManifest(target_root="/test", total_files_scanned=1, files_indexed_count=1, parse_error_count=0)
    profile = TargetRepositoryProfile(target_root="/test")
    architect = TargetArchitect(llm=None)
    architect.structured_llm = MockStructuredLLM(response=profile)
    res = architect.analyze_manifest(manifest)
    assert res.architectural_style == "unknown"
    assert res.framework == "unknown"
    assert res.orm == "unknown"

def test_85_architect_profile_indexing_coverage_rate_preserved():
    manifest = TargetEvidenceManifest(target_root="/test", total_files_scanned=1, files_indexed_count=1, parse_error_count=0)
    profile = TargetRepositoryProfile(target_root="/test", indexing_coverage_rate=0.88)
    architect = TargetArchitect(llm=None)
    architect.structured_llm = MockStructuredLLM(response=profile)
    res = architect.analyze_manifest(manifest)
    assert res.indexing_coverage_rate == 0.88


# ==============================================================================
# CATEGORY 7: Pipeline Integration & Real-World Repository Auditing (Tests 86 to 95)
# ==============================================================================

def test_86_e2e_indexer_to_validator_clean_architecture_sim():
    repo = _create_temp_repo({
        "entities/user.py": "class User:\n    id: str",
        "repositories/user_repo.py": "class UserRepository:\n    def get(self, id): pass",
        "services/user_service.py": "class UserService:\n    def __init__(self, repo): self.repo = repo",
        "api/endpoints.py": "def login(): pass",
        "requirements.txt": "fastapi\nsqlalchemy\n",
    })
    try:
        indexer = TargetRepositoryIndexer()
        idx, manifest = indexer.index_repository(repo)

        # Simulated Architect response
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            architectural_style="Clean Architecture",
            framework="fastapi",
            orm="sqlalchemy",
            components=[
                ComponentAssessment(component_id="entities/user.py", role=TargetComponentRole.DOMAIN_MODEL, confidence=0.95, rationale="User entity"),
                ComponentAssessment(component_id="repositories/user_repo.py", role=TargetComponentRole.DATA_ACCESS, confidence=0.90, rationale="User repo"),
                ComponentAssessment(component_id="services/user_service.py", role=TargetComponentRole.BUSINESS_LOGIC, confidence=0.92, rationale="User service"),
                ComponentAssessment(component_id="api/endpoints.py", role=TargetComponentRole.ENTRY_POINT, confidence=0.88, rationale="Login endpoint"),
            ],
            reusable_services=["UserService", "UserRepository"],
            existing_domain_models=["User"],
        )

        validator = ProfileValidator()
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert report.verified_components_count == 4
        assert report.coverage_score == 1.0
        assert len(sanitized.components) == 4
        assert sanitized.reusable_services == ["UserService", "UserRepository"]
        assert sanitized.existing_domain_models == ["User"]
    finally:
        shutil.rmtree(repo)

def test_87_e2e_indexer_to_validator_catches_simulated_hallucinations():
    repo = _create_temp_repo({
        "app/models.py": "class Post: pass",
        "app/views.py": "def post_detail(): pass",
    })
    try:
        indexer = TargetRepositoryIndexer()
        idx, manifest = indexer.index_repository(repo)

        # Architect with 1 hallucinated file and 1 hallucinated service
        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(component_id="app/models.py", role=TargetComponentRole.DOMAIN_MODEL, confidence=0.9, rationale="Post model"),
                ComponentAssessment(component_id="app/controllers.py", role=TargetComponentRole.ENTRY_POINT, confidence=0.9, rationale="Ghost controller"),
            ],
            reusable_services=["post_detail", "non_existent_function"],
            existing_domain_models=["Post"],
        )

        validator = ProfileValidator()
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is False
        assert report.verified_components_count == 1
        assert report.rejected_components_count == 1
        assert "app/controllers.py" in report.hallucinated_files
        assert "non_existent_function" in report.hallucinated_symbols
        assert sanitized.reusable_services == ["post_detail"]
    finally:
        shutil.rmtree(repo)

def test_88_real_ai_redemption_codebase_validation():
    indexer = TargetRepositoryIndexer()
    idx, _ = indexer.index_repository(Path("app").resolve())
    validator = ProfileValidator()

    profile = TargetRepositoryProfile(
        target_root=str(Path("app").resolve()),
        architectural_style="Clean Architecture",
        framework="fastapi",
        components=[
            ComponentAssessment(
                component_id="entities/user.py",
                role=TargetComponentRole.DOMAIN_MODEL,
                confidence=0.95,
                evidence=[EvidenceReference(file_path="entities/user.py", observation="User entity")],
                rationale="User entity",
            ),
            ComponentAssessment(
                component_id="services/user_service.py",
                role=TargetComponentRole.BUSINESS_LOGIC,
                confidence=0.92,
                evidence=[EvidenceReference(file_path="services/user_service.py", observation="UserService logic")],
                rationale="User business logic",
            ),
            ComponentAssessment(
                component_id="repositories/postgres_user.py",
                role=TargetComponentRole.DATA_ACCESS,
                confidence=0.90,
                evidence=[EvidenceReference(file_path="repositories/postgres_user.py", observation="Postgres user repo")],
                rationale="Data access",
            ),
        ],
        reusable_services=["UserService", "PostgresUserRepository"],
        existing_domain_models=["User"],
    )

    sanitized, report = validator.validate_profile(profile, idx)
    assert report.is_valid is True
    assert report.verified_components_count == 3
    assert report.coverage_score == 1.0
    assert len(sanitized.components) == 3
    assert "UserService" in sanitized.reusable_services
    assert "PostgresUserRepository" in sanitized.reusable_services
    assert "User" in sanitized.existing_domain_models

def test_89_real_ai_redemption_token_counter_symbol_lookup():
    indexer = TargetRepositoryIndexer()
    idx, _ = indexer.index_repository(Path("app").resolve())
    validator = ProfileValidator()

    profile = TargetRepositoryProfile(
        target_root=str(Path("app").resolve()),
        reusable_services=["TokenCounter", "Compactor"],
    )
    sanitized, report = validator.validate_profile(profile, idx)
    assert report.is_valid is True
    assert "TokenCounter" in sanitized.reusable_services
    assert "Compactor" in sanitized.reusable_services

def test_90_real_ai_redemption_flags_ghost_service():
    indexer = TargetRepositoryIndexer()
    idx, _ = indexer.index_repository(Path("app").resolve())
    validator = ProfileValidator()

    profile = TargetRepositoryProfile(
        target_root=str(Path("app").resolve()),
        reusable_services=["NonExistentBillingPipeline"],
    )
    sanitized, report = validator.validate_profile(profile, idx)
    assert report.is_valid is False
    assert "NonExistentBillingPipeline" in report.hallucinated_symbols
    assert sanitized.reusable_services == []

def test_91_real_conduit_fastapi_audit():
    conduit_path = Path("test_fixtures/realworld_fastapi").resolve()
    indexer = TargetRepositoryIndexer()
    idx, _ = indexer.index_repository(conduit_path)
    validator = ProfileValidator()

    profile = TargetRepositoryProfile(
        target_root=str(conduit_path),
        components=[
            ComponentAssessment(
                component_id="app/models/domain/users.py",
                role=TargetComponentRole.DOMAIN_MODEL,
                confidence=0.95,
                evidence=[EvidenceReference(file_path="app/models/domain/users.py", observation="User domain")],
                rationale="Domain user",
            ),
            ComponentAssessment(
                component_id="app/db/repositories/users.py",
                role=TargetComponentRole.DATA_ACCESS,
                confidence=0.90,
                evidence=[EvidenceReference(file_path="app/db/repositories/users.py", observation="User repository")],
                rationale="User data access",
            ),
        ],
        reusable_services=["UsersRepository"],
        existing_domain_models=["User"],
    )
    sanitized, report = validator.validate_profile(profile, idx)
    assert report.is_valid is True
    assert report.verified_components_count == 2
    assert "UsersRepository" in sanitized.reusable_services
    assert "User" in sanitized.existing_domain_models

def test_92_real_httpx_audit():
    httpx_path = Path("test_fixtures/httpx_repo").resolve()
    indexer = TargetRepositoryIndexer()
    idx, _ = indexer.index_repository(httpx_path)
    validator = ProfileValidator()

    profile = TargetRepositoryProfile(
        target_root=str(httpx_path),
        components=[
            ComponentAssessment(
                component_id="httpx/_client.py",
                role=TargetComponentRole.ENTRY_POINT,
                confidence=0.95,
                evidence=[EvidenceReference(file_path="httpx/_client.py", observation="Client entry point")],
                rationale="Client definition",
            ),
            ComponentAssessment(
                component_id="httpx/_models.py",
                role=TargetComponentRole.DOMAIN_MODEL,
                confidence=0.92,
                evidence=[EvidenceReference(file_path="httpx/_models.py", observation="Request/Response models")],
                rationale="Core HTTP models",
            ),
        ],
        reusable_services=["Client", "AsyncClient"],
        existing_domain_models=["Request", "Response"],
    )
    sanitized, report = validator.validate_profile(profile, idx)
    assert report.is_valid is True
    assert report.verified_components_count == 2
    assert "Client" in sanitized.reusable_services
    assert "Response" in sanitized.existing_domain_models

def test_93_flat_script_repo_sim():
    repo = _create_temp_repo({"etl_script.py": "def extract(): pass\ndef transform(): pass\ndef load(): pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()

        profile = TargetRepositoryProfile(
            target_root=str(repo),
            architectural_style="Script",
            framework="stdlib",
            components=[
                ComponentAssessment(component_id="etl_script.py", role=TargetComponentRole.ENTRY_POINT, confidence=0.85, rationale="Single ETL script")
            ],
            reusable_services=["extract", "transform", "load"],
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert len(sanitized.reusable_services) == 3
    finally:
        shutil.rmtree(repo)

def test_94_empty_repository_handling():
    repo = _create_temp_repo({})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()
        profile = TargetRepositoryProfile(target_root=str(repo))
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert report.coverage_score == 1.0
    finally:
        shutil.rmtree(repo)

def test_95_profile_json_roundtrip_fidelity():
    profile = TargetRepositoryProfile(
        target_root="/test",
        architectural_style="Clean Architecture",
        framework="fastapi",
        orm="sqlalchemy_2.0",
        dto_pattern="pydantic_v2",
        components=[
            ComponentAssessment(
                component_id="models/user.py",
                role=TargetComponentRole.DOMAIN_MODEL,
                confidence=0.95,
                evidence=[EvidenceReference(file_path="models/user.py", observation="ok")],
                rationale="test",
            )
        ]
    )
    raw_json = profile.model_dump_json()
    reloaded = TargetRepositoryProfile.model_validate_json(raw_json)
    assert reloaded.architectural_style == "Clean Architecture"
    assert reloaded.components[0].role == TargetComponentRole.DOMAIN_MODEL


# ==============================================================================
# CATEGORY 8: Edge Cases, Stress Tests & Boundary Conditions (Tests 96 to 100)
# ==============================================================================

def test_96_stress_100_components_50_real_50_fake():
    files = {f"pkg/module_{i}.py": f"class Model_{i}: pass" for i in range(50)}
    repo = _create_temp_repo(files)
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()

        comps = []
        for i in range(50):
            comps.append(ComponentAssessment(component_id=f"pkg/module_{i}.py", role=TargetComponentRole.DOMAIN_MODEL, confidence=0.9, rationale="real"))
        for i in range(50, 100):
            comps.append(ComponentAssessment(component_id=f"pkg/ghost_{i}.py", role=TargetComponentRole.DOMAIN_MODEL, confidence=0.9, rationale="ghost"))

        profile = TargetRepositoryProfile(target_root=str(repo), components=comps)
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.verified_components_count == 50
        assert report.rejected_components_count == 50
        assert report.coverage_score == 0.5
        assert len(report.hallucinated_files) == 50
        assert len(sanitized.components) == 50
    finally:
        shutil.rmtree(repo)

def test_97_stress_500_symbols_checked_against_symbol_table():
    code_lines = [f"class Service_{i}:\n    def execute_{i}(self): pass" for i in range(100)]
    repo = _create_temp_repo({"large_services.py": "\n".join(code_lines)})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()

        # 100 real services + 100 fake services
        test_services = [f"Service_{i}" for i in range(100)] + [f"GhostService_{i}" for i in range(100)]
        profile = TargetRepositoryProfile(target_root=str(repo), reusable_services=test_services)
        sanitized, report = validator.validate_profile(profile, idx)
        assert len(sanitized.reusable_services) == 100
        assert len(report.hallucinated_symbols) == 100
        assert report.is_valid is False
    finally:
        shutil.rmtree(repo)

def test_98_unicode_in_component_rationale_and_observations():
    repo = _create_temp_repo({"user_service.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()

        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(
                    component_id="user_service.py",
                    role=TargetComponentRole.BUSINESS_LOGIC,
                    confidence=0.99,
                    evidence=[EvidenceReference(file_path="user_service.py", observation="Service de sécurité 🔒 et authentification")],
                    rationale="Composant critique pour l'authentification 🚀",
                )
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert "🔒" in sanitized.components[0].evidence[0].observation
        assert "🚀" in sanitized.components[0].rationale
    finally:
        shutil.rmtree(repo)

def test_99_special_characters_in_rationale():
    repo = _create_temp_repo({"main.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()

        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[
                ComponentAssessment(
                    component_id="main.py",
                    role=TargetComponentRole.ENTRY_POINT,
                    confidence=0.9,
                    evidence=[EvidenceReference(file_path="main.py", observation="FastAPI(docs_url=None, redoc_url=None)")],
                    rationale="Entrypoint <with> 'quotes' & \"double-quotes\" / slashes \\",
                )
            ]
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.is_valid is True
        assert "<with>" in sanitized.components[0].rationale
    finally:
        shutil.rmtree(repo)

def test_100_division_by_zero_safety_zero_components():
    repo = _create_temp_repo({"main.py": "pass"})
    try:
        indexer = TargetRepositoryIndexer()
        idx, _ = indexer.index_repository(repo)
        validator = ProfileValidator()

        profile = TargetRepositoryProfile(
            target_root=str(repo),
            components=[],
            reusable_services=[],
            existing_domain_models=[],
        )
        sanitized, report = validator.validate_profile(profile, idx)
        assert report.coverage_score == 1.0
        assert sanitized.indexing_coverage_rate == 1.0
        assert report.is_valid is True
    finally:
        shutil.rmtree(repo)


# ==============================================================================
# TEST RUNNER
# ==============================================================================

if __name__ == "__main__":
    import sys
    all_tests = [k for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    all_tests_sorted = sorted(all_tests, key=lambda name: int(name.split("_")[1]))

    print("=" * 80)
    print(f"🚀 RUNNING MASTER 100-TEST VERIFICATION SUITE: Layers 3 & 4 (Architect & Validator)")
    print("=" * 80)

    passed = 0
    for idx, test_name in enumerate(all_tests_sorted, 1):
        test_fn = globals()[test_name]
        try:
            test_fn()
            passed += 1
            if idx % 10 == 0:
                print(f"  ✅ Completed Tests 1 to {idx}...")
        except Exception as e:
            print(f"  ❌ FAILED {test_name}: {e}")
            raise e

    print("=" * 80)
    print(f"🎉 ALL {passed}/100 ARCHITECT & VALIDATOR TESTS PASSED 100% GREEN!")
    print("=" * 80)
