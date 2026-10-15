from typing import Any
from app.repositories.in_memory import InMemoryConversationRepository
from app.schemas.chat import ChatRequest
from app.services.context_manager import ContextBudgetExceededError, ContextManager
from app.services.conversation_service import ConversationService
from app.services.token_counter import TokenCounter


class MockInferenceClient:
    """Mock client for deterministic testing without needing Ollama running."""
    def generate(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str | None = None,
    ) -> str:
        last_user_msg = messages[-1]["content"]
        return f"Echo answer to: {last_user_msg}"


def test_turn_aware_atomic_selection():
    """Verify complete (User, Assistant) pairs are preserved and never split."""
    cm = ContextManager()

    history = [
        {"role": "user", "content": "Question 1"},
        {"role": "assistant", "content": "Answer 1"},
        {"role": "user", "content": "Question 2"},
        {"role": "assistant", "content": "Answer 2"},
        {"role": "user", "content": "Question 3"},
        {"role": "assistant", "content": "Answer 3"},
    ]

    # Calculate tokens of a single turn (~25 tokens)
    # Give budget enough for system prompt + Turn 2 and Turn 3, but NOT Turn 1
    tight_budget = 45

    pkg = cm.build_context(
        conversation_id="test-conv",
        user_id="test-user",
        history=history,
        system_prompt="Short prompt",
        max_budget=tight_budget,
    )

    assert pkg.estimated_input_tokens <= tight_budget
    assert pkg.is_compacted is True

    # First message must be system
    assert pkg.messages[0]["role"] == "system"

    # Turn 1 must be excluded, Turn 2 & 3 must be fully included
    contents = [m["content"] for m in pkg.messages]
    assert "Question 1" not in contents
    assert "Answer 1" not in contents
    assert "Question 2" in contents
    assert "Answer 2" in contents
    assert "Question 3" in contents
    assert "Answer 3" in contents
    print("✅ Test 1 Passed: Turn-aware atomic selection works perfectly!")


def test_strict_token_budget_enforcement():
    """Verify that an intentionally massive history never exceeds the budget."""
    cm = ContextManager()

    # Create a massive history of 50 turns (thousands of tokens)
    massive_history = []
    for i in range(50):
        massive_history.append({"role": "user", "content": f"User long message {i} " * 20})
        massive_history.append({"role": "assistant", "content": f"AI detailed answer {i} " * 20})

    budget = 1000
    pkg = cm.build_context(
        conversation_id="conv-massive",
        user_id="user-massive",
        history=massive_history,
        max_budget=budget,
    )

    assert pkg.estimated_input_tokens <= budget
    assert pkg.is_compacted is True
    print(f"✅ Test 2 Passed: Massive history constrained to {pkg.estimated_input_tokens}/{budget} tokens!")


def test_oversized_system_prompt_guard():
    """Verify that an impossible prompt raises ContextBudgetExceededError."""
    cm = ContextManager()
    oversized_prompt = "Super long system instructions " * 100  # Hundreds of tokens

    try:
        cm.build_context(
            conversation_id="conv-fail",
            user_id="user-fail",
            history=[],
            system_prompt=oversized_prompt,
            max_budget=50,  # Impossible budget
        )
        assert False, "Should have raised ContextBudgetExceededError"
    except ContextBudgetExceededError:
        print("✅ Test 3 Passed: Oversized prompt guard successfully caught!")


def test_end_to_end_conversation_service():
    """Verify multi-turn conversation flow through ConversationService."""
    repo = InMemoryConversationRepository()
    client = MockInferenceClient()
    service = ConversationService(
        conversation_repository=repo,
        inference_client=client,
    )

    # Turn 1
    req1 = ChatRequest(message="What is Python?")
    res1 = service.process_chat_request(req1)
    assert res1.message == "Echo answer to: What is Python?"

    # Turn 2
    req2 = ChatRequest(conversation_id=res1.conversation_id, message="Explain lists.")
    res2 = service.process_chat_request(req2)
    assert res2.conversation_id == res1.conversation_id
    assert res2.message == "Echo answer to: Explain lists."

    # Verify 4 messages recorded in repo
    msgs = repo.get_messages(res1.conversation_id)
    assert len(msgs) == 4
    assert msgs[0]["sequence_number"] == 1
    assert msgs[3]["sequence_number"] == 4
    print("✅ Test 4 Passed: End-to-end ConversationService works smoothly!")


if __name__ == "__main__":
    print("\n🚀 Running Phase 2 Verification Test Suite...\n")
    test_turn_aware_atomic_selection()
    test_strict_token_budget_enforcement()
    test_oversized_system_prompt_guard()
    test_end_to_end_conversation_service()
    print("\n🎉 ALL PHASE 2 TESTS PASSED!\n")
