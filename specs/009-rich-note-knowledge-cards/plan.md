# Implementation Plan: Rich Note Knowledge Cards

**Branch**: `009-rich-note-knowledge-cards` | **Date**: 2026-04-25 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/009-rich-note-knowledge-cards/spec.md`

## Summary

Notes from any source (Kindle, Notion, Keep, etc.) with ≥ 4 paragraphs are routed to
the existing knowledge-card generation path (currently used only for articles/papers),
producing a structured four-section wiki page instead of a flat paragraph summary.
The threshold is configurable in `settings.yaml`. The review TUI labels these proposals
`[RICH NOTE]` so the reviewer knows the source is highlights, not a published article.

All changes are confined to three files: `src/watcher.py`, `src/review_cli.py`, and
`config/settings.yaml`. No schema migrations required.

## Technical Context

**Language/Version**: Python 3.11+  
**Primary Dependencies**: ollama, sqlite3 (stdlib), PyYAML, rich — all existing  
**Storage**: SQLite `db/brain.sqlite` — existing `notes.note_type` column (no migration)  
**Testing**: pytest (`tests/`)  
**Target Platform**: Linux, local machine  
**Project Type**: CLI pipeline tool  
**Performance Goals**: No new LLM calls beyond what the article path already uses  
**Constraints**: All LLM inference via local Ollama only (Constitution VI); `think=False` required  
**Scale/Scope**: Affects every note ingestion run; single-file changes only

## Constitution Check

*GATE: Must pass before implementation. Re-checked after design — all pass.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Human Gate | ✅ PASS | Rich notes go to human review queue (not fast-tracked); `fast_track_eligible=False` preserved from article path |
| II. Wiki-First Indexing | ✅ PASS | Output is a compiled wiki page written via `render_knowledge_card_page()`; raw notes never indexed |
| III. Domain-Bounded Context | ✅ PASS | `generate_knowledge_card()` passes only the note body (≤ 12,000 chars); no domain index needed for card generation |
| IV. Immutable Raw Sources | ✅ PASS | `data/raw/` untouched |
| V. Audit Trail | ✅ PASS | Proposal saved via `db.save_proposal()`; note status transitions follow existing state machine |
| VI. Local and Private | ✅ PASS | Ollama inference only; `think=False` enforced in existing `_call_ollama()` |
| VII. Fail Visibly | ✅ PASS | Timeout and empty-output errors raise `ValueError` → `db.log_error()` + `COMMIT_FAILED` status, identical to article path |

## Project Structure

### Documentation (this feature)

```text
specs/009-rich-note-knowledge-cards/
├── plan.md         ← this file
├── research.md     ← Phase 0 findings
├── data-model.md   ← Phase 1 data model
└── tasks.md        ← Phase 2 output (from /speckit-tasks)
```

### Source Code Changes

```text
config/
└── settings.yaml           ← add rich_note_paragraph_threshold: 4

src/
├── watcher.py              ← add _count_paragraphs() + update routing in _process_record()
└── review_cli.py           ← add [RICH NOTE] label in _render_diff()
```

**Structure Decision**: Single-project, minimal footprint. No new files. All logic
changes are additions to existing functions in existing files.

## Implementation Phases

### Phase 1 — Configuration & Paragraph Counter (Blocking Prerequisite)

Both tasks touch different files with no shared dependency — can be done in parallel.

**T001** — Add `rich_note_paragraph_threshold: 4` to `config/settings.yaml` under the
`ingestion:` block.

```yaml
ingestion:
  rich_note_paragraph_threshold: 4   # add this line
  fast_track_confidence: 0.85
  # ... rest unchanged
```

**T002** — Add `_count_paragraphs(body: str) -> int` to `src/watcher.py` as a
module-level helper before `_process_record`:

```python
def _count_paragraphs(body: str) -> int:
    import re
    return len([p for p in re.split(r"\n{2,}", body) if p.strip()])
```

(`re` is already imported at module level — no new import needed.)

**Checkpoint**: `_count_paragraphs("a\n\nb\n\nc")` returns 3.

---

### Phase 2 — Routing Logic (Depends on T001 + T002)

**T003** — In `src/watcher.py:_process_record()`, move the `note_type` assignment for
rich notes to before the `db.upsert_note(note)` call, and update the propose-block
routing condition.

Before the `db.upsert_note(note)` call (currently line 129), add:

```python
cfg = _load_settings()
threshold = cfg["ingestion"].get("rich_note_paragraph_threshold", 4)
if note.note_type not in ("article", "paper") and _count_paragraphs(note.body) >= threshold:
    note.note_type = "rich_note"
```

Then update the propose block routing from:

```python
if note.note_type == "article":
```

to:

```python
if note.note_type in ("article", "rich_note"):
```

The body of this branch already calls `generate_knowledge_card(note)` and
`render_knowledge_card_page(...)`. The `note_type` field in the front matter will
automatically become `"rich_note"` because `render_knowledge_card_page` writes
`note_type: article` hard-coded — this needs one small fix: pass `note.note_type`
instead of the hard-coded string.

**T004** — In `src/wiki_store.py:render_knowledge_card_page()`, replace the hard-coded
`"note_type": "article"` in the front matter dict with the caller-supplied value.
Add a `note_type: str = "article"` parameter and use it in the front matter:

```python
def render_knowledge_card_page(
    ...
    note_type: str = "article",   # ← add parameter
) -> str:
    ...
    front_matter: dict = {
        "slug": slug,
        "domain": domain,
        "note_type": note_type,   # ← was "article"
        ...
    }
```

Update the callers:
- `src/watcher.py` article branch: pass `note_type=note.note_type`
- `src/commit.py` article branch: pass `note_type=note.note_type`

**Checkpoint**: Process a note with 4+ paragraphs — wiki page front matter shows
`note_type: rich_note`. Process a note with 3 paragraphs — front matter shows nothing
(standard proposal path, no note_type in standard front matter).

---

### Phase 3 — Review TUI Label (Depends on T003)

**T005** — In `src/review_cli.py:_render_diff()`, add the `[RICH NOTE]` label:

```python
rich_label = "  [bold green]RICH NOTE[/bold green]" if note.note_type == "rich_note" else ""
console.print(
    f"[bold cyan]Proposal[/bold cyan]  "
    f"[bold]{proposal.proposed_page}[/bold]  "
    f"[dim]{note.domain}[/dim]  "
    f"[yellow]conf: {proposal.confidence:.2f}[/yellow]  "
    f"[magenta]{flag}[/magenta]"
    f"{rich_label}"
)
```

**Checkpoint**: Run `review_cli.py` with a rich-note proposal queued — header shows
`RICH NOTE` in green. Standard proposals show no label.

---

### Phase 4 — Ruff + Verification

**T006** — `uv tool run ruff check src/watcher.py src/review_cli.py src/wiki_store.py`
— all checks pass.

## Dependencies & Execution Order

```
T001 ──┐
       ├── T003 ── T004 ── T005 ── T006
T002 ──┘
```

T001 and T002 have no interdependency — parallelisable.  
T003 depends on both T001 (reads threshold from settings) and T002 (calls `_count_paragraphs`).  
T004 depends on T003 (needs to know what callers look like after routing change).  
T005 depends on T003 (needs `note.note_type == "rich_note"` to be persisted).  
T006 depends on all prior tasks.
