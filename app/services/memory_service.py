from app.repositories.interfaces import MemoryRepository
from app.schemas.memory import (
    ExtractedMemoryPackage,
    MemoryItem,
    ProjectMemoryDTO,
    UserProfileDTO,
)
from app.services.token_counter import TokenCounter


class MemoryService:
    def __init__(self,
                memory_repository: MemoryRepository,
                token_counter: TokenCounter | None = None):
        self.memory_repository = memory_repository
        self.token_counter = token_counter or TokenCounter()


    def _pack_memories_to_budget(
            self,
            memories: list[MemoryItem],
            max_tokens: int,
            tag_overhead_tokens: int = 25,) -> list[MemoryItem]:
        
        if not memories:
            return []

        usable_budget = max(0, max_tokens -  tag_overhead_tokens)
        packed: list[MemoryItem] = []
        accumulated_tokens = 0 

        for item in memories:
            line_text = f"- **{item.key}**: {item.value}\n"
            cost = self.token_counter.count_tokens(line_text)
            if accumulated_tokens + cost <= usable_budget:
                packed.append(item)
                accumulated_tokens += cost
            else:
                continue
        return packed


    def get_user_profile_context(
        self,
        user_id: str,
        max_tokens: int = 150,
    ) -> str | None:
        """
        Retrieves user facts from the repository, budget-packs them up to max_tokens,
        and returns the formatted <user_profile> context string (or None).
        """
        profile = self.memory_repository.get_user_profile(user_id)
        if not profile or not profile.memories:
            return None
        budgeted_memories = self._pack_memories_to_budget(
            memories=profile.memories,
            max_tokens=max_tokens,
        )
        if not budgeted_memories:
            return None
        budgeted_dto = UserProfileDTO(
            user_id=profile.user_id,
            memories=budgeted_memories,
        )
        return budgeted_dto.to_context_string()

    
    def get_project_memory_context(self,
                                   project_id: str,
                                   max_tokens: int  = 350) -> str | None:

        project_memory = self.memory_repository.get_project_memory(project_id)
        if not project_memory or not project_memory.memories:
            return None
        budgeted_memories = self._pack_memories_to_budget(
            memories=project_memory.memories,
            max_tokens=max_tokens,
        )
        if not budgeted_memories:
            return None
        budgeted_dto = ProjectMemoryDTO(
            project_id=project_memory.project_id,
            project_name=project_memory.project_name,
            root_path=project_memory.root_path,
            memories=budgeted_memories,
        )
        return budgeted_dto.to_context_string()
        
    def persist_extracted_memories(
        self,
        user_id: str,
        project_id: str | None,
        package: ExtractedMemoryPackage,
    ) -> tuple[int, int]:
        """
        Persists extracted facts to PostgreSQL via the repository.
        Returns (user_facts_upserted, project_facts_upserted).
        """
        return self.memory_repository.save_extracted_package(
            user_id=user_id,
            project_id=project_id,
            package=package,
        )

    def delete_user_fact(self, user_id:str, key: str) -> bool:
        return self.memory_repository.delete_user_memory(user_id, key)

    def delete_project_fact(self, project_id:str, key:str) -> bool:
        return self.memory_repository.delete_project_memory(project_id, key)