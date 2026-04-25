# Quickstart: Article Knowledge Cards

After this feature is implemented, web-clipped articles and PDF research papers flow through a dedicated pipeline that generates structured four-section knowledge cards.

---

## Scenario 1: Clip a web article with Obsidian Web Clipper

1. Browse to an article (blog post, research abstract, explainer).
2. Clip it with Obsidian Web Clipper — it saves a Markdown file to `data/raw/articles/`.
3. Run batch ingest:

```bash
uv run python src/batch_ingest.py
```

4. Open the review CLI to review the knowledge card proposal:

```bash
uv run python src/review_cli.py --type article
```

The proposal will contain four sections: **Summary**, **Key Arguments** (or **Key Findings** if empirical), **Core Concepts**, and **Questions Raised** (or **Open Questions**).

5. Press `a` to approve, `e` to edit any section, or `r` to reject.

---

## Scenario 2: Ingest a PDF research paper

1. Download a PDF paper and place it in `data/raw/papers/`.
2. Run batch ingest:

```bash
uv run python src/batch_ingest.py
```

3. If the PDF has embedded text, a NoteRecord is created and a structured knowledge card proposal is generated automatically.

4. Review it:

```bash
uv run python src/review_cli.py --type article
```

---

## Scenario 3: Detect an image-only PDF

If a PDF has no embedded text (scanned document):

```bash
uv run python src/batch_ingest.py
```

The pipeline logs:

```
[ERROR] my-scanned-paper.pdf — no extractable text — OCR required
```

The file is skipped without crashing. Check the errors table:

```bash
sqlite3 db/brain.sqlite "SELECT note_id, error_message FROM errors WHERE resolved=0;"
```

---

## Scenario 4: Review only article proposals

Mix of article and personal notes in the queue? Filter to articles only:

```bash
uv run python src/review_cli.py --type article
```

All non-article proposals (Kindle, GDrive, Keep) are excluded. Run without `--type` to see everything:

```bash
uv run python src/review_cli.py
```

---

## Scenario 5: Cross-paper wikilink suggestions (US4)

After 5 or more paper wiki pages are committed, new paper proposals may include a **Related Papers** section:

```markdown
## Related Papers

- [[attention-is-all-you-need]]
- [[bert-language-model]]
```

Review the suggested links during the human gate. Remove any that are not relevant before approving. Only links you keep will be committed to the wiki page.

---

## Checking article notes in the DB

```bash
sqlite3 db/brain.sqlite "
  SELECT title, source, note_type, status
  FROM notes
  WHERE note_type = 'article'
  ORDER BY created_at DESC
  LIMIT 20;
"
```

---

## Re-running batch ingest (dedup behavior)

Files already ingested are skipped based on content hash. Dropping a new version of the same PDF (with edits) into `data/raw/papers/` will produce a new proposal — same as all other sources.

---

## After the feature is set up

Run the DB schema migration once (idempotent):

```bash
sqlite3 db/brain.sqlite "ALTER TABLE notes ADD COLUMN note_type TEXT;"
sqlite3 db/brain.sqlite "CREATE INDEX IF NOT EXISTS idx_notes_note_type ON notes(note_type);"
```

Install the new dependency:

```bash
uv add pymupdf
```
