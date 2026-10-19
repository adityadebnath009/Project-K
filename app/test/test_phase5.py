import uuid
from typing import Any

from app.repositories.postgres_conversation import PostgresConversationRepository
from app.repositories.postgres_memory import PostgresMemoryRepository
from app.repositories.postgres_project import PostgresProjectRepository
from app.repositories.postgres_user import PostgresUserRepository
from app.schemas.chat import ChatRequest
from app.schemas.memory import ExtractedMemoryPackage, MemoryItem
from app.services.conversation_service import ConversationService
from app.services.memory_service import MemoryService
from app.services.token_counter import TokenCounter
from app.services.user_service import UserService


class MockInferenceClient:
    """Predictable mock client for deterministic generation."""
    def generate(self, messages: list[dict[str, Any]], system_prompt: str | None = None) -> str:
        last_msg = messages[-1]["content"]
        return f"Echo answer to: {last_msg}"


class MockCompactor:
    """Mock compactor producing a deterministic summary."""
    def compact_history(self, history: list[dict[str, Any]], existing_summary: str | None = None):
        from app.schemas.summary import CompactionSummary
        return CompactionSummary(
            executive_summary="Developer established Java background and Neon stack.",
            key_decisions=["Use Clean Architecture", "Use Neon PostgreSQL"],
            unresolved_tasks=["Implement Phase 5"],
            context_notes=["Strict token budgeting"],
        )


class MockMemoryExtractor:
    """Mock extractor simulating structured LLM output with zero network delay."""
    def extract_memories(
        self,
        history: list[dict[str, Any]],
        existing_user_profile: str | None = None,
        existing_project_context: str | None = None,
    ) -> ExtractedMemoryPackage:
        return ExtractedMemoryPackage(
            user_facts=[
                MemoryItem(key="role", value="Senior Java Backend Engineer", category="role"),
                MemoryItem(key="guidance_style", value="Provide step-by-step guidance", category="preference"),
            ],
            project_facts=[
                MemoryItem(key="primary_language", value="Python 3.14", category="tech_stack"),
                MemoryItem(key="database", value="Neon Cloud PostgreSQL", category="tech_stack"),
            ],
        )


def test_project_and_memory_persistence():
    """Verify Project and Memory atomic persistence and upserts in Neon PostgreSQL."""
    user_repo = PostgresUserRepository()
    user_service = UserService(user_repo)
    user = user_service.register_user()

    test_uid = uuid.uuid4().hex[:8]
    test_path = f"/tmp/test_workspace_{test_uid}"

    proj_repo = PostgresProjectRepository()
    project = proj_repo.get_or_create_project(
        user_id=user.id,
        name=f"FeatureForge-{test_uid}",
        root_path=test_path,
        description="Test project for Phase 5",
    )
    assert project.id is not None
    assert project.name == f"FeatureForge-{test_uid}"

    # Idempotent lookup
    same_project = proj_repo.get_or_create_project(
        user_id=user.id,
        name=f"FeatureForge-{test_uid}",
        root_path=test_path,
    )
    assert same_project.id == project.id

    # Memory upsert
    mem_repo = PostgresMemoryRepository()
    pkg = ExtractedMemoryPackage(
        user_facts=[MemoryItem(key="editor", value="VSCode", category="tooling")],
        project_facts=[MemoryItem(key="framework", value="SQLAlchemy", category="tech_stack")],
    )
    u_count, p_count = mem_repo.save_extracted_package(user.id, project.id, pkg)
    assert u_count == 1
    assert p_count == 1

    # Atomic update on conflict (same key, updated value)
    pkg_updated = ExtractedMemoryPackage(
        user_facts=[MemoryItem(key="editor", value="Cursor", category="tooling")],
        project_facts=[],
    )
    mem_repo.save_extracted_package(user.id, project.id, pkg_updated)

    profile = mem_repo.get_user_profile(user.id)
    editor_fact = next(m for m in profile.memories if m.key == "editor")
    assert editor_fact.value == "Cursor"  # In-place updated!

    print("✅ Test 1 Passed: Project & Memory atomic persistence and upsert verified in Neon!")
    return user.id, project.id


def test_token_budget_packing():
    """Verify that MemoryService strictly bounds facts within token limits."""
    class FakeMemoryRepo:
        def get_user_profile(self, user_id: str):
            from app.schemas.memory import UserProfileDTO
            # Create 30 facts (~500 tokens, far exceeding the 150 token budget)
            facts = [
                MemoryItem(key=f"custom_rule_{i}", value=f"Always apply rule number {i} with care", category="rules")
                for i in range(30)
            ]
            return UserProfileDTO(user_id=user_id, memories=facts)

    ms = MemoryService(memory_repository=FakeMemoryRepo(), token_counter=TokenCounter())
    context_str = ms.get_user_profile_context(user_id="any-user", max_tokens=150)

    assert context_str is not None
    assert context_str.startswith("<user_profile>")
    assert context_str.endswith("</user_profile>")

    tc = TokenCounter()
    tokens_used = tc.count_tokens(context_str)
    assert tokens_used <= 150, f"Expected <= 150 tokens, got {tokens_used}"
    print(f"✅ Test 2 Passed: Deterministic memory budget packing constrained to {tokens_used}/150 tokens!")


def test_cross_session_recall(user_id: str, project_id: str):
    """
    Verify the ultimate Phase 5 invariant:
    Session 1 compacts memories -> Session 2 (brand new conversation) immediately recalls them!
    """
    conv_repo = PostgresConversationRepository()
    proj_repo = PostgresProjectRepository()
    mem_repo = PostgresMemoryRepository()
    mem_service = MemoryService(memory_repository=mem_repo)

    service = ConversationService(
        conversation_repository=conv_repo,
        inference_client=MockInferenceClient(),
        compactor=MockCompactor(),
        memory_service=mem_service,
        memory_extractor=MockMemoryExtractor(),
        project_repository=proj_repo,
    )

    # ─── SESSION 1: Establish identity and compact ───
    req1 = ChatRequest(
        user_id=user_id,
        project_id=project_id,
        message="Hello! I am a Senior Java Backend Engineer, and this project uses Python 3.14 on Neon.",
    )
    res1 = service.process_chat_request(req1)
    conv1_id = res1.conversation_id

    # User invokes /compact
    compact_req = ChatRequest(
        conversation_id=conv1_id,
        user_id=user_id,
        project_id=project_id,
        message="/compact",
    )
    compact_res = service.process_chat_request(compact_req)
    assert "Memories updated: 2 user facts, 2 project facts" in compact_res.message

    # ─── SESSION 2: Brand new conversation, zero history ───
    req2 = ChatRequest(
        conversation_id=None,  # Brand new conversation!
        user_id=user_id,
        project_id=project_id,
        message="What is our tech stack and how should you explain things to me?",
    )

    # We inspect context package built inside service
    user_profile = mem_service.get_user_profile_context(user_id=user_id)
    project_context = mem_service.get_project_memory_context(project_id=project_id)

    assert user_profile is not None
    assert "Senior Java Backend Engineer" in user_profile
    assert project_context is not None
    assert "Neon Cloud PostgreSQL" in project_context

    res2 = service.process_chat_request(req2)
    assert res2.conversation_id != conv1_id  # Completely separate session

    print("✅ Test 3 Passed: Cross-Session Recall verified! Persona and Project Context survived session boundaries!")


if __name__ == "__main__":
    print("\n🚀 Running Phase 5 Hierarchical Memory Verification Suite (Neon Cloud)...\n")
    user_id, project_id = test_project_and_memory_persistence()
    test_token_budget_packing()
    test_cross_session_recall(user_id, project_id)
    print("\n🎉 ALL PHASE 5 TESTS PASSED!\n")
