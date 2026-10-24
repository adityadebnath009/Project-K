"""
app/test/test_target_architect_validator.py - Verification suite for Phase 7A Layers 3 & 4.
"""
from pathlib import Path

from app.schemas.transposition import (
    ComponentAssessment,
    EvidenceReference,
    TargetComponentRole,
    TargetEvidenceManifest,
    TargetRepositoryProfile,
)
from app.transposition.profile_validator import ProfileValidator
from app.transposition.target_architect import TargetArchitect
from app.transposition.target_indexer import TargetRepositoryIndexer


def test_validator_accepts_valid_components():
    indexer = TargetRepositoryIndexer()
    idx, _ = indexer.index_repository(Path("app").resolve())
    validator = ProfileValidator()

    profile = TargetRepositoryProfile(
        target_root=str(Path("app").resolve()),
        architectural_style="Clean Architecture",
        components=[
            ComponentAssessment(
                component_id="entities/user.py",
                role=TargetComponentRole.DOMAIN_MODEL,
                confidence=0.95,
                evidence=[EvidenceReference(file_path="entities/user.py", observation="User entity")],
                rationale="Real User entity",
            )
        ],
        reusable_services=["PostgresUserRepository"],
        existing_domain_models=["User"],
    )

    sanitized, report = validator.validate_profile(profile, idx)
    assert report.is_valid is True
    assert report.verified_components_count == 1
    assert report.rejected_components_count == 0
    assert report.coverage_score == 1.0
    assert len(sanitized.components) == 1
    assert sanitized.reusable_services == ["PostgresUserRepository"]
    assert sanitized.existing_domain_models == ["User"]


def test_validator_rejects_hallucinated_component_file():
    indexer = TargetRepositoryIndexer()
    idx, _ = indexer.index_repository(Path("app").resolve())
    validator = ProfileValidator()

    profile = TargetRepositoryProfile(
        target_root=str(Path("app").resolve()),
        components=[
            ComponentAssessment(
                component_id="non_existent/fake_service.py",
                role=TargetComponentRole.BUSINESS_LOGIC,
                confidence=0.9,
                evidence=[EvidenceReference(file_path="non_existent/fake_service.py", observation="Fake")],
                rationale="Non-existent service",
            )
        ],
    )

    sanitized, report = validator.validate_profile(profile, idx)
    assert report.is_valid is False
    assert report.verified_components_count == 0
    assert report.rejected_components_count == 1
    assert "non_existent/fake_service.py" in report.hallucinated_files
    assert len(sanitized.components) == 0
    assert any("Hallucination Warning" in q for q in sanitized.unresolved_questions)


def test_validator_strips_hallucinated_evidence_from_valid_component():
    indexer = TargetRepositoryIndexer()
    idx, _ = indexer.index_repository(Path("app").resolve())
    validator = ProfileValidator()

    profile = TargetRepositoryProfile(
        target_root=str(Path("app").resolve()),
        components=[
            ComponentAssessment(
                component_id="entities/user.py",
                role=TargetComponentRole.DOMAIN_MODEL,
                confidence=0.95,
                evidence=[
                    EvidenceReference(file_path="entities/user.py", observation="Real file"),
                    EvidenceReference(file_path="entities/ghost.py", observation="Ghost file"),
                ],
                rationale="User entity with one ghost evidence",
            )
        ],
    )

    sanitized, report = validator.validate_profile(profile, idx)
    assert report.verified_components_count == 1
    assert "entities/ghost.py" in report.hallucinated_files
    # Ghost evidence was stripped, real evidence kept
    assert len(sanitized.components[0].evidence) == 1
    assert sanitized.components[0].evidence[0].file_path == "entities/user.py"


def test_validator_filters_fake_symbols():
    indexer = TargetRepositoryIndexer()
    idx, _ = indexer.index_repository(Path("app").resolve())
    validator = ProfileValidator()

    profile = TargetRepositoryProfile(
        target_root=str(Path("app").resolve()),
        reusable_services=["PostgresUserRepository", "ImaginaryPaymentService"],
        existing_domain_models=["User", "ImaginaryLedgerModel"],
    )

    sanitized, report = validator.validate_profile(profile, idx)
    assert report.is_valid is False
    assert "ImaginaryPaymentService" in report.hallucinated_symbols
    assert "ImaginaryLedgerModel" in report.hallucinated_symbols
    assert sanitized.reusable_services == ["PostgresUserRepository"]
    assert sanitized.existing_domain_models == ["User"]


def test_validator_empty_profile_is_valid():
    indexer = TargetRepositoryIndexer()
    idx, _ = indexer.index_repository(Path("app").resolve())
    validator = ProfileValidator()

    profile = TargetRepositoryProfile(target_root=str(Path("app").resolve()))
    sanitized, report = validator.validate_profile(profile, idx)
    assert report.is_valid is True
    assert report.coverage_score == 1.0


def test_architect_formats_manifest_prompt_correctly():
    manifest = TargetEvidenceManifest(
        target_root="/test/root",
        total_files_scanned=10,
        files_indexed_count=10,
        parse_error_count=0,
        declared_dependencies=["fastapi", "pydantic"],
        inheritance_map={"models.py:User": ["BaseModel"]},
        decorators_by_symbol={"api.py:get_user": ["router.get"]},
        imports_by_file={"api.py": ["fastapi", "models"]},
        total_call_edges=20,
        resolved_internal_calls=15,
        unresolved_calls=5,
        call_resolution_rate=0.75,
    )

    class CaptureStructuredLLM:
        def __init__(self):
            self.captured_messages = None

        def invoke(self, messages):
            self.captured_messages = messages
            return TargetRepositoryProfile(
                target_root="/test/root",
                architectural_style="Clean Architecture",
                framework="fastapi",
            )

    architect = TargetArchitect(llm=None)
    mock_llm = CaptureStructuredLLM()
    architect.structured_llm = mock_llm

    profile = architect.analyze_manifest(manifest)
    assert profile.architectural_style == "Clean Architecture"
    assert mock_llm.captured_messages is not None
    user_prompt = mock_llm.captured_messages[1].content
    assert "fastapi" in user_prompt
    assert "BaseModel" in user_prompt
    assert "router.get" in user_prompt


if __name__ == "__main__":
    test_validator_accepts_valid_components()
    test_validator_rejects_hallucinated_component_file()
    test_validator_strips_hallucinated_evidence_from_valid_component()
    test_validator_filters_fake_symbols()
    test_validator_empty_profile_is_valid()
    test_architect_formats_manifest_prompt_correctly()
    print("\n🎉 ALL ARCHITECT & VALIDATOR UNIT TESTS PASSED 100% GREEN!")
