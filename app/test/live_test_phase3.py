import sys
from app.config import settings
from app.inference.ollama_client import OllamaClient
from app.repositories.in_memory import InMemoryConversationRepository
from app.schemas.chat import ChatRequest
from app.services.compactor import Compactor
from app.services.conversation_service import ConversationService


def run_live_test():
    print(f"Connecting to Ollama at {settings.ai_base_url} with model {settings.model_name}...")

    repo = InMemoryConversationRepository()
    client = OllamaClient()
    compactor = Compactor()

    service = ConversationService(
        conversation_repository=repo,
        inference_client=client,
        compactor=compactor,
    )

    # Turn 1
    print("\n--- Turn 1: Discussing architecture ---")
    req1 = ChatRequest(message="We are designing a user management system in Java using Spring Boot and PostgreSQL.")
    res1 = service.process_chat_request(req1)
    print(f"Assistant: {res1.message[:200]}...\n[Tokens: prompt={res1.prompt_tokens}, completion={res1.completion_tokens}]")

    # Turn 2
    print("\n--- Turn 2: Discussing constraints & files ---")
    req2 = ChatRequest(
        conversation_id=res1.conversation_id,
        message="We must enforce a maximum token budget of 6392 tokens and store summaries in a table called conversation_summaries."
    )
    res2 = service.process_chat_request(req2)
    print(f"Assistant: {res2.message[:200]}...\n[Tokens: prompt={res2.prompt_tokens}, completion={res2.completion_tokens}]")

    # Turn 3: Compact
    print("\n--- Turn 3: Executing /compact with real LLM ---")
    compact_req = ChatRequest(conversation_id=res1.conversation_id, message="/compact")
    compact_res = service.process_chat_request(compact_req)
    print(f"Compactor Output:\n{compact_res.message}")

    # Turn 4: Test context continuity
    print("\n--- Turn 4: Verifying context retention post-compaction ---")
    req4 = ChatRequest(
        conversation_id=res1.conversation_id,
        message="What database and table did we decide to use, and what is our token budget?"
    )
    res4 = service.process_chat_request(req4)
    print(f"Assistant: {res4.message}\n[Tokens: prompt={res4.prompt_tokens}, completion={res4.completion_tokens}]")
    print("\n🎉 Live LLM test finished successfully!")


if __name__ == "__main__":
    try:
        run_live_test()
    except Exception as e:
        print(f"\n❌ Live test encountered an error: {e}")
        sys.exit(1)
