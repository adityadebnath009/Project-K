from typing import Any

import tiktoken


class TokenCounter:
    MESSAGE_OVERHEAD_TOKENS = 4  # Overhead for each message turn (role + content + 4 tokens)
    def __init__(self, encoding_name:str = "cl100k_base"):
        self.encoding = tiktoken.get_encoding(encoding_name)

    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in a given text.
        """
        if not text:
            return 0
        return len(self.encoding.encode(text))

    def count_tokens_in_message(self,message: dict[str, Any]) -> int:

        """
        Counts tokens for a single message turn:
        role + content + 4 tokens message overhead.
        """
        role = message.get("role", "")
        content = message.get("content", "")
        return self.count_tokens(role) + self.count_tokens(content) + self.MESSAGE_OVERHEAD_TOKENS

    def count_tokens_in_messages(self, messages: list[dict[str, Any]]) -> int:
        """
        Counts tokens for a list of message turns.
        """
        total_tokens = 0
        for message in messages:
            total_tokens += self.count_tokens_in_message(message)
        return total_tokens

    def decode(self, tokens: list[int]) -> str:                                                                                                                                                           
          """                                                                                                                                                                                               
          Converts a list of token IDs back into a UTF-8 string.
          """                                                                                                                                                                                               
          if not tokens:
              return ""
          return self.encoding.decode(tokens)

    
    def truncate_to_token_limit(
            self, 
            text: str,
            max_tokens: int,
            from_end: bool = False,
    ) -> str:
        if not text or max_tokens<=0:
            return ""

        tokens = self.encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text

        if from_end:
            return self.encoding.decode(tokens[-max_tokens:])
        else:
            return self.encoding.decode(tokens[:max_tokens])

        