# AGENTS.md — Project Memory & Architecture Guide

## Project Identity
- **Project Name:** FeatureForge (RepoTransposer)
- **Repo Directory:** `/Users/adityadebnath/Projects/ai_redemption`
- **Vision Document:** See [PROJECT_VISION.md](file:///Users/adityadebnath/Projects/ai_redemption/PROJECT_VISION.md)
- **Mission:** An agentic feature reverse-engineering and architectural transposition engine that extracts vertical feature slices from open-source repositories and transplants them into clean, production-ready target codebases.

---

## Architectural Principles & Clean Architecture Layout

This project strictly adheres to **Clean Architecture** with separation of concerns:

```
app/
├── config.py              # Centralized dataclass Settings (Ollama, context limits, token reserves)
├── entities/              # SQLAlchemy ORM declarative models (pure domain models)
│   ├── base.py            # Base declarative class
│   ├── user.py            # User entity (UUID PK)
│   ├── conversation.py    # Conversation entity (UUID PK, user_id FK)
│   ├── message.py         # Message entity (sequence_number, role, content)
│   └── conversation_summary.py # Versioned compaction summary entity
├── repositories/          # Persistence abstraction layer
│   ├── interfaces.py      # Abstract repository protocols / interfaces
│   ├── in_memory.py       # In-memory implementation for fast mock testing
│   ├── postgres_user.py   # PostgreSQL user repository
│   └── postgres_conversation.py # PostgreSQL conversation, message & summary repo
├── schemas/               # Pydantic v2 DTOs and validation models
│   ├── chat.py            # ChatRequest, ChatResponse
│   ├── context.py         # ContextPackage, Turn models
│   └── summary.py         # CompactionSummary DTO with structured extraction
├── services/              # Pure business logic and domain orchestration
│   ├── conversation_service.py # Orchestrates chat, /compact command, and context injection
│   ├── context_manager.py # Sliding window turn grouping & token budget enforcement
│   ├── compactor.py       # LangChain structured output LLM compactor
│   ├── token_counter.py   # tiktoken BPE token counter
│   └── user_service.py    # User registration and verification
├── inference/             # Model inference clients
│   ├── base.py            # Abstract InferenceClient protocol
│   └── ollama_client.py   # Ollama / OpenAI-compatible client
└── test/                  # Verification test suites (Phase 1 through Phase 4)
```

---

## Database & Persistence Standards
- **ORM:** SQLAlchemy 2.0+ with type-annotated `Mapped[...]` columns.
- **Migrations:** Alembic (`alembic upgrade head`).
- **Data Integrity:** 
  - Messages use strictly increasing `sequence_number` scoped by `conversation_id`.
  - Summaries are versioned (`version` column) and track `last_covered_sequence_number`.
  - Foreign keys enforce `CASCADE` deletes across users $\rightarrow$ conversations $\rightarrow$ messages/summaries.

---

## Established Conventions
- **No Direct DB Access in Services:** Business services (`app/services/`) never execute raw SQL or know about database sessions; all data access goes through repository interfaces in `app/repositories/`.
- **Token Budgeting:** Every generation turn strictly calculates token usage with `TokenCounter` and guarantees context safety margins before invoking inference.
- **Structured LLM Outputs:** When extracting structured data (summaries, feature specs, plans), use LangChain's `.with_structured_output(PydanticModel)` instead of raw string parsing.
- **Strict Python Backend Exclusivity:** FeatureForge serves exclusively Python backend engineering. Frontend (React/Vue/CSS/HTML) is deliberately out of scope. All architectural deconstruction, AST parsing, and scaffolding are optimized for Python Clean Architecture, SQLAlchemy 2.0, Pydantic v2, and Alembic.
- **Transposition is Logic Adaptation (Never Direct Copying):** Transposition means reverse-engineering the core logic, state transitions, security rules, and data flows from the reference implementation, then generating 100% native target code that strictly conforms to the target codebase's conventions, existing fields, contracts, and connections.
- **Unified Autonomous Smoke-Testing (Zero Foreign Test Dependency):** Never attempt to run or adapt open-source reference test suites. Verification in Phase 7D exclusively uses autonomous, self-contained Smoke Tests generated for the target codebase (`test_transposed_<feature>_smoke.py`) to verify clean instantiation, dependency injection, exception-free execution, and zero regressions on existing target tests.
- **Deterministic-First Sandwich Architecture:** Never feed raw un-truncated code or unguided schemas directly to the LLM. Always extract AST facts and layer-grouped production symbols first (Layers 1 & 2), prompt with explicit constraints (Layer 3), and verify all proposed files and symbols against the AST `SymbolTable` (Layer 4) before accepting the output.
- **Zero-Git Remote Ingestion:** When ingesting remote public GitHub repositories, FeatureForge avoids `git clone` CLI calls (which can hang on interactive authentication or require local Git binaries). Instead, it streams tarball archives directly via HTTP (`httpx` + `tarfile`) into a local source cache (`~/.featureforge/cache/sources/`), achieving sub-2-second ingestion and instant caching.
- **Dual-Repository Git Boundary (Source vs Target):**
  - **Source (Reference) Repositories:** Strictly **Zero-Git Ingestion**. Streamed via HTTP tarball archives (`codeload.github.com/...`) into `~/.featureforge/cache/sources/` in < 2 seconds, completely avoiding terminal credential freezes and Git CLI dependencies.
  - **Target (Working) Codebase:** Git is used strictly as a **Safety & Diff Layer** (Aider pattern). Changes are written directly by Python (never `git apply`), followed by selective staging (`git add <transposed_files>`) on a dedicated feature branch (`featureforge/<feature>`). This keeps the developer's unrelated dirty files untouched and provides an instant 1-click `/undo` rollback (`git reset --hard HEAD~1`).
- **Resilient SEARCH/REPLACE Patching (Phase 7C):** For modifications to existing target files, the engine must use whitespace-tolerant `<<<<<<< SEARCH / ======= / >>>>>>> REPLACE` blocks rather than line-numbered diffs (`git apply`), preventing syntax rejections caused by minor line-number hallucinations.
- **Closed-Loop Self-Repair Cycle (Phase 7D):** In the verification sandbox, if syntax checks or the synthesized smoke test fail, the execution traceback must be intercepted and automatically fed back to the LLM repair node (up to 3 retries) before surfacing errors to the user.
- **Zero-Friction Atomic Undo (/undo):** File edits must be backed by an instant pre-apply snapshot (filesystem or git ref) so that users can roll back any transposed feature cleanly via `/undo`.
- **High-Density Signature Prompting:** When passing target context to the LLM, strip non-essential function bodies and provide typed class/function signatures grouped by architectural layer to maximize token economy.
- **Disk-Offloaded Artifact Architecture:** To prevent prompt pollution and eliminate `ContextBudgetExceededError` crashes, large extracted slices, architecture blueprints, and adaptation plans must be offloaded to disk artifacts under `~/.featureforge/artifacts/<conv_id>/`. The working prompt context carries only high-density, compact pointers (~80 tokens), reducing prompt consumption by 95% while keeping ground-truth files accessible for on-demand inspection.
- **CLI-First Architecture (Aider/Claude Code Model):** FeatureForge is primarily distributed as a native Python terminal CLI (`featureforge transpose ...` via Typer and Rich). It executes directly within the developer's project directory, eliminating remote OAuth barriers, enabling direct file writes and local `pytest` smoke testing, and maintaining 100% privacy with local Ollama inference. An optional local webview (`featureforge --ui`) provides browser-based visualization without cloud hosting dependencies.
- **Strict Pair-Programming Mode (Guide-Only Invariant):**
  - **Do NOT directly overwrite or write project code files in the editor without explicit user permission.**
  - Antigravity acts as a senior pair programmer and architectural guide: explain concepts, present code snippets in markdown blocks, explain line-by-line rationale, and allow the user to create and control files in their editor.
  - Tool usage must be limited to read/view operations, verification tests, and inspection commands, unless the user explicitly commands direct automated editing.
