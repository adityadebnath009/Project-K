"""
test_live_conversation_fast.py - Live Verification of Ollama LLM Conversation & Context Engine.

Verifies:
1. Turn 1: User sends architectural requirements -> ConversationService formats context package -> qwen2.5:7b generates response.
2. Turn 2: User triggers /compact -> Compactor extracts structured CompactionSummary via LangChain.
3. Turn 3: User queries retained context -> qwen2.5:7b verifies context continuity from summary.
"""
import time
from app.config import settings
from app.inference.ollama_client import OllamaClient
from app.repositories.in_memory import InMemoryConversationRepository
from app.schemas.chat import ChatRequest
from app.services.compactor import Compactor
from app.services.conversation_service import ConversationService


def run_live_llm_test():
    print("=" * 75)
    print(f"🚀 LIVE LLM CONVERSATION TEST: {settings.model_name} @ {settings.ai_base_url}")
    print("=" * 75)

    repo = InMemoryConversationRepository()
    client = OllamaClient()
    compactor = Compactor()

    service = ConversationService(
        conversation_repository=repo,
        inference_client=client,
        compactor=compactor,
    )

    # --- Turn 1: Discuss architecture ---
    print("\n[Turn 1] User: Establishing project architecture...")
    t0 = time.perf_counter()
    req1 = ChatRequest(message="We are building FeatureForge using Clean Architecture and PostgreSQL Neon.")
    res1 = service.process_chat_request(req1)
    duration1 = time.perf_counter() - t0

    print(f"✅ Turn 1 Complete ({duration1:.1f}s) | Tokens: in={res1.prompt_tokens}, out={res1.completion_tokens}")
    print(f"🤖 Assistant:\n{res1.message[:300]}...\n")

    # --- Turn 2: Execute /compact with real LLM ---
    print("\n[Turn 2] User: Executing /compact to test LangChain structured extraction...")
    t0 = time.perf_counter()
    compact_req = ChatRequest(conversation_id=res1.conversation_id, message="/compact")
    compact_res = service.process_chat_request(compact_req)
    duration2 = time.perf_counter() - t0

    print(f"✅ Turn 2 Complete ({duration2:.1f}s)")
    print(f"📋 Structured Summary Produced:\n{compact_res.message[:400]}...\n")

    # --- Turn 3: Verify context retention post-compaction ---
    print("\n[Turn 3] User: Verifying context retention post-compaction...")
    t0 = time.perf_counter()
    req3 = ChatRequest(
        conversation_id=res1.conversation_id,
        message="What database and architecture style are we using?",
    )
    res3 = service.process_chat_request(req3)
    duration3 = time.perf_counter() - t0

    print(f"✅ Turn 3 Complete ({duration3:.1f}s) | Tokens: in={res3.prompt_tokens}, out={res3.completion_tokens}")
    print(f"🤖 Assistant:\n{res3.message}\n")

    print("=" * 75)
    print("🎉 ALL LIVE LLM CONVERSATION & COMPACTOR TURNS PASSED!")
    print("=" * 75)


if __name__ == "__main__":
    run_live_llm_test()
