import uuid
from app.database import SessionLocal
from app.repositories.postgres_conversation import PostgresConversationRepository

def fetch_transcript():
    # We need to find the most recent conversation since the ID was random in the test
    with SessionLocal() as session:
        conv_repo = PostgresConversationRepository()
        
        # Get the most recent conversation ID from the DB
        # Since the test used uuid.uuid4(), we look for the one with the latest created_at
        from sqlalchemy import text
        result = session.execute(text("SELECT id FROM conversations ORDER BY created_at DESC LIMIT 1")).fetchone()
        
        if not result:
            print("No conversations found in the database.")
            return
        
        conv_id = result[0]
        print(f"Fetching transcript for Conversation ID: {conv_id}\n" + "="*60)
        
        messages = conv_repo.get_messages(str(conv_id))
        for m in messages:
            role = m.get("role", "Unknown").upper()
            content = m.get("content", "")
            seq = m.get("sequence_number", "?")
            print(f"[{seq}] {role}: {content}\n")

if __name__ == "__main__":
    fetch_transcript()
