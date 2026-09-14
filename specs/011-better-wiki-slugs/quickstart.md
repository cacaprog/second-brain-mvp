# Quickstart: Better Wiki Slugs

## Verify generation-time fix (no wiki-wide migration needed)

1. Run the normal ingestion pipeline on a note with a long, punctuation-heavy, or instruction-like title.
2. Confirm the resulting wiki page's slug/filename:
   - Is at most 4 hyphen-separated words.
   - Contains no `--` runs.
   - Is not truncated mid-word.
   - Does not end with the note's own domain name appended.
3. Force an unusable LLM slug (e.g. by temporarily returning `"none"` from a mocked Ollama call in a test) and confirm no `none.md`-style placeholder page is ever written — the pipeline should raise/log instead.

## Preview the retroactive migration (read-only)

```bash
cd src
python slug_migrator.py detect
```

Review the printed report. Nothing is written to disk, the database, or ChromaDB at this step.

## Apply the retroactive migration

```bash
cd src
python slug_migrator.py apply --dry-run   # optional extra safety pass, still no writes
python slug_migrator.py apply
```

After it completes:

```bash
# Confirm no broken cross-links remain
grep -rlo '\[\[.*\]\]' ../wiki/domains/*/*.md | xargs -I{} echo {}   # spot-check a few

# Confirm DB and wiki agree
sqlite3 ../db/brain.sqlite "SELECT wiki_page FROM notes WHERE wiki_page IS NOT NULL LIMIT 20;"

# Confirm the wiki git history recorded renames (so re-running is a no-op)
cd ../wiki && git log --oneline | grep '^.* rename:' | head
```

Re-run `python slug_migrator.py detect` — it should report 0 newly flagged pages that were already renamed in a prior run, confirming idempotency.

## Run tests

```bash
cd src
pytest ../tests/unit/test_slug_utils.py ../tests/unit/test_slug_migrator.py -v
```
