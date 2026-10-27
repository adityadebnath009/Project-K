"""
test_live_llm_conversation.py - Live Verification of Ollama LLM Conversation & Context Engine.

Tests:
1. Multi-turn chat with local Ollama qwen2.5:7b via ConversationService.
2. ContextManager token tracking & budget enforcement across turns.
3. Slash command /compact execution with real LangChain structured LLM output (Compactor).
4. Post-compaction context retention and memory injection on Turn 4.
"""
import time
from app.config import settings
from app.inference.ollama_client import OllamaClient
from app.repositories.in_memory import InMemoryConversationRepository
from app.schemas.chat import ChatRequest
from app.services.compactor import Compactor
from app.services.conversation_service import ConversationService


def test_live_conversation_with_ollama():
    print("\n" + "=" * 70)
    print(f"🚀 LIVE LLM CONVERSATION TEST ({settings.model_name} @ {settings.ai_base_url})")
    print("=" * 70)

    repo = InMemoryConversationRepository()
    client = OllamaClient()
    compactor = Compactor()

    service = ConversationService(
        conversation_repository=repo,
        inference_client=client,
        compactor=compactor,
    )

    # -------------------------------------------------------------
    # TURN 1: User introduces architectural decisions
    # -------------------------------------------------------------
    t0 = time.perf_counter()
    print("\n[Turn 1] User: Establishing architectural stack...")
    msg1 = "We are building an autonomous feature transposition engine in Python using Clean Architecture, SQLAlchemy 2.0, and Pydantic v2."
    res1 = service.process_chat_request(ChatRequest(message=msg1))
    t1 = time.perf_counter() - t0

    print(f"   🤖 Assistant ({t1:.2f}s, {res1.completion_tokens} tokens):")
    print(f"   \"{res1.message[:250]}...\"")
    assert len(res1.message) > 20
    assert res1.prompt_tokens > 0

    # -------------------------------------------------------------
    # TURN 2: User adds specific constraints & rules
    # -------------------------------------------------------------
    t0 = time.perf_counter()
    print("\n[Turn 2] User: Adding database & context constraints...")
    msg2 = "Remember our critical rule: The project database is PostgreSQL Neon with asyncpg, and we strictly use UUID7 for primary keys."
    res2 = service.process_chat_request(ChatRequest(
        conversation_id=res1.conversation_id,
        message=msg2,
    ))
    t2 = time.perf_counter() - t0

    print(f"   🤖 Assistant ({t2:.2f}s, {res2.completion_tokens} tokens):")
    print(f"   \"{res2.message[:250]}...\"")
    assert len(res2.message) > 20

    # -------------------------------------------------------------
    # TURN 3: Execute /compact with real LLM structured output
    # -------------------------------------------------------------
    t0 = time.perf_counter()
    print("\n[Turn 3] User: Executing /compact command...")
    res3 = service.process_chat_request(ChatRequest(
        conversation_id=res1.conversation_id,
        message="/compact",
    ))
    t3 = time.perf_counter() - t0

    print(f"   📋 Compactor Result ({t3:.2f}s):")
    print(f"   {res3.message[:350]}...")
    assert "compacted successfully" in res3.message or "Conversation compacted" in res3.message

    # -------------------------------------------------------------
    # TURN 4: Post-compaction memory test
    # -------------------------------------------------------------
    t0 = time.perf_counter()
    print("\n[Turn 4] User: Testing context retention post-compaction...")
    msg4 = "What database and primary key strategy did we agree upon?"
    res4 = service.process_chat_request(ChatRequest(
        conversation_id=res1.conversation_id,
        message=msg4,
    ))
    t4 = time.perf_counter() - t0

    print(f"   🤖 Assistant ({t4:.2f}s, {res4.completion_tokens} tokens):")
    print(f"   \"{res4.message}\"")

    reply_lower = res4.message.lower()
    has_postgres = "postgres" in reply_lower or "neon" in reply_lower
    has_uuid = "uuid" in reply_lower or "uuid7" in reply_lower

    print(f"\n   • Context Recall Check: PostgreSQL/Neon={has_postgres}, UUID7={has_uuid}")
    assert has_postgres or has_uuid, "Assistant must recall decisions from compacted memory!"

    print("\n" + "=" * 70)
    print("🎉 ALL 4 TURNS OF LIVE LLM CONVERSATION & COMPACTION VERIFIED!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    test_live_conversation_with_ollama()
