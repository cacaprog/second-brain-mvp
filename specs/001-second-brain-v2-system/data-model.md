# Data Model: Second Brain v2

**Phase 1 output** | **Date**: 2026-04-21 | **Branch**: `001-second-brain-v2-system`

---

## Entities

### NoteRecord

Represents a raw personal knowledge artifact, canonical and immutable once ingested.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `str` | PK, SHA-256 of file content | Stable identity across renames |
| `title` | `str` | non-empty | Extracted from file (H1 or filename) |
| `body` | `str` | non-empty | Full text of the note |
| `tags` | `list[str]` | may be empty | Source system tags |
| `language` | `str` | `pt\|en\|fr\|es\|unknown` | Detected by langdetect |
| `source` | `str` | `notion\|keep\|kindle` | Source system type |
| `source_path` | `str` | unique, immutable | Absolute path to raw file |
| `created_at` | `str` | ISO 8601 | From file metadata or source system |
| `modified_at` | `str` | ISO 8601 | Updated on each file modification |
| `version` | `int` | ≥ 1, increments on modify | Concurrency version counter |
| `domain` | `str` | non-empty after classification | Primary domain slug |
| `secondary_domain` | `str\|None` | nullable | Set when top-2 scores within 0.05 |
| `status` | `str` | see state machine below | Current lifecycle position |
| `wiki_page` | `str\|None` | nullable | Slug of resulting wiki page |
| `word_count` | `int` | ≥ 0 | Used for `link_only` flag logic (< 100 words) |

#### NoteRecord Status State Machine

```
pending
  ├──[parse ok]───────────────────► classified
  └──[parse error]─────────────────► parsing_failed → manual_queue

classified
  ├──[dedup similarity ≥ 0.90]────► duplicate_candidate → human_gate (merge)
  ├──[fast-track eligible]─────────► fast_tracked → committing → committed
  ├──[human approve]───────────────► committing → committed
  ├──[human reject]────────────────► rejected → pending_review
  └──[commit error]────────────────► commit_failed → errors table

pending_review
  └──[requeue]─────────────────────► classified  (loop with rejection context)

deleted
  └──[source file removed; wiki page orphaned; lint flags; human decides]
```

---

### Proposal

LLM-generated recommendation for integrating a note into the wiki. Immutable after
creation — edits by the human reviewer produce a new `decision="edited"` record.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `str` | PK, UUID4 | Stable proposal identity |
| `note_id` | `str` | FK → notes.id | Source note |
| `note_version` | `int` | ≥ 1 | Note version at proposal time |
| `proposed_page` | `str` | lowercase-hyphenated | Target wiki page slug |
| `is_new_page` | `bool` | — | True if slug not in domain index |
| `link_only` | `bool` | — | True if note < 100 words, existing page only |
| `summary` | `str` | 2–3 sentences | Same language as note |
| `proposed_links` | `list[str]` | all slugs must exist in domain index | Cross-references |
| `confidence` | `float` | 0.0–1.0 | Reduced by 0.1 per stripped invalid link |
| `flag_contradiction` | `bool` | — | LLM-flagged internal contradiction |
| `flag_duplicate` | `bool` | — | LLM-flagged potential duplicate |
| `fast_track_eligible` | `bool` | set by pipeline, not LLM | All fast-track criteria met |
| `ollama_model` | `str` | — | Model ID for audit (e.g., `qwen3.5:9b`) |
| `created_at` | `str` | ISO 8601 | Proposal generation timestamp |
| `decision` | `str\|None` | `approved\|edited\|fast_tracked\|rejected\|None` | Human/auto decision |
| `rejection_reason` | `str\|None` | nullable | Required when decision=rejected |
| `decided_at` | `str\|None` | ISO 8601, nullable | When decision was made |
| `edited_content` | `str\|None` | nullable | Human-edited wiki page content if decision=edited |

#### Fast-Track Eligibility Rules (all must be true)

```python
fast_track_eligible = (
    confidence >= 0.85
    and not flag_contradiction
    and not flag_duplicate
    and not is_new_page
    and not link_only  # link_only still requires human (adds to existing page)
    and all(link_exists_in_domain_index(l) for l in proposed_links)
)
```

---

### WikiPage (markdown file + YAML front matter)

Compiled, synthesized concept page. The primary artifact stored in ChromaDB and
served by the query and MCP layers. Lives in `wiki/domains/{domain}/{slug}.md`.

#### YAML Front Matter

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
disputes: []
confidence: 0.82
---
```

| Field | Type | Description |
|-------|------|-------------|
| `slug` | `str` | Unique identifier, lowercase-hyphenated |
| `domain` | `str` | Owning domain |
| `languages` | `list[str]` | Languages present in source notes |
| `created` | `date` | ISO date of first commit |
| `updated` | `date` | ISO date of last commit |
| `version` | `int` | Increments on each approved update |
| `sources` | `list[str]` | Source note paths (relative to `data/raw/`) |
| `links` | `list[str]` | Approved cross-reference slugs |
| `disputes` | `list[str]` | Human-authored cross-page disagreements |
| `confidence` | `float` | Aggregate confidence of contributing proposals |

#### Page Size Constraint

Pages MUST NOT exceed ~2,000 words. Structural lint flags pages approaching this
limit so they can be split before Ollama's query context window is exceeded.

---

### CommitRecord

Transaction coordinator entry. Enables idempotent replay of interrupted commits.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `str` | PK, UUID4 | Commit identity |
| `proposal_id` | `str` | FK → proposals.id | Source proposal |
| `status` | `str` | `committing\|committed\|failed` | Current state |
| `git_hash` | `str\|None` | nullable | Set after successful git commit |
| `started_at` | `str` | ISO 8601 | When commit began |
| `finished_at` | `str\|None` | ISO 8601, nullable | When commit completed |
| `error_message` | `str\|None` | nullable | Set on failure |

#### Commit Operation Sequence (all steps idempotent except last)

```
1. db.begin_commit(proposal_id)          → status = "committing"
2. write_wiki_page(page_path, content)   → idempotent (overwrite)
3. vector_store.upsert(slug, content)    → idempotent (by slug ID)
4. register_cross_links(links)           → idempotent (upsert in cross-links.md)
5. update_domain_index(domain, slug)     → idempotent (upsert row in index.md)
6. git_commit_wiki(page_path)            → produces git_hash
7. db.finish_commit(commit_id, git_hash) → status = "committed"  ← only non-idempotent
```

On restart: replay all rows where `status = "committing"` from step 1.

---

### ErrorRecord

Dead-letter queue for pipeline failures requiring human attention.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `str` | PK, UUID4 | Error identity |
| `note_id` | `str` | FK → notes.id | Affected note |
| `stage` | `str` | `parsing\|classifying\|proposing\|committing` | Where failure occurred |
| `error_message` | `str` | — | Exception text |
| `occurred_at` | `str` | ISO 8601 | When the error was recorded |
| `resolved` | `int` | 0 or 1 | Resolved by human action |

---

### DomainConfig

Configuration entity (read from `config/domains.yaml`, not stored in SQLite).

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Domain slug |
| `seeds` | `list[str]` | Keyword seed terms for classifier |
| `max_pages` | `int` | Default 300; lint flags when exceeded |
| `centroid_embedding` | `np.ndarray\|None` | Pre-computed at setup, cached in memory |

---

## SQLite Schema

All tables in `db/brain.sqlite`. WAL mode enabled on connection open.

```sql
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS notes (
    id              TEXT PRIMARY KEY,   -- SHA-256 of content
    source_path     TEXT UNIQUE NOT NULL,
    title           TEXT NOT NULL,
    language        TEXT NOT NULL,
    source          TEXT NOT NULL,
    domain          TEXT,
    secondary_domain TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    wiki_page       TEXT,
    word_count      INTEGER NOT NULL DEFAULT 0,
    version         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL,
    modified_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proposals (
    id              TEXT PRIMARY KEY,   -- UUID4
    note_id         TEXT NOT NULL REFERENCES notes(id),
    note_version    INTEGER NOT NULL,
    proposed_page   TEXT NOT NULL,
    is_new_page     INTEGER NOT NULL,   -- 0/1
    link_only       INTEGER NOT NULL,   -- 0/1
    summary         TEXT NOT NULL,
    proposed_links  TEXT NOT NULL,      -- JSON array of slugs
    confidence      REAL NOT NULL,
    flag_contradiction INTEGER NOT NULL, -- 0/1
    flag_duplicate  INTEGER NOT NULL,   -- 0/1
    fast_track_eligible INTEGER NOT NULL, -- 0/1
    ollama_model    TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    decision        TEXT,
    rejection_reason TEXT,
    decided_at      TEXT,
    edited_content  TEXT
);

CREATE TABLE IF NOT EXISTS commits (
    id              TEXT PRIMARY KEY,   -- UUID4
    proposal_id     TEXT NOT NULL REFERENCES proposals(id),
    status          TEXT NOT NULL,      -- committing/committed/failed
    git_hash        TEXT,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    error_message   TEXT
);

CREATE TABLE IF NOT EXISTS errors (
    id              TEXT PRIMARY KEY,   -- UUID4
    note_id         TEXT NOT NULL REFERENCES notes(id),
    stage           TEXT NOT NULL,
    error_message   TEXT NOT NULL,
    occurred_at     TEXT NOT NULL,
    resolved        INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_notes_status ON notes(status);
CREATE INDEX IF NOT EXISTS idx_notes_domain ON notes(domain);
CREATE INDEX IF NOT EXISTS idx_proposals_note_id ON proposals(note_id);
CREATE INDEX IF NOT EXISTS idx_commits_status ON commits(status);
CREATE INDEX IF NOT EXISTS idx_errors_resolved ON errors(resolved);
```

---

## Relationships

```
NoteRecord (1) ──────── (0..N) Proposal
Proposal   (1) ──────── (0..1) CommitRecord
NoteRecord (1) ──────── (0..N) ErrorRecord
NoteRecord (0..N) ─────── (0..1) WikiPage  [via wiki_page slug]
WikiPage   (0..N) ─────── (0..N) WikiPage  [via links[] cross-references]
```

---

## State Invariants

1. A `NoteRecord` with `status="committed"` MUST have a non-null `wiki_page`.
2. A `CommitRecord` with `status="committed"` MUST have a non-null `git_hash`.
3. A `Proposal` with `fast_track_eligible=True` MUST have `is_new_page=False`.
4. All slugs in `proposed_links` MUST exist in the domain's `index.md` at proposal
   creation time (invalid links are stripped before saving the proposal).
5. A wiki page's `links[]` front-matter field MUST only contain slugs that exist
   as files in `wiki/domains/*/` — validated by structural lint.
