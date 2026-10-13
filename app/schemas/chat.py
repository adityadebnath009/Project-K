from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    conversation_id: str | None = Field(default=None, description="The ID of the conversation. If not provided, a new conversation will be created.")
    message: str = Field(description="The user's message.", min_length=1, max_length=1000)



class ChatResponse(BaseModel):
    conversation_id: str = Field(description="The ID of the conversation.")
    message: str = Field(description="The assistant's response message.")