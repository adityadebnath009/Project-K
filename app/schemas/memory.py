
from xml.sax.saxutils import quoteattr

from pydantic import BaseModel, Field


class MemoryItem(BaseModel):
    category: str = Field(
        description="Grouping namespace, e.g., 'role', 'tech_stack', 'architecture', 'standards', 'constraints'"
    )
    key: str = Field(
        description="Unique property key, e.g., 'primary_language', 'backend_framework', 'guidance_rule'"
    )
    value: str = Field(
        description="The factual assertion or engineering rule"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0"
    )
def _format_grouped_memories(memories: list[MemoryItem]) -> list[str]:

    grouped :dict[str, list[MemoryItem]] = {}

    for item in memories:
        grouped.setdefault(item.category, []).append(item)

    lines: list[str] = []

    for category, items in grouped.items():
        lines.append(f'###{category.replace('_',' ').title()}')
        for item in items:
            lines.append(f"- **{item.key}**: {item.value}")

    return lines





class UserProfileDTO(BaseModel):
    user_id: str
    memories: list[MemoryItem] = Field(default_factory=list)

    def to_context_string(self) -> str:
        """Formats user profile memories into an LLM-friendly context block."""
        if not self.memories:
            return ""

        # Group by category
        body_lines = _format_grouped_memories(self.memories)
        return "\n".join(["<user_profile>", *body_lines, "</user_profile>"])


class ProjectMemoryDTO(BaseModel):
    project_id: str
    project_name: str
    root_path: str
    memories: list[MemoryItem] = Field(default_factory=list)

    def to_context_string(self) -> str:
        """Formats project architecture memories into an LLM-friendly context block."""
        if not self.memories:
            return ""

        # Group by category
       
        name_attr = quoteattr(self.project_name)
        root_attr = quoteattr(self.root_path)
        body_lines = _format_grouped_memories(self.memories)
        return "\n".join([
            f"<project_context name={name_attr} root={root_attr}>",
            *body_lines,
            "</project_context>"
        ])


class ExtractedMemoryPackage(BaseModel):
    """
    Contract used for LangChain structured extraction from conversation history.
    Strictly separates user persona facts from project codebase facts.
    """
    user_facts: list[MemoryItem] = Field(
        default_factory=list,
        description="Durable facts about the user's personal identity, engineering role, habits, or communication preferences"
    )
    project_facts: list[MemoryItem] = Field(
        default_factory=list,
        description="Durable facts about this codebase's architecture, dependencies, database schema, design patterns, or milestones"
    )