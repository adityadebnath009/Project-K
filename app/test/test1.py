
from app.schemas.chat import ChatRequest, ChatResponse

request = ChatRequest(
    conversation_id=None,
    message="Explain how context windows work."
)

print(request)
print(request.model_dump())

response = ChatResponse(
    conversation_id="conv_123",
    message="A context window limits the information processed in a model call."
)

print(response.model_dump())
print(response.model_dump_json())
