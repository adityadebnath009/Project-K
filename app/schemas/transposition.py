from enum import Enum
from typing import Any, TypedDict

from pydantic import BaseModel, Field, field_validator

from app.schemas.slice import VerticalSlice


class TargetLayer(str, Enum):
    ENTITY = "entity"
    REPOSITORY_PROTOCOL = "repository_protocol"
    REPOSITORY_IMPL = "repository_impl"
    SERVICE = "service"
    SCHEMA = "schema"
    TEST = "test"
class TargetComponentRole(str, Enum):
    """The inferred behavioral responsibility of a target file or symbol."""
    ENTRY_POINT = "entry_point"
    DOMAIN_MODEL = "domain_model"
    DATA_ACCESS = "data_access"
    BUSINESS_LOGIC = "business_logic"
    DATA_CONTRACT = "data_contract"
    TEST_SUITE = "test_suite"
    INFRASTRUCTURE = "infrastructure"
    UNKNOWN = "unknown"
class ComponentAction(str, Enum):
    """The explicit architectural action for transposing a component."""
    REUSE = "reuse"
    EXTEND = "extend"
    ADAPT = "adapt"
    CREATE = "create"


class DataContractField(BaseModel):
    name: str = Field(description="Field name, e.g. 'email', 'price_cents'")
    field_type: str = Field(description="Normalized Python type, e.g. 'str', 'int', 'uuid.UUID'")
    is_required: bool = Field(default=True, description="Whether the field is mandatory")
    default_value: Any | None = Field(default=None, description="Default value if optional")
    description: str | None = Field(default=None, description="Field explanation")


class DataContract(BaseModel):
    name: str = Field(description="Contract name, e.g. 'UserLoginRequest', 'TokenResponse'")
    fields: list[DataContractField] = Field(default_factory=list)
    description: str | None = None


class StateTransition(BaseModel):
    from_state: str
    to_state: str
    trigger: str
    guard_condition: str | None = None


class StateMachine(BaseModel):
    name: str
    states: list[str] = Field(default_factory=list)
    initial_state: str
    transitions: list[StateTransition] = Field(default_factory=list)


class AlgorithmStep(BaseModel):
    step_number: int
    action: str
    description: str
    error_condition: str | None = None


class PureAlgorithm(BaseModel):
    name: str
    inputs: list[str] = Field(default_factory=list)
    output: str
    steps: list[AlgorithmStep] = Field(default_factory=list)
    exceptions_raised: list[str] = Field(default_factory=list)


class FrameworkAgnosticIR(BaseModel):
    feature_name: str
    summary: str
    contracts: list[DataContract] = Field(default_factory=list)
    state_machines: list[StateMachine] = Field(default_factory=list)
    algorithms: list[PureAlgorithm] = Field(default_factory=list)
    source_provenance_files: list[str] = Field(default_factory=list)
    source_symbol_ids: list[str] = Field(default_factory=list)

def default_layer_dirs() -> dict[TargetLayer, str]:
    return {
        TargetLayer.ENTITY: "app/entities",
        TargetLayer.REPOSITORY_PROTOCOL: "app/repositories",
        TargetLayer.REPOSITORY_IMPL: "app/repositories",
        TargetLayer.SERVICE: "app/services",
        TargetLayer.SCHEMA: "app/schemas",
        TargetLayer.TEST: "app/test",
    }


def default_dto_suffixes() -> list[str]:
    return [
        "request", "response", "dto", "schema", "inresponse",
        "payload", "view", "body", "out", "param"
    ]


class TargetConventionMap(BaseModel):
    architecture_style: str = "Clean Architecture"
    layer_directories: dict[TargetLayer, str] = Field(default_factory=default_layer_dirs)
    repo_naming_pattern: str = "{symbol}Repository"
    service_naming_pattern: str = "{symbol}Service"
    dto_suffixes: list[str] = Field(default_factory=default_dto_suffixes)
    base_entity_import: str = "app.entities.base.Base"
    pk_strategy: str = "uuid7"
    orm_style: str = "sqlalchemy_2.0"
    schema_style: str = "pydantic_v2"
    existing_entities: list[str] = Field(default_factory=list)
    existing_services: list[str] = Field(default_factory=list)

    def get_layer_dir(self, layer: TargetLayer) -> str:
        """Returns the center-of-gravity directory for a given architectural layer."""
        return self.layer_directories.get(layer, f"app/{layer.value}s")

    def get_file_path(self, layer: TargetLayer, file_slug: str) -> str:
        """Returns the full relative target file path for a component."""
        layer_dir = self.get_layer_dir(layer)
        return f"{layer_dir}/{file_slug}.py"

    def format_repo_name(self, symbol_name: str) -> str:
        """Applies the discovered repository naming pattern to an entity symbol."""
        return self.repo_naming_pattern.format(symbol=symbol_name)


class ComponentMapping(BaseModel):
    source_id: str
    target_layer: TargetLayer
    action: ComponentAction = Field(default=ComponentAction.CREATE, 
                                    description="Architectural action: reuse, extend, create, or adapt")
    target_file_path: str
    target_symbol_name: str
    description: str


class AdaptationPlan(BaseModel):
    feature_name: str
    target_root: str
    mappings: list[ComponentMapping] = Field(default_factory=list)
    new_dependencies: list[str] = Field(default_factory=list)
    schema_diff_summary: str

class ScaffoldedFile(BaseModel):
    file_path: str
    content: str
    layer: TargetLayer
    description: str


class TranspositionResult(BaseModel):
    feature_name: str
    success: bool = True
    scaffolded_files: list[ScaffoldedFile] = Field(default_factory=list)
    plan: AdaptationPlan
    ir: FrameworkAgnosticIR
    audit_passed: bool = False
    audit_feedback: str | None = None
class EvidenceReference(BaseModel):
    """An empirical observation backed by exact AST, symbol, or manifest evidence."""
    file_path: str = Field(description="Relative path of file containing the evidence")
    symbol_name: str | None = Field(default=None, description="Exact symbol identifier if applicable")
    line_start: int | None = Field(default=None, description="Line number start")
    line_end: int | None = Field(default=None, description="Line number end")
    observation: str = Field(description="Direct factual observation (e.g. 'Imports sqlalchemy.orm.Mapped')")


class ComponentAssessment(BaseModel):
    """An architectural role assessment for a target component, backed by evidence."""
    component_id: str = Field(description="Relative file path or symbol ID")
    role: TargetComponentRole = Field(description="Inferred architectural role")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    evidence: list[EvidenceReference] = Field(default_factory=list, description="Ground-truth supporting facts")
    rationale: str = Field(description="Why this role was inferred from the evidence")

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, v: Any) -> float:
        if isinstance(v, (int, float)):
            if v > 1.0:
                return min(1.0, float(v) / 100.0)
            return max(0.0, float(v))
        if isinstance(v, str):
            val = float(v.rstrip("%").strip())
            return min(1.0, val / 100.0 if val > 1.0 else val)
        return 1.0


class TargetEvidenceManifest(BaseModel):
    """
    Factual, structural summary of the target codebase produced by Layers 1 & 2.
    Contains no framework guesses—only verified facts and relationships.
    """
    target_root: str
    total_files_scanned: int
    files_indexed_count: int
    parse_error_count: int
    parse_errors: dict[str, str] = Field(default_factory=dict, description="File path -> parse error description")
    
    # Manifest observations
    declared_dependencies: list[str] = Field(default_factory=list, description="Libraries from pyproject/requirements")
    
    # Relationship facts
    inheritance_map: dict[str, list[str]] = Field(default_factory=dict, description="Class -> base classes")
    decorators_by_symbol: dict[str, list[str]] = Field(default_factory=dict, description="Symbol -> decorator names")
    imports_by_file: dict[str, list[str]] = Field(default_factory=dict, description="File -> imported modules")
    
    # Graph metrics
    total_call_edges: int = 0
    resolved_internal_calls: int = 0
    unresolved_calls: int = 0
    call_resolution_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class TargetRepositoryProfile(BaseModel):
    """
    Inferred architectural profile of the target repository.
    Produced by Layer 3 (LLM Architect) and verified by Layer 4 (Validator).
    """
    target_root: str = Field(description="Absolute root path of target codebase")
    architectural_style: str = Field(default="unknown", description="e.g. 'Clean Architecture', 'Layered', 'Flat', 'unknown'")
    framework: str = Field(default="unknown", description="e.g. 'fastapi', 'flask', 'django', 'unknown'")
    orm: str = Field(default="unknown", description="e.g. 'sqlalchemy_2.0', 'django_orm', 'unknown'")
    dto_pattern: str = Field(default="unknown", description="e.g. 'pydantic_v2', 'dataclasses', 'unknown'")
    primary_key_pattern: str = Field(default="unknown", description="e.g. 'uuid7', 'uuid4', 'int', 'unknown'")
    test_framework: str = Field(default="unknown", description="e.g. 'pytest', 'unittest', 'unknown'")
    conventions: TargetConventionMap = Field(default_factory=TargetConventionMap)
    
    # Explicit evidence-backed component roles
    components: list[ComponentAssessment] = Field(default_factory=list)
    
    # Discovered public interfaces/services that are safe to reuse or extend
    reusable_interfaces: list[str] = Field(default_factory=list)
    reusable_services: list[str] = Field(default_factory=list)
    existing_domain_models: list[str] = Field(default_factory=list)
    
    # Any ambiguities, missing evidence, or questions that require review
    unresolved_questions: list[str] = Field(default_factory=list)
    indexing_coverage_rate: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("indexing_coverage_rate", mode="before")
    @classmethod
    def normalize_coverage_rate(cls, v: Any) -> float:
        if isinstance(v, (int, float)):
            if v > 1.0:
                return min(1.0, float(v) / 100.0)
            return max(0.0, float(v))
        if isinstance(v, str):
            val = float(v.rstrip("%").strip())
            return min(1.0, val / 100.0 if val > 1.0 else val)
        return 1.0


class TranspositionState(TypedDict):
    """The shared state dictionary flowing through the LangGraph StateGraph."""
    source_slice: VerticalSlice
    target_repo_path: str
    target_profile: TargetRepositoryProfile | None
    target_manifest: TargetEvidenceManifest | None
    ir: FrameworkAgnosticIR | None
    conventions: TargetConventionMap | None
    plan: AdaptationPlan | None
    scaffolded_files: list[ScaffoldedFile]
    audit_passed: bool
    audit_feedback: str | None
    retry_count: int