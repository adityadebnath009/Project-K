import uuid
from typing import Any

from app.exceptions.user_not_found_error import UserNotFoundError
from app.repositories.postgres_conversation import PostgresConversationRepository
from app.repositories.postgres_user import PostgresUserRepository
from app.schemas.chat import ChatRequest
from app.services.conversation_service import ConversationService
from app.services.user_service import UserService


class MockInferenceClient:
    """Predictable mock client for fast, deterministic persistence testing."""
    def generate(self, messages: list[dict[str, Any]], system_prompt: str | None = None) -> str:
        last_msg = messages[-1]["content"]
        return f"Echo answer to: {last_msg}"


def test_user_service_and_repository():
    """Verify User registration, lookup, and current_user resolution."""
    user_repo = PostgresUserRepository()
    user_service = UserService(user_repo)

    # 1. Register a new user
    user = user_service.register_user()
    assert user.id is not None
    assert user_repo.user_exists(user.id) is True

    # 2. Lookup existing user
    fetched = user_service.get_user(user.id)
    assert fetched.id == user.id

    # 3. Non-existent user throws UserNotFoundError
    try:
        user_service.get_user(str(uuid.uuid7()))
        assert False, "Should have raised UserNotFoundError"
    except UserNotFoundError:
        pass

    print("✅ Test 1 Passed: UserService & PostgresUserRepository work properly!")
    return user.id


def test_conversation_persistence_and_auth_boundary(user_id: str):
    """Verify conversations enforce user existence and cross-user security."""
    user_repo = PostgresUserRepository()
    conv_repo = PostgresConversationRepository(user_repository=user_repo)

    # 1. Non-existent user should be rejected
    fake_user_id = str(uuid.uuid7())
    try:
        conv_repo.get_or_create_conversation(None, fake_user_id)
        assert False, "Should have raised UserNotFoundError"
    except UserNotFoundError:
        pass

    # 2. Registered user creates a conversation
    conv_id = conv_repo.get_or_create_conversation(None, user_id)
    assert conv_repo.conversation_exists(conv_id) is True

    # 3. Another user attempting to access this conversation is rejected
    user2 = user_repo.create_user()
    try:
        conv_repo.get_or_create_conversation(conv_id, user2.id)
        assert False, "Should have raised PermissionError"
    except PermissionError:
        pass

    print("✅ Test 2 Passed: Auth boundary and cross-user isolation verified!")
    return conv_id


def test_messages_and_sequence_monotonicity(conv_id: str):
    """Verify message persistence and atomic per-conversation sequence numbering."""
    conv_repo = PostgresConversationRepository()

    # Append 3 messages
    m1 = conv_repo.append_message(conv_id, "user", "Message 1")
    assert m1["sequence_number"] == 1

    m2 = conv_repo.append_message(conv_id, "assistant", "Answer 1")
    assert m2["sequence_number"] == 2

    m3 = conv_repo.append_message(conv_id, "user", "Message 2")
    assert m3["sequence_number"] == 3

    # Fetch messages
    messages = conv_repo.get_messages(conv_id)
    assert len(messages) >= 3
    assert messages[0]["sequence_number"] == 1
    assert messages[1]["sequence_number"] == 2
    assert messages[2]["sequence_number"] == 3

    # Test limit
    last_two = conv_repo.get_messages(conv_id, limit=2)
    assert len(last_two) == 2
    assert last_two[0]["sequence_number"] == 2
    assert last_two[1]["sequence_number"] == 3

    print("✅ Test 3 Passed: Messages and monotonic sequence numbers verified!")


def test_versioned_summaries(conv_id: str):
    """Verify versioned operational ledgers increment monotonically in Neon."""
    conv_repo = PostgresConversationRepository()

    # Save summary version 1
    s1 = conv_repo.save_summary(conv_id, "Ledger V1", last_covered_sequence_number=2)
    assert s1["version"] == 1
    assert s1["last_covered_sequence_number"] == 2

    # Save summary version 2
    s2 = conv_repo.save_summary(conv_id, "Ledger V2", last_covered_sequence_number=3)
    assert s2["version"] == 2
    assert s2["last_covered_sequence_number"] == 3

    # Latest summary must be version 2
    latest = conv_repo.get_latest_summary(conv_id)
    assert latest is not None
    assert latest["version"] == 2
    assert latest["summary_content"] == "Ledger V2"

    print("✅ Test 4 Passed: Versioned summaries (v1 -> v2) verified in PostgreSQL!")


def test_end_to_end_conversation_service_with_postgres():
    """Verify full chat loop through ConversationService backed by PostgreSQL."""
    user_repo = PostgresUserRepository()
    user_service = UserService(user_repo)
    user = user_service.get_current_user("default_user")

    conv_repo = PostgresConversationRepository(user_repository=user_repo)
    service = ConversationService(
        conversation_repository=conv_repo,
        inference_client=MockInferenceClient(),
    )

    req = ChatRequest(user_id=user.id, message="Hello Neon PostgreSQL!")
    res = service.process_chat_request(req)

    assert res.conversation_id is not None
    assert res.message == "Echo answer to: Hello Neon PostgreSQL!"

    # Verify message was stored in Neon
    messages = conv_repo.get_messages(res.conversation_id)
    assert len(messages) == 2  # 1 user + 1 assistant
    assert messages[0]["content"] == "Hello Neon PostgreSQL!"
    assert messages[1]["content"] == "Echo answer to: Hello Neon PostgreSQL!"

    print("✅ Test 5 Passed: End-to-end chat turn persisted to Neon PostgreSQL successfully!")


if __name__ == "__main__":
    print("\n🚀 Running Phase 4 Persistence Verification Suite (Neon Cloud)...\n")
    user_id = test_user_service_and_repository()
    conv_id = test_conversation_persistence_and_auth_boundary(user_id)
    test_messages_and_sequence_monotonicity(conv_id)
    test_versioned_summaries(conv_id)
    test_end_to_end_conversation_service_with_postgres()
    print("\n🎉 ALL PHASE 4 PERSISTENCE TESTS PASSED!\n")
