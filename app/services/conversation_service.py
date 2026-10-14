from app.inference import OllamaClient
from app.repositories import ConversationRepository
from app.schemas import ChatRequest, ChatResponse, ContextPackage


class ConversationService:
    def __init__(self,
                    conversation_repository: ConversationRepository,
                    inference_client: OllamaClient):
        self.conversation_repository = conversation_repository
        self.inference_client = inference_client


    def process_chat_request(self, chat_request: ChatRequest) -> ChatResponse:

        user_id = chat_request.user_id or "default_user"
        conversation_id = self.conversation_repository.get_or_create_conversation(
            chat_request.conversation_id, 
            user_id)

       

        self.conversation_repository.append_message(
            conversation_id=conversation_id,
            role="user",
            content=chat_request.message
        )


        history = self.conversation_repository.get_messages(conversation_id)
     
        model_messages = [
            {"role": msg["role"], "content": msg["content"]} for msg in history
        ]
        assistant_reply = self.inference_client.generate(messages=model_messages)
        self.conversation_repository.append_message(
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_reply,
        )
      
        return ChatResponse(
            conversation_id=conversation_id,
            message=assistant_reply,
        )

