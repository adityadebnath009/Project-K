from typing import Protocol, runtime_checkable, Any

@runtime_checkable
class InferenceClient(Protocol):
    """
    Abstract interface for LLM inference.
    Can be implemented by different LLM providers (e.g., OpenAI, Anthropic, etc.) to provide a consistent interface for generating responses.
    This allows for easy swapping of LLM providers without changing the rest of the application code.
    """

    def generate(
        self, conversation_id: str, 
        messages: list[dict[str, Any]],
        system_prompt: str | None = None,
    ) -> str:
        """
        Sends formatted messages to the LLM and returns the text response.
        """
        ...