from typing import Any

from app.config import settings
from app.schemas import ContextPackage
from app.services.token_counter import TokenCounter


class ContextBudgetExceededError(ValueError):
    """Raised when the context budget is exceeded."""
    pass  # noqa: PIE790

class ContextManager:
    def __init__(self, token_counter: TokenCounter | None = None):
        self.token_counter = token_counter or TokenCounter()


    def _group_into_turns(
            self,
            history: list[dict[str, Any]],
    ) -> list[list[dict[str, str]]]:

        """
        Groups flat messages into atomic conversational turns.
        A turn is typically [user_message, assistant_message].
        """


    
        turns: list[list[dict[str, str]]] = []
        current_turn: list[dict[str, str]] = []

        for msg in history:
            cleaned = {"role": msg.get("role", ""), "content": msg.get("content", "")}

            current_turn.append(cleaned)

            if cleaned["role"] == "assistant":
                turns.append(current_turn)
                current_turn = []


        if current_turn:
            turns.append(current_turn)


        return turns

    def build_context(
            self,
            conversation_id: str,
            user_id:str,
            history: list[dict[str, Any]],
            system_prompt: str | None = None,
            max_budget: int | None = None
    ) -> ContextPackage:
        budget = max_budget or settings.max_input_tokens
        prompt_text = system_prompt or settings.system_prompt

        system_message = {"role":"system", "content": prompt_text}

        system_tokens = self.token_counter.count_tokens_in_message(system_message)


        if system_tokens >= budget:
            raise ContextBudgetExceededError(
                f"System prompt ({system_tokens} tokens) exceeds total input budget ({budget} tokens)."
            )

        remaining_budget = budget - system_tokens

        turns = self._group_into_turns(history)

        selected_turns: list[list[dict[str, Any]]] = []

        accumulated_history_tokens = 0
        was_trimmed = False

        for turn in reversed(turns):
            turn_tokens = self.token_counter.count_tokens_in_messages(turn)

            if accumulated_history_tokens + turn_tokens <= remaining_budget:

                selected_turns.append(turn)
                accumulated_history_tokens += turn_tokens

            else:
                
                was_trimmed = True
                break

        selected_turns.reverse()

        flattened_history: list[dict[str, str]] = [
            msg for turn in selected_turns for msg in turn
        ]
       
        final_messages = [system_message, *flattened_history]
        total_tokens = system_tokens + accumulated_history_tokens
        return ContextPackage(
            conversation_id=conversation_id,
            user_id=user_id,
            messages=final_messages,
            estimated_input_tokens=total_tokens,
            max_input_budget=budget,
            is_compacted=was_trimmed,
        )




        
        


