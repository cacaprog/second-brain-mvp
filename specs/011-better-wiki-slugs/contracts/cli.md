# CLI Contract: `src/slug_migrator.py`

## Command Signature

```
python src/slug_migrator.py detect [--path FILEPATH]
python src/slug_migrator.py apply [--path FILEPATH] [--dry-run]
```

Modeled on the existing `wiki_merger.py` (`detect`/`batch` subcommands) and `wiki_cleaner.py` (`--path` for single-page runs, `--dry-run`) conventions already used in this project.

## Flags

| Flag | Type | Required | Description |
|---|---|---|---|
| `detect` \| `apply` | subcommand | yes | `detect` only previews; `apply` performs the migration |
| `--path FILEPATH` | string | no | Limit the run to a single wiki page instead of the full wiki |
| `--dry-run` | flag | no (only on `apply`) | Perform the full `apply` flow (heuristic scan, regeneration, collision check) but skip all writes — an extra safety net beyond `detect` |

## Behaviour

### `detect` (preview, always read-only)

Scans the wiki (or the single page at `--path`), skipping `domains/queries/` and any page already covered by a prior `rename:` commit in the wiki's git history. For every page matching a bad-slug heuristic, calls Ollama to regenerate a candidate slug and resolves collisions, then prints a report. No file, database, or vector store write occurs.

```
$ python src/slug_migrator.py detect

Scanning 627 pages (skipping domains/queries/, 0 already migrated)...
14 pages flagged for review:

  [health] sprint-how-to-solve-big-problems-and-tes
    → sprint-methodology                          (length>=40)
  [theology] ciencia-e-fe---a-particula-de-deus
    → ciencia-fe-particula-deus                    (artifact--)
  [marketing] tribes-we-need-you-to-lead-us-marketing
    → tribes-leadership                             (length>=40, words>4)
  ...

12 will be renamed, 2 flagged as needs-manual-review (collision unresolved).
Run `python src/slug_migrator.py apply` to perform these renames.
```

### `apply` (writes, unless `--dry-run`)

Same scan and regeneration as `detect`, then for each resolved candidate: `wiki_store.rename_wiki_page()`, `db.rename_wiki_page()`, and the ChromaDB `delete_embedding()`/`upsert()` pair, each wrapped so a single page's failure is logged and does not abort the run.

```
$ python src/slug_migrator.py apply

Scanning 627 pages (skipping domains/queries/, 0 already migrated)...
14 pages flagged for review:
  ...
[1/12] sprint-how-to-solve-big-problems-and-tes → sprint-methodology  OK
[2/12] ciencia-e-fe---a-particula-de-deus → ciencia-fe-particula-deus  OK
...

Summary: 11 renamed, 1 error, 2 needs-manual-review, 613 unchanged.

Errors:
  [career] some-broken-page: ChromaDB upsert failed: <reason>

Needs manual review (unresolved collision):
  [marketing] tribes-we-need-you-to-lead-us-analytics
  [marketing] tribes-we-need-you-to-lead-us-marketing
```

### `apply --dry-run`

Identical output to `apply`, prefixed with `[DRY-RUN]` on each line, with zero writes performed — matches the existing `--dry-run` convention in `wiki_merger.py` and `wiki_cleaner.py`.

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | Completed (including when some pages need manual review or errored — those are reported, not fatal) |
| 1 | Fatal error before any page could be processed (e.g. wiki root not found) |

## Out of Scope

- `domains/queries/` pages are never scanned, flagged, or renamed by this tool (spec FR-013).
- True cross-domain duplicate concepts are not merged by this tool — that remains `wiki_merger.py`'s responsibility.
