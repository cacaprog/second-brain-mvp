# Phase 1 Data Model: Better Wiki Slugs

No new persistent tables or files are introduced. This feature adds one method to an existing store and reuses existing entities. It's documented here for how each entity is touched, not because new schema is being created.

## Wiki Page *(existing — `wiki/domains/{domain}/{slug}.md`)*

Unchanged shape. Front matter already carries `slug` and `domain`. Touched by:
- **Generation**: written once at ingest time with the (now word-boundary-safe) generated slug.
- **Migration**: renamed via `wiki_store.rename_wiki_page(domain, old_slug, new_slug)` — file move + front-matter `slug:` field update, both already implemented.

## Domain Index *(existing — `wiki/domains/{domain}/index.md`)*

Unchanged shape (`| Slug | Description | Languages |` table). Updated automatically by `rename_wiki_page()` as part of the same atomic commit as the page rename.

## Cross-Link *(existing — in-body `[[slug]]` references and `wiki/cross-links.md`)*

Unchanged shape. Updated automatically by `rename_wiki_page()`, which rewrites `cross-links.md` and scans every other page's front-matter links list for the old slug.

## Note Record *(existing — `notes` table in `db/brain.sqlite`)*

Unchanged schema. New behavior: `notes.wiki_page` is repointed from `old_slug` to `new_slug` for every note referencing a renamed page, via a new method:

```python
class DB:
    def rename_wiki_page(self, old_slug: str, new_slug: str) -> None:
        """Repoint every note's wiki_page from old_slug to new_slug (a page rename)."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE notes SET wiki_page=?, modified_at=? WHERE wiki_page=?",
                (new_slug, _now(), old_slug),
            )
```

Distinct from the existing `clear_wiki_page()` (nulls the reference — used by merge/delete) and `get_notes_by_wiki_page()` (used to find a note to attach a migration error to, since `errors.note_id` is `NOT NULL`).

## Vector Embedding Record *(existing — ChromaDB collection per domain, keyed by slug)*

Unchanged schema (`ids=[slug]`, `metadatas=[{slug, domain, language, updated}]`). Re-keyed on rename via the existing pair already used by `wiki_merger.py`:

```python
vs.delete_embedding(old_slug, domain)
vs.upsert(new_slug, page_content, domain, language)
```

## Migration Candidate *(new — in-memory only, not persisted)*

Produced by the heuristic scan in `slug_migrator.py`; consumed by preview and apply. Not written to disk except as the human-readable preview report.

| Field | Type | Description |
|---|---|---|
| `domain` | str | Owning domain directory |
| `old_slug` | str | Current slug/filename stem |
| `new_slug` | str \| None | Regenerated slug once available; `None` until the LLM call runs |
| `reasons` | list[str] | Which heuristic(s) flagged this page — e.g. `["length>=40", "artifact--"]` |
| `status` | `"pending" \| "renamed" \| "unchanged" \| "collision" \| "error"` | Outcome after apply |
| `error` | str \| None | Failure reason, when `status == "error"` |

## State / Flow Summary

```
scan wiki (skip domains/queries/)
  → heuristic filter (pure functions, no I/O side effects)
      → flagged pages: call Ollama (single-page-scoped prompt) → slug_utils.slugify()
          → collision check against other candidates + existing slugs in domain
              → preview report (no writes)
                  → [user reviews, re-runs with apply]
                      → for each candidate:
                          wiki_store.rename_wiki_page()   # file, front matter, index, cross-links, git commit
                          db.rename_wiki_page()            # notes.wiki_page
                          vs.delete_embedding() + vs.upsert()  # ChromaDB re-key
                      → summary: renamed / unchanged / collision / error counts
```

Re-running the whole flow: pages whose current slug already appears as a rename target in the wiki's own git history (`rename: <old> → <new>` commits) are skipped before the heuristic filter even runs, making the process idempotent without new persisted state.
