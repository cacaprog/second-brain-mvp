<!--
SYNC IMPACT REPORT
==================
Version change: (unversioned template) → 1.0.0
Bump rationale: MAJOR — first ratification, all principles defined from scratch.

Modified principles: N/A (initial constitution)

Added sections:
  - Core Principles (7 principles from SDD Appendix A)
  - Technology Stack Constraints
  - Calibration & Quality Gates
  - Governance

Removed sections: N/A

Templates reviewed:
  - .specify/templates/plan-template.md      ✅ no changes needed (Constitution Check
                                                section is generic and will reference this
                                                document at plan time)
  - .specify/templates/spec-template.md      ✅ no changes needed
  - .specify/templates/tasks-template.md     ✅ no changes needed

Follow-up TODOs:
  - None. All fields resolved from second-brain-sdd.md.
-->

# Second Brain v2 Constitution

## Core Principles

### I. Human Gate — Ollama Proposes, Humans Commit

No LLM output reaches the wiki without passing through the human verification gate.
The fast-track path (confidence ≥ 0.85, no flags, existing page only) MUST write to
`batch_log.jsonl` for asynchronous human review; retroactive revert via `git revert`
MUST always be possible. New wiki pages and new `[[wikilinks]]` MUST NEVER be
auto-approved — they require real-time human confirmation.

**Rationale**: A hallucinated `[[wikilink]]` is structural corruption in a Zettelkasten.
Unlike a bad RAG answer (contained), a false associative trail compounds across all
subsequent queries. The gate exists to prevent this existential failure mode.

### II. Wiki-First Indexing

ChromaDB MUST index compiled wiki pages only — never raw notes. Semantic search
and Ollama synthesis operate exclusively over synthesized, cross-linked knowledge.
Raw notes are inputs to the ingestion pipeline; they are not queryable artifacts.

**Rationale**: Indexing raw notes produces passive retrieval with no accumulation.
The system's value comes from synthesis: the compiled wiki page is the unit of
knowledge, not the note that contributed to it.

### III. Domain-Bounded Context

Each Ollama inference call MUST receive at most one domain `index.md` plus the
incoming note. Domain indices MUST remain within ~3,000–4,000 tokens (≤ 300 pages
at ~15 tokens per entry). Domains exceeding 300 pages MUST be split into
sub-domains. The full note corpus MUST NEVER be loaded into any single LLM call.

**Rationale**: Local 7B–8B models have reliable output within 4,000–8,000 tokens.
Domain sharding is what makes the system scale past 100 notes without hallucination.
This is the primary architectural constraint — all scale decisions derive from it.

### IV. Immutable Raw Sources

`data/raw/` is append-only. Files in this directory MUST NEVER be modified or
deleted by any pipeline component. All derived artifacts (wiki pages, ChromaDB
embeddings, SQLite records) are downstream of raw sources. Ground truth lives in
`data/raw/`; everything else is derived and reconstructable.

**Rationale**: Immutability guarantees that the ingestion pipeline can always be
re-run from scratch. It decouples source capture from knowledge synthesis, and
prevents accidental data loss from pipeline bugs.

### V. Audit Trail First-Class

`brain.sqlite` MUST record every proposal, every human decision, every commit
status, and every error. The NoteRecord state machine (§5 of the SDD) MUST be
respected in all pipeline code. Silent partial states are not permitted: operations
MUST either complete fully, replay deterministically, or be recorded in the `errors`
table. The SQLite commit coordinator MUST be the single source of truth for
in-flight commits.

**Rationale**: The audit trail is the basis for calibration (rejection rate by domain),
model drift detection, and future learning. It also enables safe recovery: on startup,
any commit in `status = "committing"` MUST be idempotently replayed.

### VI. Local and Private

No note content, no embedding, no query, and no response MAY leave the local
machine. All LLM inference MUST use Ollama. All vector search MUST use the local
ChromaDB instance. External API calls are not permitted for any core pipeline
operation. The MCP server (read-only, localhost port 8765) is the only permitted
interface to external agents, and it MUST enforce read-only access.

**Rationale**: This is a design constraint, not a preference. The entire value of
the system rests on the user's trust that their personal knowledge remains private.

### VII. Fail Visibly, Recover Deterministically

All pipeline failures MUST be recorded in the `errors` table with stage, message,
and timestamp. The system MUST surface failures explicitly (CLI output, lint report,
or `errors` table) rather than silently skipping or degrading. Every mutating
operation in the commit layer MUST be idempotent so that startup replay is always
safe. `status = "failed"` commits unresolved for > 24 hours MUST be flagged by
structural lint.

**Rationale**: In a long-running personal knowledge system, silent failures
accumulate into invisible corruption. Visible failure + deterministic recovery is
cheaper than debugging mystery state months later.

## Technology Stack Constraints

The following technology choices are binding for v2. Changes require a constitution
amendment with explicit rationale for why the constraint no longer holds.

- **LLM inference**: Ollama only (local). Active model: `qwen3.5:9b`. Model is
  swappable via `config/settings.yaml` (key: `ollama.model`). All `ollama.chat()`
  calls MUST include `think=False` (qwen3.5:9b is a thinking model — omitting it
  exhausts the token budget before producing output).
- **Bi-encoder**: `BAAI/bge-m3`. Fallback:
  `paraphrase-multilingual-MiniLM-L12-v2` (384d) for machines with < 8 GB RAM.
- **Cross-encoder**: `BAAI/bge-reranker-v2-m3` for cross-domain re-ranking only.
- **Vector store**: ChromaDB (persistent, one collection per domain).
- **Metadata store / commit coordinator**: SQLite (`db/brain.sqlite`).
- **Wiki format**: Markdown + YAML front matter. MUST be Obsidian-compatible.
- **Wiki versioning**: git. Every approved proposal MUST produce a `git commit`.
- **Language**: Python 3.11+.
- **Supported note languages**: Portuguese, English, French, Spanish.

## Calibration & Quality Gates

Before enabling fast-track automation, the system MUST pass a calibration sprint:

- Ingest the first 500 notes in manual-only mode (no fast-track).
- Go/no-go criterion: rejection rate MUST fall below 15% per domain before
  fast-track is enabled for that domain.
- Domain taxonomy MUST be validated empirically before full migration.
- Obsidian cross-domain backlinks MUST be confirmed working with ≥ 10 cross-domain
  pages before finalizing the directory structure.

Ongoing quality gates:
- Structural lint MUST run daily (or after every 10 commits).
- Semantic lint MUST run monthly on pages modified in the last 30 days.
- The `batch_log.jsonl` MUST be reviewed weekly during active migration.

## Governance

This constitution supersedes all other development practices and preferences for
Second Brain v2. Any decision that conflicts with a principle stated here MUST be
escalated to a constitution amendment — not silently overridden.

**Amendment procedure**:
1. Document the proposed change and its rationale.
2. Identify which principle(s) are affected and whether the change is
   MAJOR (backward incompatible removal/redefinition), MINOR (new section or
   material expansion), or PATCH (clarification, wording, non-semantic fix).
3. Increment `CONSTITUTION_VERSION` accordingly.
4. Update `LAST_AMENDED_DATE` to the date of the change.
5. All in-flight feature specs and plans referencing changed principles MUST be
   reviewed for consistency.

**Compliance**: All implementation plans (plan.md) MUST include a Constitution Check
section before Phase 0 research begins. Any complexity that violates a principle
MUST be explicitly justified in the Complexity Tracking section.

**Version**: 1.0.0 | **Ratified**: 2026-04-21 | **Last Amended**: 2026-04-21
