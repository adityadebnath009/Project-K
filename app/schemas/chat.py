from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: str | None = Field(default=None, description="The ID of the conversation. If not provided, a new conversation will be created.")
    message: str = Field(description="The user's message.", min_length=1, max_length=1000)
    user_id: str | None = Field(default="default_user", description="The ID of the user. If not provided, a new user will be created.")



class ChatResponse(BaseModel):
    conversation_id: str = Field(description="The ID of the conversation.")
    message: str = Field(description="The assistant's response message.")
    model: str = Field(default="qwen2.5:7b", description="The model used for generating the response.")
    prompt_tokens: int = Field(default=0, description="The number of tokens used in the prompt.")
    completion_tokens: int = Field(default=0, description="The number of tokens used in the completion.")

    