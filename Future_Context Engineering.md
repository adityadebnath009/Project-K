# Future Context Engineering: Roadmap & Advanced Architectural Evolution

This document outlines advanced context engineering enhancements for **FeatureForge (RepoTransposer)**. These enhancements build upon our hardened 5-tier context hierarchy, watermark partitioning, and proactive auto-compaction engine.

---

## Architecture Roadmap Overview

| Initiative | Core Mechanism | Target Problem Solved | Complexity |
| :--- | :--- | :--- | :---: |
| **1. Dynamic Budget Allocation** | Elastic Partitioning between User & Project Memory | Eliminates rigid token waste; adapts to query intent | Medium |
| **2. Hierarchical Summaries** | Multi-Tier Chapter Trees & Meta-Ledgers | Solves information compression loss in 1,000+ turn chats | High |
| **3. Memory Decay & Conflict Resolution** | Half-Life Confidence Scoring & Active Reconciliation | Prevents stale architectural ghost rules when tech stacks evolve | Medium |

*(Note: Semantic Vector Retrieval / pgvector RAG is tracked separately in `implementation_plan.md`.)*

---

## 1. From Static Budgeting → Dynamic Allocation

### The Current Baseline
Currently, memory tiers have static token caps:
- User Profile Tier: $\le 150$ tokens
- Project Context Tier: $\le 350$ tokens
- Total Memory Reservation: $\le 500$ tokens

### The Gap
- In small projects, 350 tokens are rarely filled, resulting in unused headroom.
- In enterprise monorepos, 350 tokens can only fit 3–4 architecture rules, truncating critical persistence or security constraints.
- Rigid partitions ignore intent: if the developer asks *"What are my personal coding habits?"*, spending 350 tokens on project facts and only 150 on user persona is an inversion of priority.

### The Proposed Architecture: Elastic Partitioning
Instead of two static buckets, enforce an **invariant total memory pool** with an **adaptive split**:

$$B_{\text{memory\_total}} = B_{\text{user}} + B_{\text{project}} \le 500 \text{ tokens}$$

```
Static Allocation (Current):
┌───────────────────────────┬────────────────────────────────────────────────────────┐
│ User Profile (150 tokens) │ Project Context (350 tokens)                           │
└───────────────────────────┴────────────────────────────────────────────────────────┘

Dynamic Allocation (Intent-Adaptive):
Query: "Explain my personal design habits"
┌────────────────────────────────────────────────────────┬───────────────────────────┐
│ User Profile: 375 tokens (Expanded)                    │ Project: 125 tokens (Slim)│
└────────────────────────────────────────────────────────┴───────────────────────────┘

Query: "Review the database schema and foreign key constraints"
┌───────────────────────────┬────────────────────────────────────────────────────────┐
│ User: 100 tokens (Slim)   │ Project Context: 400 tokens (Expanded)                 │
└───────────────────────────┴────────────────────────────────────────────────────────┘
```

### Implementation Blueprint
1. **Lightweight Intent Classifier**: A deterministic regex / keyword classifier (or fast token heuristic) determines whether the incoming turn is **User-Centric**, **Project-Centric**, or **Balanced**.
2. **Elastic Knapsack**: `MemoryService` adjusts `usable_budget` for each tier dynamically per turn while strictly ensuring the sum never exceeds the global memory allocation ceiling.

---

## 2. From Basic Compaction → Recursive / Hierarchical Summaries

### The Current Baseline
Summaries progress linearly: $\text{Version 1} \rightarrow \text{Version 2} \rightarrow \text{Version 3}$. Each compaction condenses all uncovered turns into a single operational ledger.

### The Gap (The "Compression Loss" Ceiling)
In long-running development projects (500 to 2,000+ turns):
- A single summary ledger becomes either **too large** (crowding out raw history) or **over-compressed** (losing critical details from early milestones like *"How we configured Alembic migrations in Phase 1"*).
- Compaction models tend to summarize the most recent 10 turns well, but dilute or omit decisions made 50 turns ago.

### The Proposed Architecture: Chapter Trees & Meta-Ledgers
Borrow the **LSM-Tree / B-Tree Compaction** concept from database storage engines:

```
                      ┌────────────────────────────────────┐
                      │            META-SUMMARY            │
                      │    (High-Level Project Vision)     │
                      └─────────────────┬──────────────────┘
                                        │
           ┌────────────────────────────┼────────────────────────────┐
           ▼                            ▼                            ▼
┌──────────────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│  CHAPTER 1: PHASE 1  │     │  CHAPTER 2: PHASE 4  │     │  CHAPTER 3: PHASE 5  │
│  Base Clean Arch &   │     │  Neon PostgreSQL &   │     │  Hierarchical Memory │
│  Token Formulas      │     │  Sequence Numbers    │     │  & Auto-Compaction   │
│  (Seq 1 - 40)        │     │  (Seq 41 - 95)       │     │  (Seq 96 - Current)  │
└──────────────────────┘     └──────────────────────┘     └──────────────────────┘
```

### Implementation Blueprint
1. **Milestone / Chapter Segmentation**: Compaction groups history into discrete chapters when major phase milestones are hit (e.g. 50+ turns or explicit `/milestone` tag).
2. **Meta-Summary Injection**: The prompt receives a compact Meta-Summary (the Table of Contents) + the **Active Chapter Summary** (~400 tokens total).
3. **On-Demand Chapter Zooming**: If a user asks *"How did we implement sequence monotonic numbering in Phase 4?"*, the engine pulls that specific archived Chapter ledger into Tier 4.

---

## 3. Memory Decay & Conflict Resolution

### The Current Baseline
Memories are persisted to PostgreSQL with `confidence` scores and `ON CONFLICT DO UPDATE`. The highest confidence / most recent item currently wins.

### The Gap (The "Stale Architecture" Problem)
Software architectures evolve constantly:
- Phase 1: Prototype with SQLite (`database = "sqlite"`).
- Phase 3: Transition to Neon PostgreSQL (`database = "neon_postgres"`).
If the SQLite fact was assigned a high confidence score of `0.95` and the PostgreSQL transition was stated casually (`0.85`), naive confidence ranking might retain the obsolete SQLite fact.
- This creates **Architectural Ghost Rules** where the LLM writes code for a deprecated stack.

### The Proposed Architecture

```
                       [Incoming Fact Extraction]
                                    │
                                    ▼
                     Does Key Exist in DB Already?
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
                 NO ▼                            YES ▼
            [Insert New Fact]           [Evaluate Semantics]
                                                    │
                               ┌────────────────────┴────────────────────┐
                               ▼                                         ▼
                     Compatible Update                        Contradiction Detected
               (e.g., Python 3.12 -> 3.14)                  (e.g., SQLite vs PostgreSQL)
                               │                                         │
                               ▼                                         ▼
                     [Update In-Place]                     [Temporal Decay / Prompt]
                                                           - Apply Half-Life Decay to Old Fact
                                                           - If delta > threshold: Auto-Replace
                                                           - If ambiguous: Ask User Confirmation
```

### Implementation Blueprint
1. **Temporal Half-Life Decay**:
   Apply an exponential decay formula to fact confidence over turns/time:
   $$C_{\text{effective}}(t) = C_0 \cdot e^{-\lambda \cdot \Delta t}$$
   Facts that are actively referenced or re-confirmed maintain high confidence; facts that are never mentioned slowly lose weight.
2. **Explicit Contradiction Guard**:
   When `MemoryExtractor` proposes a new fact for an existing key, compare values:
   - If mutually exclusive (e.g. `sqlite` vs `postgresql`, `flask` vs `fastapi`), the newly confirmed architectural decision actively deprecates the older fact.
   - For high-impact shifts, the system can prompt: *"You previously configured SQLite, but confirmed Neon PostgreSQL. Updating project memory."*
