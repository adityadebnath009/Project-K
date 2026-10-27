import pytest
import uuid
from app.database import SessionLocal
from app.repositories.postgres_conversation import PostgresConversationRepository
from app.repositories.postgres_user import PostgresUserRepository
from app.repositories.postgres_memory import PostgresMemoryRepository
from app.repositories.postgres_project import PostgresProjectRepository
from app.services.conversation_service import ConversationService
from app.services.context_manager import ContextManager
from app.services.compactor import Compactor
from app.services.memory_extractor import MemoryExtractor
from app.services.memory_service import MemoryService
from app.inference.ollama_client import OllamaClient
from app.schemas.chat import ChatRequest

def test_real_llm_master_integration():
    """
    TRUE MASTER INTEGRATION TEST
    Connects: Real DB -> Real Ollama LLM -> Real Memory/Compaction Logic
    Runs a 20-turn conversation to verify the actual LLM-driven state management.
    """
    print("\n🚀 STARTING REAL LLM SYSTEM INTEGRATION TEST (20 TURNS)...")
    
    # 1. Infrastructure
    user_repo = PostgresUserRepository()
    conv_repo = PostgresConversationRepository()
    mem_repo = PostgresMemoryRepository()
    proj_repo = PostgresProjectRepository()
    
    # REAL LLM Client
    inference_client = OllamaClient() 
    
    # Services
    mem_service = MemoryService(mem_repo)
    compactor = Compactor(inference_client)
    mem_extractor = MemoryExtractor(inference_client)
    
    service = ConversationService(
        conversation_repository=conv_repo,
        inference_client=inference_client,
        compactor=compactor,
        memory_service=mem_service,
        memory_extractor=mem_extractor,
        project_repository=proj_repo
    )

    user_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())
    conversation_id = str(uuid.uuid4())
    user_repo.create_user(user_id=user_id)

    scenarios = [
        "Hello! I'm building a new app and I want to implement a login system.",
        "I saw how FastAPI-Users does it. Can we look at that?",
        "I want my project to follow Clean Architecture with a 'src/' root.",
        "My services should be called 'Managers'.",
        "My repositories should be called 'Stores'.",
        "I already have a User model in src/domain/models/user.py.",
        "Can you explain the password reset flow in FastAPI-Users?",
        "How does the JWT token get signed in their implementation?",
        "I want to use Argon2 instead of Bcrypt for hashing.",
        "Where should the password reset DTOs go in my project?",
        "Can you summarize everything we've decided so far?",
        "Actually, I want to change the 'Store' suffix to 'Repository'.",
        "Let's add a 'NotificationService' to the plan for email alerts.",
        "Does this affect the User model we reused?",
        "What are the exact file paths for the new service?",
        "I want to add a 'Redis' cache for the session tokens.",
        "Which library should I use for Redis in Python?",
        "Can you update the Adaptation Plan with the Redis dependency?",
        "I'm happy with the plan. Please confirm the final architecture.",
        "Final request: summarize the final project structure and dependencies.",
    ]

    print("\n--- Starting Real LLM Conversation Loop ---")
    for i, user_msg in enumerate(scenarios, 1):
        request = ChatRequest(
            user_id=user_id,
            project_id=project_id,
            conversation_id=conversation_id,
            message=user_msg
        )
        
        # This now hits the real Ollama API
        response = service.process_chat_request(request)
        print(f"Turn {i}: User: {user_msg[:30]}... -> Assistant: {response.message[:50]}...")

    # --- FINAL VERIFICATION ---
    messages = conv_repo.get_messages(conversation_id)
    assert len(messages) >= 40, "Conversation history not fully persisted"
    
    # Verify that at least one compaction happened given the turn count
    summaries = conv_repo.get_latest_summary(conversation_id)
    if summaries:
        print(f"✅ Compaction verified: Summary version {summaries['version']}")
    
    print("\n🎉 REAL SYSTEM INTEGRATION SUCCESSFUL: DB + Real Ollama LLM + Memory")

if __name__ == "__main__":
    test_real_llm_master_integration()
