from pydantic import BaseModel, Field


class ContextPackage(BaseModel):
    conversation_id:str = Field(description="The ID of the conversation.")
    user_id:str = Field(description="The ID of the user.")

    messages:list[dict[str, str]] = Field(description="A list of messages in the conversation, each represented as a dictionary with 'role' and 'content' keys.")

    estimated_input_tokens:int = Field(description="The estimated number of tokens used in the input messages.")

    max_input_budget:int = Field(description="The maximum number of tokens allowed for the input messages, calculated based on the effective context limit, reserved output tokens, and safety margin.")

    is_compacted:bool = Field(description="A boolean indicating whether the context has been compacted to fit within the token budget.")
