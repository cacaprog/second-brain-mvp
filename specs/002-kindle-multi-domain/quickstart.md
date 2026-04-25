# Quickstart: Re-ingesting Kindle Files with Multi-Domain Support

After this feature is implemented, Kindle clippings files that were previously ingested under the old single-domain model need to be re-processed. Here is how to do it.

## What changes

Previously, one clippings file produced one NoteRecord per book. Now it produces one NoteRecord per (book × domain) group. A book like *Antifragile* might now produce two records: one for philosophy and one for personal-development.

## Re-ingesting a single file

```bash
uv run python src/watcher.py --once data/raw/kindle/my_clippings.txt
```

The pipeline detects old-format records (those with one `#` in `source_path`) and removes them before inserting new multi-domain records. No manual cleanup needed.

## Re-ingesting all Kindle files

```bash
uv run python src/batch_ingest.py --dir data/raw/kindle
```

By default, files whose new-format records already exist are skipped. Files that were only processed under the old format are treated as unprocessed and re-ingested automatically.

## Reviewing the new proposals

After re-ingestion, the review queue will contain new proposals — one per (book, domain) group. Run the review CLI as usual:

```bash
uv run python src/review_cli.py
```

## Checking group quality

To see how many domain groups were created per book, query the DB:

```bash
sqlite3 db/brain.sqlite "
  SELECT title, domain, word_count, status
  FROM notes
  WHERE source LIKE 'kindle%'
  ORDER BY title, domain;
"
```

## Adjusting the minimum group size

If you find that the default minimum of 3 highlights produces groups that are too thin or too coarse, change `kindle.min_group_size` in `config/settings.yaml` and re-ingest.
