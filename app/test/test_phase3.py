from typing import Any

from app.repositories.in_memory import InMemoryConversationRepository
from app.schemas.chat import ChatRequest
from app.schemas.summary import CompactionSummary
from app.services.conversation_service import ConversationService


class MockInferenceClient:
    """Captures messages received for prompt inspection."""
    def __init__(self):
        self.last_messages: list[dict[str, Any]] = []

    def generate(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str | None = None,
    ) -> str:
        self.last_messages = messages
        last_user_msg = messages[-1]["content"]
        return f"Echo answer to: {last_user_msg}"


class MockCompactor:
    """Predictable mock compactor returning a structured operational ledger."""
    def compact_history(
        self,
        history: list[dict[str, Any]],
        existing_summary: str | None = None,
    ) -> CompactionSummary:
        return CompactionSummary(
            primary_goal="Build a high-performance Java microservice",
            key_decisions=["Use PostgreSQL with Spring Data JPA", "Enforce strict clean architecture"],
            constraints=["Input budget equation: I = C - O - S"],
            files_and_artifacts=["pom.xml", "ConversationService.java"],
            completed_tasks=["Initialized Maven project", "Configured database entities"],
            pending_tasks=["Implement history compaction endpoint"],
        )


def test_compaction_summary_markdown():
    """Verify CompactionSummary renders markdown cleanly."""
    summary = CompactionSummary(
        primary_goal="Build AI Memory Engine",
        key_decisions=["Use LangChain structured output"],
        constraints=["Max 6392 tokens input"],
        files_and_artifacts=["compactor.py"],
        completed_tasks=["Phase 1", "Phase 2"],
        pending_tasks=["Phase 3 verification"],
    )
    context_str = summary.to_context_string()

    assert "### [COMPACTED OPERATIONAL STATE]" in context_str
    assert "**Goal**: Build AI Memory Engine" in context_str
    assert "- Use LangChain structured output" in context_str
    assert "- Max 6392 tokens input" in context_str
    assert "- compactor.py" in context_str
    print("✅ Test 1 Passed: CompactionSummary markdown generation is formatted properly!")


def test_repository_versioned_summaries():
    """Verify repository increments summary versions and tracks sequence numbers."""
    repo = InMemoryConversationRepository()
    conv_id = repo.get_or_create_conversation(None, "user-1")

    # Add 2 messages (sequence 1 and 2)
    repo.append_message(conv_id, "user", "Hello")
    repo.append_message(conv_id, "assistant", "Hi there")

    # Save version 1
    s1 = repo.save_summary(conv_id, "Summary V1", last_covered_sequence_number=2)
    assert s1["version"] == 1
    assert s1["last_covered_sequence_number"] == 2

    # Add 2 more messages (sequence 3 and 4)
    repo.append_message(conv_id, "user", "Add DB layer")
    repo.append_message(conv_id, "assistant", "Done")

    # Save version 2
    s2 = repo.save_summary(conv_id, "Summary V2", last_covered_sequence_number=4)
    assert s2["version"] == 2
    assert s2["last_covered_sequence_number"] == 4

    # Verify latest returns version 2
    latest = repo.get_latest_summary(conv_id)
    assert latest is not None
    assert latest["version"] == 2
    assert latest["summary_content"] == "Summary V2"
    print("✅ Test 2 Passed: Repository versioned summaries work monotonically!")


def test_compact_command_and_context_injection():
    """Verify the /compact command triggers compaction and injects summary into subsequent turns."""
    repo = InMemoryConversationRepository()
    client = MockInferenceClient()
    mock_compactor = MockCompactor()

    service = ConversationService(
        conversation_repository=repo,
        inference_client=client,
        compactor=mock_compactor,
    )

    # Turn 1: Normal conversation
    req1 = ChatRequest(message="We are designing a Spring Boot backend.")
    res1 = service.process_chat_request(req1)
    conv_id = res1.conversation_id

    # Turn 2: Another exchange
    req2 = ChatRequest(conversation_id=conv_id, message="Let's use PostgreSQL.")
    res2 = service.process_chat_request(req2)

    # 4 messages in history so far
    assert len(repo.get_messages(conv_id)) == 4

    # Trigger /compact command
    compact_req = ChatRequest(conversation_id=conv_id, message="/compact")
    compact_res = service.process_chat_request(compact_req)

    assert "Conversation compacted successfully (version 1)" in compact_res.message
    assert "[COMPACTED OPERATIONAL STATE]" in compact_res.message

    # Verify summary is persisted in repo
    latest_summary = repo.get_latest_summary(conv_id)
    assert latest_summary is not None
    assert latest_summary["version"] == 1
    assert latest_summary["last_covered_sequence_number"] == 4

    # Notice: /compact control command was not added, but the assistant's ack response is persisted
    assert len(repo.get_messages(conv_id)) == 5

    # Turn 3: Post-compaction conversation turn
    req3 = ChatRequest(conversation_id=conv_id, message="What architecture did we choose?")
    service.process_chat_request(req3)

    # Inspect the prompt messages sent to the LLM
    llm_messages = client.last_messages

    # Message 0: Default System Prompt
    assert llm_messages[0]["role"] == "system"

    # Message 1: The Compacted Operational State (Injected as second system message)
    assert llm_messages[1]["role"] == "system"
    assert "### [COMPACTED OPERATIONAL STATE]" in llm_messages[1]["content"]
    assert "Build a high-performance Java microservice" in llm_messages[1]["content"]

    # Subsequent messages: The conversation turns
    roles = [m["role"] for m in llm_messages[2:]]
    assert "user" in roles
    assert "assistant" in roles
    assert llm_messages[-1]["content"] == "What architecture did we choose?"

    print("✅ Test 3 Passed: /compact workflow & summary context injection verified end-to-end!")


def test_compactor_with_inference_client():
    """Verify Compactor supports custom InferenceClient without AttributeError."""
    import json
    from app.inference.ollama_client import OllamaClient
    from app.services.compactor import Compactor

    # 1. Initialization check
    compactor_ollama = Compactor(llm=OllamaClient())
    assert compactor_ollama.structured_llm is None

    # 2. Functional compaction check via InferenceClient generate()
    class MockClient:
        def generate(self, messages, system_prompt=None):
            payload = {
                "primary_goal": "Migrate Redis queue to Celery",
                "key_decisions": ["Use RabbitMQ broker"],
                "constraints": ["Zero downtime"],
                "files_and_artifacts": ["tasks.py"],
                "completed_tasks": ["Setup broker"],
                "pending_tasks": ["Migrate workers"],
            }
            return "```json\n" + json.dumps(payload) + "\n```"

    compactor = Compactor(llm=MockClient())
    summary = compactor.compact_history([
        {"role": "user", "content": "How do we migrate to Celery?"},
        {"role": "assistant", "content": "We can use RabbitMQ as broker."},
    ])

    assert isinstance(summary, CompactionSummary)
    assert summary.primary_goal == "Migrate Redis queue to Celery"
    assert "Use RabbitMQ broker" in summary.key_decisions
    print("✅ Test 4 Passed: Compactor handles InferenceClient and Markdown JSON cleanly!")


if __name__ == "__main__":
    print("\n🚀 Running Phase 3 Verification Test Suite...\n")
    test_compaction_summary_markdown()
    test_repository_versioned_summaries()
    test_compact_command_and_context_injection()
    test_compactor_with_inference_client()
    print("\n🎉 ALL PHASE 3 TESTS PASSED!\n")
