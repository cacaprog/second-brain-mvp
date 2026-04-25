# Software Design Document — Second Brain v2

**Project:** Second Brain v2 — Hybrid Zettelkasten Knowledge System  
**Author:** Cairo Cananea  
**Version:** 0.2  
**Date:** 2026-04-21  
**Status:** Pre-implementation  
**Changelog:** v0.2 — Incorporated peer review findings: fast-track threshold, atomic commit via SQLite coordinator, update/delete handling, cross-domain re-ranking, two-tier lint, versioning/backup strategy, error state machine, MCP promoted to v2 scope, calibration sprint formalized.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Goals and non-goals](#2-goals-and-non-goals)
3. [Context and motivation](#3-context-and-motivation)
4. [System architecture](#4-system-architecture)
5. [Data model](#5-data-model)
6. [Directory structure](#6-directory-structure)
7. [Component design](#7-component-design)
8. [Two-phase ingestion pipeline](#8-two-phase-ingestion-pipeline)
9. [Query system](#9-query-system)
10. [Lint and maintenance](#10-lint-and-maintenance)
11. [Versioning and backup](#11-versioning-and-backup)
12. [Scale strategy](#12-scale-strategy)
13. [Technology stack](#13-technology-stack)
14. [Configuration](#14-configuration)
15. [Open questions and future work](#15-open-questions-and-future-work)

---

## 1. Overview

Second Brain v2 is a local-first personal knowledge management system designed to scale to 18,000+ notes while preserving the integrity of a multilingual Zettelkasten. It combines two complementary patterns:

- **RAG (Retrieval-Augmented Generation):** semantic search over compiled wiki pages via ChromaDB and multilingual embeddings, with cross-encoder re-ranking for cross-domain queries.
- **LLM Wiki (Karpathy pattern):** an LLM agent incrementally compiles raw notes into a structured, cross-linked markdown wiki, rather than re-deriving answers from raw documents at query time.

The key architectural insight is that the LLM never operates on the full 18,000-note corpus at once. Instead, the corpus is sharded into domain wikis, each with a bounded context index. A human verification gate prevents link hallucination — the primary failure mode that corrupts Zettelkasten integrity at scale. The gate is tiered, not monolithic: high-confidence proposals that update existing pages are fast-tracked with batch log review; new pages and new links always require real-time human approval.

All computation runs locally via Ollama. No data leaves the machine.

---

## 2. Goals and non-goals

### Goals

- Store all notes in one place with a single canonical structure.
- Connect related notes through LLM-proposed, human-approved `[[wikilinks]]`.
- Amplify knowledge by compiling raw notes into persistent, synthesized concept pages.
- Run entirely locally using Ollama for LLM inference and ChromaDB for vector search.
- Support multilingual content natively: Portuguese, English, French, Spanish.
- Scale to 18,000+ notes without context window overflow or link hallucination.
- Preserve Zettelkasten principles: atomicity, explicit links, emergent structure.
- Handle note updates and deletions gracefully without corrupting the wiki layer.
- Expose the wiki as an MCP resource for use by Claude Code and compatible agents.

### Non-goals

- Cloud storage or sync (out of scope for v2).
- Real-time collaborative editing.
- Mobile interface.
- Fully automatic link approval — the fast-track threshold applies only to safe updates to existing pages; new pages and new links always require human confirmation.
- Fine-tuning any LLM model (v3 feature).
- Obsidian plugin (v3 feature — CLI is sufficient for v2).

---

## 3. Context and motivation

### The problem with pure RAG (current Second Brain MVP)

The existing system (ChromaDB + multilingual-e5-large + Gradio) solves retrieval correctly but never synthesizes. Every query re-derives answers from raw chunks. Cross-note reasoning — "what is my evolving mental model on X?" — is beyond its reach. The system is passive and non-accumulating.

### The problem with pure LLM Wiki (Karpathy pattern)

The LLM Wiki pattern was validated up to approximately 80–100 articles before context window overflow caused confident hallucinations by blending disparate notes. At 18,000 notes, loading even the index into a local model's context is impossible. The pattern assumes a bounded, curated corpus — not a growing Zettelkasten.

### Why link hallucination is the existential threat

In a standard RAG system, a hallucinated answer is bad but contained. In a Zettelkasten, a hallucinated `[[wikilink]]` is structural corruption: it creates a false associative trail that compounds over subsequent queries. The human verification gate exists specifically to prevent this. The gate is tiered, not eliminated.

### The hybrid solution

Second Brain v2 layers the two patterns:

1. Raw notes are parsed and classified into domain shards.
2. Per-domain, an Ollama agent reads a bounded context index and proposes wiki patches.
3. High-confidence proposals (existing pages only) are fast-tracked; new pages and new links require explicit human approval.
4. On approval, a compiled markdown wiki page is written (via SQLite-coordinated atomic commit) and ChromaDB is updated — indexing the wiki page, not the raw note.
5. Semantic search runs over synthesized knowledge, with cross-encoder re-ranking for cross-domain queries.

---

## 4. System architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Raw sources                          │
│   data/raw/notion/   data/raw/keep/   data/raw/kindle/      │
└───────────────────────────┬─────────────────────────────────┘
                            │ file watcher (create / modify / delete)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Phase 1 — Automated                      │
│  Parser → Dedup check → Domain classifier → Ollama proposal │
│  (Ollama reads domain index only — bounded context)         │
└───────────────────────────┬─────────────────────────────────┘
                            │ proposal object (JSON)
                            ▼
              ┌─────────────────────────┐
              │  Fast-track eligible?   │
              │  confidence > 0.85      │
              │  no flags, links exist  │
              │  updating existing page │
              └──────┬──────────┬───────┘
               yes   │          │  no (new page / new link / flagged)
                     ▼          ▼
          ┌──────────────┐  ┌──────────────────────────────┐
          │ Auto-approve │  │  Phase 2 — Human gate        │
          │ + batch log  │  │  CLI diff → approve/edit/    │
          └──────┬───────┘  │  reject                      │
                 │          └──────────────┬───────────────┘
                 └──────────────┬──────────┘
                                │ approved
                                ▼
┌─────────────────────────────────────────────────────────────┐
│          Commit layer (SQLite-coordinated)                  │
│  status → "committing" → file write → ChromaDB upsert       │
│  → cross-links update → git commit → status → "committed"   │
│  Idempotent replay on startup for unfinished commits        │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     Query layer                             │
│  ChromaDB bi-encoder retrieval → cross-encoder re-rank      │
│  → Ollama synthesis → response with [[wikilink]] citations  │
└──────────────────────────────┬──────────────────────────────┘
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
┌─────────────────────────┐     ┌───────────────────────────┐
│  Structural lint        │     │  MCP server (read-only)   │
│  (Python, daily)        │     │  Claude Code / agents     │
│  + Semantic lint        │     └───────────────────────────┘
│  (Ollama, monthly)      │
└─────────────────────────┘
```

---

## 5. Data model

### NoteRecord — parsed raw note

```python
@dataclass
class NoteRecord:
    id: str           # SHA-256 of file content
    title: str
    body: str
    tags: list[str]
    language: str     # "pt" | "en" | "fr" | "es"
    source: str       # "notion" | "keep" | "kindle"
    source_path: str  # original file path (immutable)
    created_at: str   # ISO 8601
    modified_at: str  # ISO 8601 — updated on file modification
    version: int      # increments on each modification
    domain: str       # assigned by domain classifier
    status: str       # see state machine below
```

#### NoteRecord status state machine

```
pending
  ├──[parse ok]──────────────────► classified
  └──[parse error]────────────────► parsing_failed → manual_queue

classified
  ├──[dedup: similarity ≥ 0.9]───► duplicate_candidate → human_gate (merge proposal)
  ├──[fast-track eligible]───────► fast_tracked → committing → committed
  ├──[human approve]─────────────► committing → committed
  ├──[human reject]──────────────► rejected → pending_review
  └──[commit error]──────────────► commit_failed → errors table

pending_review
  └──[requeue with reason]───────► classified  (loop)

deleted
  └──[source file removed; wiki page orphaned; lint flags; human decides]
```

### Proposal — Ollama output

```python
@dataclass
class Proposal:
    note_id: str
    proposed_page: str         # wiki page slug (existing or new)
    is_new_page: bool          # True if proposed_page does not yet exist
    link_only: bool            # True: add source ref to existing page only
    summary: str               # 2–3 sentences, same language as note
    proposed_links: list[str]  # [[wikilink]] slugs — existing index entries only
    confidence: float          # 0.0–1.0
    flag_contradiction: bool
    flag_duplicate: bool
    fast_track_eligible: bool  # set by pipeline, not Ollama
    ollama_model: str          # for audit trail
    created_at: str
```

### WikiPage — compiled concept page (markdown + YAML front matter)

```yaml
---
slug: antifragility
domain: philosophy
languages: [pt, en]
created: 2026-04-21
updated: 2026-04-21
version: 3
sources: [kindle/antifragile-ch3, notion/taleb-notes]
links: [via-negativa, optionality, black-swan]
disputes: []          # explicit cross-page disagreements (human-authored)
confidence: 0.82
---

## Antifragility

[Body: synthesized concept text, 100–400 words]

## Sources
- [[kindle/antifragile-ch3]]
- [[notion/taleb-notes]]

## Related
- [[via-negativa]]
- [[optionality]]
- [[black-swan]]
```

### SQLite tables (unified `brain.sqlite`)

**`notes`** — canonical note lifecycle:

| column | type | notes |
|---|---|---|
| id | TEXT PK | SHA-256 of content |
| source_path | TEXT | original file path |
| version | INTEGER | increments on modification |
| domain | TEXT | assigned domain |
| status | TEXT | state machine value |
| wiki_page | TEXT | slug of resulting wiki page (nullable) |
| created_at | TEXT | ISO 8601 |
| modified_at | TEXT | ISO 8601 |

**`proposals`** — full audit trail:

| column | type | notes |
|---|---|---|
| id | TEXT PK | UUID |
| note_id | TEXT FK | references notes.id |
| note_version | INTEGER | version of note at proposal time |
| proposal_json | TEXT | full Proposal as JSON |
| decision | TEXT | approved / edited / fast_tracked / rejected |
| rejection_reason | TEXT | nullable |
| decided_at | TEXT | ISO 8601 |

**`commits`** — transaction coordinator:

| column | type | notes |
|---|---|---|
| id | TEXT PK | UUID |
| proposal_id | TEXT FK | references proposals.id |
| status | TEXT | committing / committed / failed |
| started_at | TEXT | ISO 8601 |
| finished_at | TEXT | ISO 8601, nullable |

**`errors`** — dead-letter queue:

| column | type | notes |
|---|---|---|
| id | TEXT PK | UUID |
| note_id | TEXT FK | references notes.id |
| stage | TEXT | parsing / classifying / proposing / committing |
| error_message | TEXT | exception text |
| occurred_at | TEXT | ISO 8601 |
| resolved | INTEGER | 0 / 1 |

---

## 6. Directory structure

```
second-brain-v2/
├── src/
│   ├── watcher.py           # File system watcher (create / modify / delete)
│   ├── models.py            # NoteRecord, Proposal, WikiPage dataclasses
│   ├── notion_parser.py     # Existing — parse Notion markdown exports
│   ├── keep_parser.py       # Existing — parse Google Keep JSON
│   ├── kindle_parser.py     # Existing — parse Kindle clippings
│   ├── dedup.py             # Pre-commit similarity check via ChromaDB
│   ├── classifier.py        # Domain classifier (keyword + embedding)
│   ├── ollama_agent.py      # Proposal engine — calls Ollama
│   ├── review_cli.py        # Human gate — diff display + decision capture
│   ├── commit.py            # SQLite-coordinated atomic commit
│   ├── wiki_store.py        # Read/write wiki markdown, manage wikilinks
│   ├── vector_store.py      # ChromaDB wrapper + cross-encoder re-ranker
│   ├── query.py             # Query layer — retrieval + Ollama synthesis
│   ├── lint.py              # Two-tier lint (structural + semantic)
│   ├── mcp_server.py        # MCP resource server (read-only)
│   └── app.py               # Optional Gradio UI (modified from MVP)
│
├── wiki/                    # Git repository — full history per page
│   ├── domains/
│   │   ├── analytics/
│   │   │   ├── index.md     # One-liner per concept, fits Ollama context
│   │   │   ├── mmm-robyn.md
│   │   │   └── attribution-models.md
│   │   ├── philosophy/
│   │   │   ├── index.md
│   │   │   ├── antifragility.md
│   │   │   └── via-negativa.md
│   │   └── [other domains]/
│   ├── cross-links.md       # Global cross-domain link registry
│   └── lint/
│       ├── structural-2026-04-21.json
│       └── semantic-2026-04-01.json
│
├── data/
│   ├── raw/                 # Append-only — never modified by pipeline
│   │   ├── notion/
│   │   ├── keep/
│   │   └── kindle/
│   └── processed/
│       └── chroma/          # ChromaDB persistent storage
│
├── db/
│   ├── brain.sqlite
│   └── backups/
│
├── config/
│   ├── ollama_model.txt
│   ├── domains.yaml
│   └── settings.yaml
│
└── requirements.txt
```

---

## 7. Component design

### 7.1 File watcher (`watcher.py`)

Uses `watchdog` to monitor `data/raw/` recursively. Handles three event types:

- `on_created` → queue `IngestJob(event="create")`
- `on_modified` → queue `IngestJob(event="modify")`, increment `version` in `notes` table; pipeline generates a patch proposal comparing existing wiki page to updated note
- `on_deleted` → set note `status = "deleted"`; wiki page is orphaned and flagged by next structural lint — never auto-deleted

```python
class RawSourceHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            ingest_queue.put(IngestJob(path=event.src_path, event="create"))
    def on_modified(self, event):
        if not event.is_directory:
            ingest_queue.put(IngestJob(path=event.src_path, event="modify"))
    def on_deleted(self, event):
        if not event.is_directory:
            db.mark_deleted(source_path=event.src_path)
```

### 7.2 Duplicate check (`dedup.py`)

Runs before the Ollama proposal. Embeds the incoming note and queries all domain ChromaDB collections. If any existing wiki page has cosine similarity ≥ 0.9, generates a merge proposal instead of a new-page proposal. The human sees both pages side by side and approves the merge, selects the existing page as canonical, or confirms they are genuinely distinct.

```python
DUPLICATE_THRESHOLD = 0.90

def check_duplicate(note: NoteRecord) -> str | None:
    """Returns existing wiki page slug if a near-duplicate is found, else None."""
    embedding = model.encode(f"query: {note.body}").tolist()
    for domain in list_domains():
        results = get_collection(domain).query(
            query_embeddings=[embedding], n_results=1,
            include=["distances", "metadatas"]
        )
        if results["distances"][0] and (1 - results["distances"][0][0]) >= DUPLICATE_THRESHOLD:
            return results["metadatas"][0][0]["slug"]
    return None
```

### 7.3 Domain classifier (`classifier.py`)

Two-stage classification. First pass: keyword matching against `domains.yaml` seed terms (fast, zero-cost). If ambiguous (top-2 scores within 0.1), falls back to cosine similarity against domain centroid embeddings (pre-computed at setup).

Multi-domain notes are permitted: the classifier returns a primary domain and an optional secondary domain. The proposal is generated for the primary domain only; the secondary classification is stored for future cross-link suggestions.

```yaml
# config/domains.yaml
domains:
  analytics:
    seeds: ["MMM", "Robyn", "atribuição", "churn", "funil", "ROAS", "mídia paga"]
  philosophy:
    seeds: ["Taleb", "Hadot", "estoicismo", "antifragile", "Seneca", "via negativa"]
  data-science:
    seeds: ["regressão", "clustering", "survival analysis", "random forest", "feature"]
  fiction:
    seeds: ["Tolkien", "worldbuilding", "narrative", "personagem", "enredo"]
  personal:
    seeds: ["diário", "journal", "reflexão", "meta", "hábito"]
```

### 7.4 Ollama proposal engine (`ollama_agent.py`)

Reads only the target domain's `index.md` plus the new note. Returns structured JSON.

**Error handling:**
- Malformed JSON → retry once with stricter prompt; on second failure → `errors` table
- Ollama timeout (>60s) → `errors` table with `stage="proposing"`
- `proposed_links` referencing slugs not in domain index → strip invalid links, set `confidence -= 0.1`

The `link_only` flag is set by the pipeline when the note body is short (<100 words) and clearly about an already-existing concept. No new wiki page is created — only the existing page's Sources section is updated.

**Fast-track eligibility** is determined after the proposal is returned (never by Ollama itself):

```python
def is_fast_track(proposal: Proposal) -> bool:
    return (
        proposal.confidence >= 0.85
        and not proposal.flag_contradiction
        and not proposal.flag_duplicate
        and not proposal.is_new_page
        and all(link_exists_in_index(l) for l in proposal.proposed_links)
    )
```

Fast-tracked proposals are committed immediately and appended to `batch_log.jsonl`. The human reviews this log asynchronously (weekly or on-demand) and can retroactively reject any entry, which triggers a git revert.

**Proposal prompt:**

```python
PROPOSAL_PROMPT = """
You are maintaining a Zettelkasten wiki. Propose how a new note should be
integrated — do not invent connections that aren't clearly present.

Existing concepts in this domain (index):
{domain_index}

New note:
Title: {title}
Body: {body}
Language: {language}

Rules:
- Only propose [[wikilinks]] to concepts explicitly in the index above.
- If no link is warranted, return an empty proposed_links list.
- Do not hallucinate connections.
- Respond with valid JSON only, no preamble.

JSON schema:
{{
  "summary": "string (2-3 sentences, same language as note)",
  "proposed_page": "string (slug: lowercase-hyphenated)",
  "is_new_page": bool,
  "link_only": bool,
  "proposed_links": ["slug1", "slug2"],
  "confidence": float,
  "flag_contradiction": bool,
  "flag_duplicate": bool
}}
"""
```

### 7.5 Review CLI (`review_cli.py`)

Presents the proposal as a colored diff using `rich`. Keybindings:

| Key | Action |
|---|---|
| `a` | Approve |
| `e` | Approve + edit (opens `$EDITOR`) |
| `r` | Reject (prompts for reason) |
| `s` | Skip (defer to end of session queue) |
| `b` | Batch mode (approve all remaining fast-track candidates) |

Target: under 10 seconds per unambiguous proposal.

### 7.6 Commit layer (`commit.py`) — SQLite-coordinated atomic commit

The file-lock-only approach of v0.1 was not truly atomic across file, ChromaDB, and SQLite. The corrected pattern uses SQLite as the transaction coordinator. All operations after the initial write are idempotent, so replaying a partial commit on startup is always safe.

```python
def commit(proposal: Proposal, note: NoteRecord) -> None:
    commit_id = db.begin_commit(proposal.id)   # status = "committing"

    try:
        page_path = wiki_page_path(note.domain, proposal.proposed_page)

        # All steps below are idempotent — safe to replay on startup
        new_content = render_wiki_page(read_if_exists(page_path), proposal, note)
        write_wiki_page(page_path, new_content)                          # idempotent

        vector_store.upsert(                                             # idempotent
            id=proposal.proposed_page, document=new_content,
            metadata={"domain": note.domain, "language": note.language,
                      "slug": proposal.proposed_page}
        )

        for link in proposal.proposed_links:
            register_cross_link(source=proposal.proposed_page, target=link)  # idempotent

        update_domain_index(note.domain, proposal.proposed_page, proposal.summary)

        git_commit_wiki(page_path, proposal)   # git add + git commit

        # Only non-idempotent step — done last
        db.finish_commit(commit_id)            # status = "committed"
        db.update_note_status(note.id, "committed", wiki_page=proposal.proposed_page)

    except Exception as e:
        db.fail_commit(commit_id, str(e))      # status = "failed"
        db.log_error(note.id, "committing", str(e))
        raise

# On startup:
def replay_unfinished_commits():
    for commit in db.get_commits_by_status("committing"):
        proposal = db.get_proposal(commit.proposal_id)
        note = db.get_note(proposal.note_id)
        commit(proposal, note)   # idempotent replay
```

### 7.7 Vector store and re-ranker (`vector_store.py`)

One ChromaDB collection per domain. Cross-domain search uses a two-stage pipeline:

```python
bi_encoder = SentenceTransformer("intfloat/multilingual-e5-large")
cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def search(query: str, domain: str = None, n_results: int = 5) -> list[dict]:
    q_embedding = bi_encoder.encode(f"query: {query}").tolist()

    if domain:
        # Single-domain: bi-encoder only, no re-ranking needed
        raw = get_collection(domain).query(
            query_embeddings=[q_embedding], n_results=n_results,
            include=["documents", "metadatas"]
        )
        return raw["documents"][0]

    # Cross-domain: bi-encoder retrieves candidates, cross-encoder re-ranks
    candidates = []
    for d in list_domains():
        results = get_collection(d).query(
            query_embeddings=[q_embedding], n_results=10,
            include=["documents", "metadatas"]
        )
        candidates.extend(zip(results["documents"][0], results["metadatas"][0]))

    pairs = [[query, doc] for doc, _ in candidates]
    scores = cross_encoder.predict(pairs)
    ranked = sorted(zip(scores, candidates), reverse=True)
    return [doc for _, (doc, _) in ranked[:n_results]]
```

The cross-encoder (`ms-marco-MiniLM-L-6-v2`, ~85MB) adds ~200ms per cross-domain query on CPU — acceptable for interactive use.

### 7.8 MCP server (`mcp_server.py`)

Exposes the wiki as a read-only MCP resource, enabling Claude Code and other MCP-compatible agents to query the knowledge base directly. Thin wrapper over `query.py`:

```python
from mcp import FastMCP
from query import search_and_synthesize
from wiki_store import read_wiki_page_by_slug

mcp = FastMCP("second-brain")

@mcp.resource("wiki://{slug}")
def get_wiki_page(slug: str) -> str:
    """Return a single compiled wiki page by slug."""
    return read_wiki_page_by_slug(slug)

@mcp.tool()
def query_knowledge_base(question: str, domain: str = None) -> str:
    """Semantic search + Ollama synthesis over the compiled wiki."""
    return search_and_synthesize(question, domain=domain)

if __name__ == "__main__":
    mcp.run(port=8765)
```

The MCP server runs as a sidecar process. It never writes to the wiki.

---

## 8. Two-phase ingestion pipeline

### Phase 1 — Automated

| Step | Component | Input | Output |
|---|---|---|---|
| 1. Detect | `watcher.py` | Filesystem event | `IngestJob` in queue |
| 2. Parse | `*_parser.py` | Raw file | `NoteRecord` |
| 3. Dedup | `dedup.py` | `NoteRecord` + ChromaDB | Merge flag if similarity ≥ 0.9 |
| 4. Classify | `classifier.py` | `NoteRecord` | `NoteRecord` with `domain` |
| 5. Propose | `ollama_agent.py` | `NoteRecord` + domain index | `Proposal` JSON |
| 6. Route | pipeline | `Proposal` | Fast-track or human gate |

Ollama context per call: domain `index.md` (~2,000–4,000 tokens) + new note (~200–800 tokens).

### Phase 2 — Human gate

| Step | Component | Input | Output |
|---|---|---|---|
| 7. Review | `review_cli.py` | `Proposal` | Decision |
| 8. Commit | `commit.py` | Approved `Proposal` | Wiki + ChromaDB + git updated |

### Rejection and requeue

Rejected notes are set to `pending_review`. Weekly requeue pass re-runs with rejection reason as a negative example in the prompt.

### 8.4 Migration strategy — calibration sprint

**Sprint 1 — calibration (first 500 notes, 1–2 weeks)**

- Ingest 500 most recent notes (active working set).
- Run in manual-only mode (no fast-track) to observe proposal quality.
- Measure: rejection rate by domain, confidence distribution, duplicate false positive rate.
- Tune: `domains.yaml` seed terms, `DUPLICATE_THRESHOLD`, fast-track confidence floor.
- Go/no-go criterion: rejection rate below 15% per domain before proceeding.

**Sprint 2 — domain-by-domain (weeks 3–8)**

- Enable fast-track after calibration confirms thresholds.
- One domain per week, recency order (newest to oldest).
- Review `batch_log.jsonl` weekly before advancing to next domain.

**Sprint 3 — tail migration (weeks 9+)**

- Remaining older notes. Many will be caught by duplicate detection and route to merge proposals, reducing net review burden.

### Throughput estimate

| Mode | Notes/hour | Hours for 18,000 |
|---|---|---|
| v0.1 all-manual | ~120 | ~150 h total; ~50 h human |
| v0.2 fast-track (70%) | ~400 | ~45 h total; ~12–15 h human |

---

## 9. Query system

### Retrieval flow

```
User question
     │
     ▼
Language detection
     │
     ▼
Domain hint? (optional)
     ├── yes → bi-encoder, single domain collection
     └── no  → bi-encoder all domains (top-10 each)
                  → cross-encoder re-rank
                  → top-k wiki pages
                        │
                        ▼
               Ollama synthesis
               (wiki pages in context)
                        │
                        ▼
               Answer + [[wikilink]] citations
```

### Query prompt

```python
QUERY_PROMPT = """
You are answering questions using a personal knowledge base (Zettelkasten).
Use only the wiki pages provided. Cite sources using [[wikilink]] notation.
Do not add information not present in the pages below.
If the answer cannot be found, say so explicitly.

Wiki pages:
{retrieved_pages}

Question: {question}
"""
```

### Cross-language queries

`multilingual-e5-large` produces language-agnostic embeddings. A Portuguese query surfaces English wiki pages and vice versa. No special handling needed.

---

## 10. Lint and maintenance

### Tier 1 — Structural lint (daily, Python only, no LLM)

Runs in seconds. Fully deterministic. No LLM required.

| Check | Implementation |
|---|---|
| Orphan pages | Pages with no inbound entries in `cross-links.md` |
| Missing concepts | Slug references in page bodies with no corresponding file |
| Stale pages | `updated` > 90 days ago with ≥ 2 inbound links |
| Low-confidence pages | All source proposals had `confidence < 0.6` |
| Deleted-source orphans | Wiki pages whose source notes have `status = "deleted"` |
| Failed commits | `commits` rows with `status = "failed"` unresolved > 24h |

Output: `wiki/lint/structural-{date}.json`

### Tier 2 — Semantic lint (monthly, Ollama, recent pages only)

Runs on pages modified in the last 30 days only. Contradiction detection is scoped strictly to within a single page's body — not across pages. This avoids false positives from legitimately opposing perspectives.

```python
SEMANTIC_LINT_PROMPT = """
Read the following wiki page and identify:
1. internal_contradictions: statements within this page that directly
   contradict each other (logical contradiction only — not differing views).
2. unsupported_claims: assertions with no source reference.

Return JSON only.

Page: {page_slug}
Content:
{page_body}

{
  "internal_contradictions": [{"statement_a": "", "statement_b": ""}],
  "unsupported_claims": ["..."]
}
"""
```

**Cross-page disagreements** are handled by the human via the `disputes::` front-matter field — not by the LLM:

```yaml
disputes: [precautionary-principle]
```

### On-demand lint

```bash
python src/lint.py --tier structural
python src/lint.py --tier semantic --domain philosophy
python src/lint.py --after-commits 10
```

---

## 11. Versioning and backup

### Wiki versioning (git)

`wiki/` is a git repository. Every successful commit adds a `git commit`:

```python
def git_commit_wiki(page_path: str, proposal: Proposal) -> None:
    subprocess.run(["git", "-C", "wiki/", "add", str(page_path)], check=True)
    subprocess.run([
        "git", "-C", "wiki/", "commit", "-m",
        f"ingest: {proposal.proposed_page} (confidence={proposal.confidence:.2f})"
    ], check=True)
```

- Every approved proposal is a git commit.
- Reverting a bad approval: `git revert <commit-hash>`.
- Page history: `git log wiki/domains/philosophy/antifragility.md`.

`data/raw/` does not need git — files are immutable by design.

### Database backup (daily cron)

```bash
#!/bin/bash
DATE=$(date +%Y-%m-%d)
cp db/brain.sqlite db/backups/brain-${DATE}.sqlite
tar -czf db/backups/chroma-${DATE}.tar.gz data/processed/chroma/
find db/backups/ -mtime +30 -delete
```

### Hardware requirements

| Component | RAM |
|---|---|
| Ollama (Mistral 7B, 4-bit) | ~5.0 GB |
| multilingual-e5-large | ~1.3 GB |
| ms-marco-MiniLM-L-6-v2 | ~0.1 GB |
| ChromaDB (1,750 pages × 1024d) | ~0.1 GB |
| **Total** | **~6.5 GB** |

For machines with <8 GB RAM available for inference, the fallback embedding model is `paraphrase-multilingual-MiniLM-L12-v2` (384d, ~470 MB), requiring a ChromaDB re-index.

---

## 12. Scale strategy

### The fundamental constraint

Local Ollama models have effective context windows of 4,000–8,000 tokens for reliable output. A domain `index.md` with 200 concept entries at ~15 tokens each = ~3,000 tokens. This fits. The full 18,000-note corpus does not.

### Domain sharding rules

- Each domain: at most 300 concept pages.
- If a domain exceeds 300 pages, split into sub-domains (e.g., `analytics` → `analytics/mmm` + `analytics/attribution`).
- `cross-links.md` tracks cross-domain links without being loaded per-query.
- Global `index.md`: one line per domain — always fits in any local model's context.

### ChromaDB scaling

HNSW index scales to millions of vectors. Per-domain collections keep individual queries fast. The cross-encoder re-ranker adds ~200ms regardless of domain count. System will perform well to 100,000+ wiki pages.

### Proposed domain taxonomy (initial)

| Domain | Estimated pages |
|---|---|
| `analytics` | 200–300 |
| `philosophy` | 250–350 |
| `data-science` | 150–200 |
| `behavioral-economics` | 100–150 |
| `fiction` | 100–150 |
| `neuroscience` | 80–120 |
| `personal` | 100–200 |
| `marketing` | 150–200 |
| `career` | 50–100 |

Total estimated: 1,100–1,750 compiled pages from 18,000 raw notes (~10–15× compression).

---

## 13. Technology stack

| Component | Technology | Rationale |
|---|---|---|
| LLM inference | Ollama (local) | Privacy, zero API cost, model swap via config |
| Default model | Mistral 7B or LLaMA 3 8B | Good Portuguese support, 8K context |
| Bi-encoder | intfloat/multilingual-e5-large | Retained from MVP; 100+ languages, 1024d |
| Cross-encoder | ms-marco-MiniLM-L-6-v2 | Cross-domain re-ranking; 85MB, CPU-viable |
| Vector store | ChromaDB (persistent) | Scales to millions of vectors |
| File watcher | watchdog | Lightweight, cross-platform |
| Metadata store | SQLite (brain.sqlite) | Transaction coordinator + audit trail |
| Wiki format | Markdown + YAML front matter | Obsidian-compatible, LLM-readable, git-friendly |
| Wiki versioning | git | Full history; easy revert of bad approvals |
| Wiki viewer | Obsidian | Graph view, backlinks, wikilinks |
| CLI | Python (rich library) | Colored diff, keyboard shortcuts |
| MCP server | FastMCP | Exposes wiki to Claude Code and agents |
| Optional UI | Gradio | Retained from MVP |
| Language | Python 3.11+ | Ecosystem alignment with MVP |

### Ollama model selection

| Model | Context | Portuguese quality | Speed (CPU) |
|---|---|---|---|
| `mistral` | 8K | good | moderate |
| `llama3` | 8K | very good | moderate |
| `phi3` | 4K | fair | fast (low-RAM option) |
| `mixtral` | 32K | good | slow (semantic lint overnight) |

---

## 14. Configuration

### `config/settings.yaml`

```yaml
paths:
  raw_data: "data/raw"
  wiki: "wiki"
  chroma: "data/processed/chroma"
  db: "db/brain.sqlite"
  backup_dir: "db/backups"

ollama:
  model: "mistral"
  timeout_seconds: 60
  min_confidence: 0.5           # below this → errors table

ingestion:
  fast_track_confidence: 0.85   # above this + no flags + existing page → auto-approve
  duplicate_threshold: 0.90     # cosine similarity → merge proposal

embeddings:
  model: "intfloat/multilingual-e5-large"
  fallback_model: "paraphrase-multilingual-MiniLM-L12-v2"
  batch_size: 32

reranker:
  model: "cross-encoder/ms-marco-MiniLM-L-6-v2"
  cross_domain_candidates_per_domain: 10

domains:
  max_pages_per_domain: 300
  config_file: "config/domains.yaml"

lint:
  structural_schedule: "daily"
  semantic_schedule: "monthly"
  semantic_lookback_days: 30
  stale_days: 90
  run_structural_after_n_commits: 10

backup:
  retention_days: 30

languages:
  supported: [pt, en, fr, es]
  detection_library: "langdetect"

mcp:
  enabled: true
  port: 8765
  read_only: true
```

---

## 15. Open questions and future work

### Resolved from v0.1

- ~~Human gate bottleneck~~ → fast-track threshold (§7.4, §8.4)
- ~~Commit not truly atomic~~ → SQLite coordinator, idempotent replay (§7.6)
- ~~Update/delete handling missing~~ → `on_modified` / `on_deleted`, patch proposals, `deleted` status (§7.1, §5)
- ~~Cross-domain search naive~~ → cross-encoder re-ranker (§7.7)
- ~~Duplicate detection underspecified~~ → `dedup.py`, cosine ≥ 0.9, merge proposals (§7.2)
- ~~Lint contradiction over-scoped~~ → two-tier lint, semantic scoped to single-page body (§10)
- ~~No versioning/backup~~ → git for `wiki/`, cron backup for `db/` and `chroma/` (§11)
- ~~Error handling under-specified~~ → `errors` table, full state machine, startup replay (§5, §7.6)
- ~~MCP listed as v3~~ → promoted to v2 scope (§7.8)
- ~~Migration strategy informal~~ → calibration sprint with explicit go/no-go criteria (§8.4)

### Remaining open questions

1. **Obsidian cross-domain backlinks.** Obsidian scans the entire vault by default, so `[[analytics/mmm-robyn]]` referenced from a philosophy page should appear in `mmm-robyn.md`'s backlinks pane. Needs empirical confirmation before finalizing the directory structure. Test with 10 cross-domain pages before committing to the full taxonomy.

2. **Rejection learning systematization.** With >50 rejections per domain, a few-shot prompt using the top-3 historical rejection reasons per domain would improve proposal quality more reliably than one-shot requeue. Revisit after calibration sprint.

3. **Wiki page size ceiling.** A concept page accumulating many sources over time will eventually exceed Ollama's query context window. Practical ceiling: ~2,000 words per page. Structural lint should flag pages exceeding this threshold. Implement once 500+ pages are live.

### Future work (v3+)

| Feature | Notes |
|---|---|
| Fine-tuning on wiki | Train a small domain-specific model on the compiled wiki |
| Auto-tagging | Use wiki pages to suggest tags for new Notion/Keep notes at capture time |
| Writing assistant mode | Draft Dados & Devaneios posts grounded in wiki pages |
| Obsidian plugin | Surface proposals as modal dialogs; commit via local API |
| Kindle real-time sync | Replace manual clippings export with Kindle API polling |

---

## Appendix A — Key design principles

**1. Ollama proposes, humans commit.** No LLM output reaches the wiki without passing through the gate. Fast-track is a threshold with batch log review — retroactive revert is always possible via git.

**2. Index the wiki, not the raw notes.** ChromaDB holds embeddings of compiled wiki pages only. Semantic search runs over synthesized, cross-linked knowledge.

**3. Domain sharding bounds context.** Each Ollama inference call sees one domain index (~3,000 tokens). This is what makes the system scale past 100 notes without hallucination.

**4. Raw sources are immutable.** `data/raw/` is append-only. Ground truth; everything else is derived.

**5. The audit trail is first-class.** `brain.sqlite` stores every proposal, every decision, every commit status, every error. This is the basis for calibration, model drift detection, and future learning.

**6. Local and private by default.** No data leaves the machine. No API keys. This is a design constraint, not a preference.

**7. Fail visibly, recover deterministically.** The SQLite commit coordinator ensures interrupted operations are either fully replayed or clearly flagged. Silent partial states are not permitted.

---

## Appendix B — Review changelog (v0.1 → v0.2)

| Finding | Source | Resolution |
|---|---|---|
| Human gate bottleneck (~50h migration) | Both | Fast-track (confidence >0.85, no flags, existing page) + batch log + retroactive revert |
| Commit not atomic across file/ChromaDB/SQLite | Review 1 | SQLite coordinator; idempotent ops; startup replay |
| Update/delete handling absent | Review 2 | `on_modified` → patch proposal; `on_deleted` → orphan flag; `version` field on NoteRecord |
| Cross-domain search naive, no re-ranking | Review 1 | Cross-encoder re-ranker (ms-marco-MiniLM-L-6-v2); bi-encoder + cross-encoder two-stage |
| Duplicate detection underspecified | Both | `dedup.py`; cosine ≥ 0.9 → merge proposal, not new page |
| Lint contradiction detection over-scoped for 7B | Both | Two-tier lint; semantic = intra-page body only, monthly, last 30 days |
| No versioning or backup strategy | Review 1 | git for `wiki/`; daily cron for `db/` and `chroma/`; hardware requirements documented |
| Error handling under-specified | Review 1 | `errors` table; full NoteRecord state machine; `commits` table with replay |
| MCP listed as future v3 | Both | Promoted to v2 scope as `mcp_server.py` |
| Migration strategy informal | Review 1 | §8.4 calibration sprint; explicit go/no-go criterion (rejection rate <15% per domain) |
| Obsidian plugin | Review 2 | Deferred to v3; acknowledged in §15 |

---

*End of document — Second Brain v2 SDD v0.2*
