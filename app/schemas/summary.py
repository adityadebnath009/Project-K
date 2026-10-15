from pydantic import BaseModel, Field


class CompactionSummary(BaseModel):
    """
    Structured Operational Ledger.
    Captures durable context so the LLM never loses critical project state.
    """
    primary_goal: str = Field(
        default="",
        description="The main goal or task being worked on in this chat.",
    )
    key_decisions: list[str] = Field(
        default_factory=list,
        description="Architectural or design decisions explicitly agreed upon.",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Rules or invariants the assistant must follow.",
    )
    files_and_artifacts: list[str] = Field(
        default_factory=list,
        description="Key files, tables, or modules created or modified.",
    )
    completed_tasks: list[str] = Field(
        default_factory=list,
        description="Completed milestones or steps.",
    )
    pending_tasks: list[str] = Field(
        default_factory=list,
        description="Upcoming tasks or unresolved questions.",
    )

    def to_context_string(self) -> str:
        """
        Formats the structured ledger into a dense markdown block
        ready to be injected directly into the LLM's prompt.
        """
        lines = ["### [COMPACTED OPERATIONAL STATE]"]
        if self.primary_goal:
            lines.append(f"**Goal**: {self.primary_goal}")

        if self.key_decisions:
            lines.append("**Key Decisions**:")
            for d in self.key_decisions:
                lines.append(f"- {d}")

        if self.constraints:
            lines.append("**Constraints**:")
            for c in self.constraints:
                lines.append(f"- {c}")

        if self.files_and_artifacts:
            lines.append("**Files & Artifacts**:")
            for f in self.files_and_artifacts:
                lines.append(f"- {f}")

        if self.completed_tasks:
            lines.append("**Completed Tasks**:")
            for t in self.completed_tasks:
                lines.append(f"- {t}")

        if self.pending_tasks:
            lines.append("**Pending Tasks**:")
            for p in self.pending_tasks:
                lines.append(f"- {p}")

        return "\n".join(lines)