# Research: Rich Note Knowledge Cards (009)

## Finding 1: Current Routing Entry Point

**Decision**: All routing changes go in `src/watcher.py:_process_record()` at the `# Propose` block (line 153).

**Current logic**:
```python
if note.note_type == "article":
    # knowledge card path
else:
    # standard proposal path → generate_proposal()
```

**Rationale**: This is the single place where `note_type` is checked and the proposal
generation path is chosen. Changing it here covers every ingestion path (watcher daemon,
`--once`, batch ingest) without duplication.

---

## Finding 2: Paragraph Counting

**Decision**: Reuse the same double-newline split logic already in `wiki_cleaner.py`
(`_extract_heading_and_paragraphs`). Implement as a module-level helper
`_count_paragraphs(body: str) -> int` directly in `watcher.py`.

```python
def _count_paragraphs(body: str) -> int:
    return len([p for p in re.split(r"\n{2,}", body) if p.strip()])
```

**Rationale**: Keeps counting consistent with what `wiki_cleaner.py` already uses.
Importing from `wiki_cleaner` would create a cross-module dependency for a one-liner —
inlining is simpler and avoids circular imports.

---

## Finding 3: Rich Note Routing Condition

**Decision**: The routing check becomes:

```python
is_rich = (
    note.note_type not in ("article", "paper")
    and _count_paragraphs(note.body) >= cfg["ingestion"]["rich_note_paragraph_threshold"]
)
if note.note_type == "article" or is_rich:
    # knowledge card path
else:
    # standard proposal path
```

**Rationale**: `"paper"` typed notes currently fall through to `generate_proposal()` and
that behaviour must remain unchanged per FR-004. The guard on both `"article"` and
`"paper"` prevents accidentally promoting PDFs to the rich-note path.

**Alternative rejected**: Checking only `note.note_type != "article"` would silently
capture papers. Explicit exclusion list is safer.

---

## Finding 4: note_type Value for Rich Notes

**Decision**: Set `note.note_type = "rich_note"` before entering the knowledge card
path in `_process_record`. Persist this via `db.upsert_note(note)` (already called
before the propose block — note must be re-upserted or the status update must carry
it).

Actually, `db.upsert_note` is called at line 129 (before classify/propose). At the
propose step, only `db.set_note_domain` and `db.save_proposal` are called. The
`note_type` must be set before `db.upsert_note` or via a dedicated update call.

**Resolution**: Set `note.note_type = "rich_note"` before the `db.upsert_note(note)`
call at line 129 (i.e., add the paragraph count check earlier, after the empty body
guard). This ensures it's persisted in the same upsert.

**Rationale**: Storing `"rich_note"` in the existing `notes.note_type` column requires
zero schema changes. The review TUI and any future tool can query this column to
distinguish rich-note proposals without re-counting paragraphs.

---

## Finding 5: Knowledge Card Render Path for Rich Notes

**Decision**: Reuse `generate_knowledge_card(note)` and `render_knowledge_card_page()`
unchanged. Pass `note_type="rich_note"` implicitly via the fact that the caller is not
the article branch — the front matter will contain `note_type: rich_note` instead of
`note_type: article`.

**Impact on wiki_cleaner**: `_is_article_page()` checks DB `note_type == "article"`.
Rich note wiki pages have `note_type = "rich_note"` → they will NOT be skipped by the
cleaner. This is acceptable for v1 (rich notes may have repetitive paragraphs that
benefit from cleaning). Out of scope for this feature.

---

## Finding 6: Review TUI Label Location

**Decision**: Add `[RICH NOTE]` label in `review_cli.py:_render_diff()` at line 95–101,
alongside the existing `conf:`, domain, and `NEW PAGE`/`UPDATE` flags.

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

**Rationale**: Single-line change at the only display point. No new function needed.

---

## Finding 7: Settings Key

**Decision**: Add under the existing `ingestion:` block in `config/settings.yaml`:

```yaml
ingestion:
  rich_note_paragraph_threshold: 4
```

**Rationale**: Groups with related ingestion knobs (`fast_track_confidence`,
`duplicate_threshold`, etc.). Default 4 matches the spec assumption.
