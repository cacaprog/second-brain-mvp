# Second Brain v2 — Runbook

**GPU**: NVIDIA RTX 3060 12 GB  
**Model**: Qwen 3.5 9B (Ollama — thinking model, `think=False` required)  
**Python**: 3.11+ via `uv`

---

## Part 1 — One-Time Setup

### 1.1 Install Ollama

```bash
# Linux (official installer)
curl -fsSL https://ollama.com/install.sh | sh

# Verify
ollama --version
```

Ollama installs a systemd service that auto-starts. Verify it's running:

```bash
systemctl status ollama
# or start manually if needed:
ollama serve &
```

### 1.2 Pull the LLM model

```bash
ollama pull qwen3.5:9b
```

This downloads ~4.7 GB. Verify GPU offload after the pull:

```bash
ollama run qwen3.5:9b "Reply with exactly: GPU OK"
```

In a second terminal, `nvidia-smi` should show the model consuming VRAM during the
response. If it shows CPU-only, your CUDA drivers need attention (see 1.3).

### 1.3 Verify CUDA drivers (if GPU not detected)

```bash
nvidia-smi                    # must show your RTX 3060
nvcc --version                # CUDA toolkit version
python3 -c "import torch; print(torch.cuda.is_available())"  # must print True
```

If `torch.cuda.is_available()` returns False:
```bash
# Reinstall PyTorch with CUDA support
uv pip install torch --index-url https://download.pytorch.org/whl/cu121
```

### 1.4 Install Python dependencies

```bash
cd /home/cairo/code/second-brain-mvp
uv sync
```

Verify all modules load:

```bash
uv run python -c "
import ollama, chromadb, sentence_transformers, watchdog, rich, fastmcp, langdetect, yaml
print('All dependencies OK')
"
```

### 1.5 Initialize the database

```bash
uv run python src/db.py --init
```

Expected: `db/brain.sqlite` created with tables `notes`, `proposals`, `commits`, `errors`.

Verify:
```bash
sqlite3 db/brain.sqlite ".tables"
# notes  proposals  commits  errors
```

### 1.6 Initialize the wiki git repository

Skip if `wiki/.git` already exists.

```bash
git init wiki/
git -C wiki/ commit --allow-empty -m "init: wiki repository"
```

Create domain directories:
```bash
mkdir -p wiki/domains/analytics
mkdir -p wiki/domains/philosophy
mkdir -p wiki/domains/data-science
mkdir -p wiki/domains/behavioral-economics
mkdir -p wiki/domains/fiction
mkdir -p wiki/domains/neuroscience
mkdir -p wiki/domains/personal
mkdir -p wiki/domains/marketing
mkdir -p wiki/domains/career
mkdir -p wiki/lint
```

### 1.7 Pre-compute domain centroids

This must run before the classifier's stage-2 (cosine similarity) works.
Takes ~2 minutes on GPU; loads multilingual-e5-large (~1.1 GB VRAM).

```bash
uv run python src/classifier.py --precompute
```

Expected output (one line per domain):
```
[OK] analytics centroid computed
[OK] philosophy centroid computed
...
[OK] career centroid computed
[CENTROIDS] Saved to config/centroids.pkl
```

### 1.8 Smoke test — single note end-to-end

```bash
# Create a test note in Portuguese
cat > /tmp/test-note.md << 'EOF'
# Antifragilidade

Antifragilidade é a propriedade de sistemas que se beneficiam de choques e perturbações.
Diferente da resiliência, que apenas sobrevive, o antifrágil se fortalece com a volatilidade.
Nassim Taleb desenvolveu o conceito em contraposição ao frágil e ao robusto.

Tags: filosofia, taleb
EOF

cp /tmp/test-note.md data/raw/notion/test-antifragilidade.md

# Process it (single-file mode, no daemon)
uv run python src/watcher.py --once data/raw/notion/test-antifragilidade.md
```

Expected:
```
[PARSE]    OK: test-antifragilidade.md → NoteRecord (lang=pt, words=...)
[DEDUP]    No duplicates found
[CLASSIFY] domain=philosophy (keyword match: taleb, antifragilidade)
[PROPOSE]  Proposal created: antifragility (confidence=0.xx, new_page=True)
[GATE]     Proposal queued for review (new page → human gate required)
```

### 1.9 Review and approve the test proposal

```bash
uv run python src/review_cli.py
```

The TUI shows the proposal diff. Press `a` to approve.

Expected commit log:
```
[COMMIT]  Writing wiki/domains/philosophy/antifragility.md
[VECTOR]  ChromaDB upserted: antifragility (domain_philosophy)
[INDEX]   Updated wiki/domains/philosophy/index.md
[GIT]     Committed: ingest: antifragility (confidence=0.xx)
[DB]      Note status → committed
```

### 1.10 Query test

```bash
uv run python src/query.py "O que é antifragilidade?"
```

Expected: synthesized answer citing `[[antifragility]]` with a Sources line.

### 1.11 Structural lint test

```bash
uv run python src/lint.py --tier structural
```

Expected: `wiki/lint/structural-{today}.json` written, 0 errors.

---

## Part 2 — First 500 Notes (Calibration Sprint)

The goal is to measure classifier and proposal quality before enabling automation.
Fast-track is already disabled (`fast_track_confidence: 1.01` in `config/settings.yaml`).
**Every proposal goes through human review.**

### 2.1 Prepare your raw note sources

Copy your exports into the source directories:

```bash
# Notion exports (.md files)
cp -r /path/to/notion-export/* data/raw/notion/

# Google Keep export (JSON files from Google Takeout)
cp /path/to/Takeout/Keep/*.json data/raw/keep/

# Kindle clippings
cp "/path/to/My Clippings.txt" data/raw/kindle/

# Google Drive Obsidian vault backup (recursive .md tree)
cp -r /path/to/gdrive-obsidian-backup/* data/raw/gdrive/

# Evernote HTML exports (recursive — preserve subdirectory structure)
cp -r /path/to/evernote-export/* data/raw/evernote/

# Obsidian direct vault export (when available)
cp -r /path/to/obsidian-vault/* data/raw/obsidian/
```

Check counts before starting:

```bash
find data/raw/notion/  -name "*.md"   | wc -l
find data/raw/keep/    -name "*.json" | wc -l
find data/raw/kindle/  -name "*.txt"  | wc -l
find data/raw/gdrive/  -name "*.md"   | wc -l
find data/raw/evernote/ -name "*.html" | wc -l
find data/raw/obsidian/ -name "*.md"  | wc -l
```

**Note on Kindle**: one `My Clippings.txt` produces one NoteRecord per book
(all highlights grouped). Running `--once` on it processes every book in that file.

**Note on GDrive/Evernote**: files are nested in subdirectories. The batch script
handles recursive discovery automatically — no need to flatten the tree.

### 2.2 Process notes in batches of ~50

Do not start the file watcher daemon yet. Use `batch_ingest.py` for controlled
ingestion — it handles all sources, skips already-processed files, and pauses
between batches for review.

**Recommended: use batch_ingest.py (handles all sources uniformly)**
```bash
# Notion — flat directory, 50 at a time
uv run python src/batch_ingest.py --dir data/raw/notion --limit 50 --batch-size 50

# Google Keep — flat directory
uv run python src/batch_ingest.py --dir data/raw/keep --limit 50 --batch-size 50

# Google Drive — recursive; Excalidraw/config files auto-skipped
uv run python src/batch_ingest.py --dir data/raw/gdrive --limit 50 --batch-size 50

# Evernote — recursive; attachment subdirs auto-skipped
uv run python src/batch_ingest.py --dir data/raw/evernote --limit 50 --batch-size 50

# Kindle — one file produces all books at once; omit --limit
uv run python src/batch_ingest.py --dir data/raw/kindle

# Obsidian — same as gdrive
uv run python src/batch_ingest.py --dir data/raw/obsidian --limit 50 --batch-size 50
```

**Alternative: watcher --once for a single file**
```bash
uv run python src/watcher.py --once data/raw/notion/myfile.md
uv run python src/watcher.py --once "data/raw/kindle/My Clippings.txt"
```

**Check what's queued after each batch:**
```bash
sqlite3 db/brain.sqlite \
  "SELECT source, domain, COUNT(*) FROM proposals p
   JOIN notes n ON n.id = p.note_id
   WHERE p.decision IS NULL GROUP BY source, domain ORDER BY source, domain;"
```

### 2.3 Review the batch

Run the review CLI per domain to keep sessions focused:

```bash
# Review philosophy proposals first
uv run python src/review_cli.py --domain philosophy

# Then analytics
uv run python src/review_cli.py --domain analytics

# Then the rest
uv run python src/review_cli.py --domain data-science
uv run python src/review_cli.py --domain behavioral-economics
uv run python src/review_cli.py --domain fiction
uv run python src/review_cli.py --domain neuroscience
uv run python src/review_cli.py --domain personal
uv run python src/review_cli.py --domain marketing
uv run python src/review_cli.py --domain career
```

**Review CLI keybindings:**

| Key | Action |
|-----|--------|
| `a` | Approve proposal as-is |
| `e` | Edit in `$EDITOR`, then commit edited version |
| `r` | Reject (prompts for reason) |
| `s` | Skip (keep pending, review later) |
| `d` | Reassign to a different domain — or add a new one on the spot |
| `b` | Batch-approve all remaining fast-track eligible in queue |
| `q` | Quit |
| `?` | Show help |

### 2.4 Track rejection rate per domain

After each batch of 50, measure:

```bash
sqlite3 db/brain.sqlite "
SELECT
  n.source,
  p.domain,
  COUNT(*) AS total,
  SUM(CASE WHEN p.decision='approved' THEN 1 ELSE 0 END) AS approved,
  SUM(CASE WHEN p.decision='rejected' THEN 1 ELSE 0 END) AS rejected,
  ROUND(
    100.0 * SUM(CASE WHEN p.decision='rejected' THEN 1 ELSE 0 END) / COUNT(*),
    1
  ) AS rejection_rate_pct
FROM proposals p
JOIN notes n ON n.id = p.note_id
WHERE p.decision IS NOT NULL
GROUP BY n.source, p.domain
ORDER BY rejection_rate_pct DESC;
"
```

**Target**: rejection rate < 15% per domain before enabling fast-track for that domain.

### 2.4b Re-queue rejected proposals

**Option A — Fresh proposal** (use after fixing the prompt or slugify — Ollama re-runs):
```bash
# Inspect what was rejected and why
sqlite3 db/brain.sqlite "
SELECT p.proposed_page, p.rejection_reason, n.source_path
FROM proposals p JOIN notes n ON n.id = p.note_id
WHERE p.decision = 'rejected' ORDER BY p.created_at;
"

# Reset notes + delete old proposals so the pipeline regenerates them
sqlite3 db/brain.sqlite "
UPDATE notes SET status = 'ingested'
  WHERE id IN (SELECT note_id FROM proposals WHERE decision = 'rejected');
DELETE FROM proposals WHERE decision = 'rejected';
"

# Re-run review — fresh proposals will appear in queue
uv run python src/review_cli.py
```

**Option B — Re-review original proposal unchanged** (no new Ollama call):
```bash
sqlite3 db/brain.sqlite "
UPDATE proposals SET decision = NULL WHERE decision = 'rejected';
UPDATE notes SET status = 'classified'
  WHERE id IN (SELECT note_id FROM proposals WHERE decision IS NULL);
"
uv run python src/review_cli.py
```

### 2.5 Tune domain seeds if classifier misroutes notes

If you see notes landing in the wrong domain consistently, add seed terms:

```yaml
# config/domains.yaml — example: add seeds to analytics
analytics:
  seeds:
    - "MMM"
    - "seu novo termo aqui"
```

Then recompute centroids:
```bash
uv run python src/classifier.py --precompute
```

You do not need to reprocess already-classified notes — only new ones will use
the updated centroids.

### 2.6 Continue until 500 notes reviewed

Repeat steps 2.2–2.4 in batches of 50 until you've reviewed 500 proposals.

Check total progress:
```bash
sqlite3 db/brain.sqlite "
SELECT
  COUNT(*) AS total_proposals,
  SUM(CASE WHEN decision='approved' THEN 1 ELSE 0 END) AS approved,
  SUM(CASE WHEN decision='rejected' THEN 1 ELSE 0 END) AS rejected,
  SUM(CASE WHEN decision IS NULL THEN 1 ELSE 0 END) AS pending
FROM proposals;
"
```

Check wiki pages created:
```bash
find wiki/domains/ -name "*.md" ! -name "index.md" | wc -l
```

### 2.7 Run structural lint after every 10 commits

The system is configured to remind you after every 10 commits. Run manually:

```bash
uv run python src/lint.py --tier structural
```

Review the JSON report:
```bash
cat wiki/lint/structural-$(date +%Y-%m-%d).json | python3 -m json.tool | grep '"type"'
```

Address any `error`-severity issues before continuing.

---

## Part 3 — Enable Fast-Track (After Calibration)

Only after **all domains have rejection rate < 15%** and **all 500 notes reviewed**.

### 3.1 Set fast-track threshold per domain

Edit `config/settings.yaml`:

```yaml
ingestion:
  fast_track_confidence: 0.85   # restore to production threshold
```

### 3.2 Start the file watcher daemon

```bash
# Replay any commits that were interrupted (safe to run even if none pending)
uv run python src/watcher.py --replay

# Start daemon (watches data/raw/ recursively)
uv run python src/watcher.py
```

Keep it running in a terminal, or install as a systemd user service:

```bash
# Create service file
cat > ~/.config/systemd/user/second-brain-watcher.service << 'EOF'
[Unit]
Description=Second Brain v2 file watcher
After=network.target

[Service]
WorkingDirectory=/home/cairo/code/second-brain-mvp
ExecStart=/home/cairo/.local/bin/uv run python src/watcher.py --replay
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now second-brain-watcher
systemctl --user status second-brain-watcher
```

### 3.3 Review fast-tracked notes periodically

Fast-tracked approvals are logged to `batch_log.jsonl`. Review them:

```bash
uv run python src/review_cli.py --batch-log
```

Press `r` on any entry to trigger a git revert (retroactive rejection).

---

## Part 4 — Ongoing Operations

### Check ingestion completeness

Use this to know whether every file has been fully processed and every note is in
the wiki.

**Quick dashboard (proposals + note statuses by domain):**

```bash
uv run python src/batch_ingest.py --status
```

**You are done when all three conditions are true:**

| Status | Target | Meaning if non-zero |
|--------|--------|---------------------|
| `pending` / `ingested` | **0** | Files still waiting to be classified/proposed |
| `commit_failed` | **0** | Pipeline errors — wiki write failed |
| `classified` | 0 | Proposals waiting for your review (expected to be non-zero during active use) |

`committed` and `rejected` are terminal states — nothing to do.

**Raw SQL check:**

```bash
sqlite3 -column -header db/brain.sqlite "
SELECT
    n.source,
    COUNT(*)                                                          AS total,
    SUM(CASE WHEN n.status='committed'     THEN 1 ELSE 0 END)        AS committed,
    SUM(CASE WHEN n.status='classified'    THEN 1 ELSE 0 END)        AS awaiting_review,
    SUM(CASE WHEN n.status='commit_failed' THEN 1 ELSE 0 END)        AS failed,
    SUM(CASE WHEN n.status IN ('pending','ingested') THEN 1 ELSE 0 END) AS in_progress,
    SUM(CASE WHEN n.status='rejected'      THEN 1 ELSE 0 END)        AS rejected
FROM notes n
GROUP BY n.source
ORDER BY total DESC;
"
```

**Note on file count vs note count:** raw file counts will never match note counts.
Kindle produces one note per book from a single `.txt` file; empty and config files
are skipped silently. Do not use `find data/raw | wc -l` as a completeness check.

**Resolving `commit_failed` notes:**

```bash
uv run python src/review_cli.py --errors
# r = re-queue for fresh attempt   d = dismiss permanently
```

Once `commit_failed = 0`, `pending = 0`, `ingested = 0`, and the `classified` review
queue is cleared — every sentence from every source file is in the wiki.

### Daily backup (set up cron)

```bash
crontab -e
# Add this line:
0 2 * * * /home/cairo/code/second-brain-mvp/db/backups/backup.sh >> /home/cairo/code/second-brain-mvp/db/backups/backup.log 2>&1
```

### Daily structural lint (set up cron)

```bash
# Add to crontab:
30 2 * * * cd /home/cairo/code/second-brain-mvp && uv run python src/lint.py --tier structural >> wiki/lint/lint.log 2>&1
```

### Monthly semantic lint (one domain at a time)

```bash
uv run python src/lint.py --tier semantic --domain philosophy
uv run python src/lint.py --tier semantic --domain analytics
# ... repeat for each domain
```

### Query the wiki

```bash
# Single domain
uv run python src/query.py "O que é antifragilidade?" --domain philosophy

# Cross-domain (slower, uses cross-encoder re-ranking)
uv run python src/query.py "Como vieses cognitivos afetam decisões financeiras?"
```

### Rich note knowledge cards

Notes from any source (Kindle, Notion, Keep, etc.) with **4 or more paragraphs** are
automatically treated as rich notes and routed through the knowledge-card generation
path — the same structured four-section format used for articles and papers. In the
review TUI they show a green `RICH NOTE` label so you know the source is highlights,
not a published article.

The threshold is configurable without touching code:

```yaml
# config/settings.yaml
ingestion:
  rich_note_paragraph_threshold: 4   # increase to require more content before upgrading
```

**Check how many notes qualified as rich notes:**

```bash
sqlite3 -column -header db/brain.sqlite "
SELECT
    source,
    COUNT(*) AS rich_notes,
    SUM(CASE WHEN status='committed' THEN 1 ELSE 0 END) AS committed,
    SUM(CASE WHEN status='classified' THEN 1 ELSE 0 END) AS awaiting_review
FROM notes
WHERE note_type='rich_note'
GROUP BY source
ORDER BY rich_notes DESC;
"
```

**Tune the threshold if too many thin notes are getting knowledge-card treatment:**

```bash
# Edit the threshold, then re-ingest affected notes (optional — only new ingestion
# picks up the new threshold; existing classified/committed notes are unaffected)
# To force re-routing of pending rich notes, reset them:
sqlite3 db/brain.sqlite "
UPDATE notes SET status='pending', note_type=NULL
WHERE note_type='rich_note' AND status='classified';
DELETE FROM proposals
WHERE note_id IN (SELECT id FROM notes WHERE note_type IS NULL AND status='pending')
  AND decision IS NULL;
"
# Then re-run batch ingest or watcher --once
```

### Clean and merge wiki pages

Run these tools periodically to consolidate duplicate content across the wiki.

**Always commit their changes before resuming ingestion.** Both tools modify wiki
files without committing — if you start ingesting while their changes are pending,
the next fast-track commit will sweep them up via `git add domains` and bundle
everything into a single commit with the wrong message.

```bash
# 1. Consolidate repetitive paragraphs within each page (dry-run first)
uv run python src/wiki_cleaner.py --dry-run
uv run python src/wiki_cleaner.py

# 2. Detect and merge pages with duplicate slugs across domains
uv run python src/wiki_merger.py detect
uv run python src/wiki_merger.py batch --dry-run
uv run python src/wiki_merger.py batch

# 3. Commit their changes explicitly before ingesting anything else
git -C wiki/ add -A
git -C wiki/ commit -m "maintenance: clean and merge wiki pages"
```

### Rename a wiki page slug

Use this when a slug was generated with stripped accents (e.g. `caracterstica`,
`automao`) or is simply too long. The command updates the file, domain index,
cross-links, all back-references, and creates a git commit atomically.

```bash
uv run python src/wiki_store.py rename <domain> <old-slug> <new-slug>
```

Examples:
```bash
uv run python src/wiki_store.py rename mental-model caracterstica caracteristica
uv run python src/wiki_store.py rename mental-model automao automacao
uv run python src/wiki_store.py rename philosophy um-slug-muito-longo-aqui slug-curto
```

After renaming, sync SQLite and ChromaDB:
```bash
# Update the DB reference (replace values as needed)
sqlite3 db/brain.sqlite \
  "UPDATE notes SET wiki_page='<new-slug>' WHERE wiki_page='<old-slug>';"

# Re-index in ChromaDB
uv run python src/vector_store.py --reindex-slug <domain> <new-slug>
```

**Slug rules** (applied automatically to all new proposals):
- 1–4 words, lowercase-hyphenated
- Max 40 characters
- Accented characters transliterated: `ã→a`, `ç→c`, `ê→e`, `ó→o`, etc.

### MCP server (for Claude Code integration)

```bash
uv run python src/mcp_server.py
# Runs on localhost:8765 by default
```

Add to your Claude Code MCP config (`~/.claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "second-brain": {
      "command": "uv",
      "args": ["run", "python", "src/mcp_server.py"],
      "cwd": "/home/cairo/code/second-brain-mvp"
    }
  }
}
```

---

## Quick Reference

```bash
# Process a single file (any source)
uv run python src/watcher.py --once data/raw/notion/myfile.md
uv run python src/watcher.py --once data/raw/gdrive/Code/myfile.md
uv run python src/watcher.py --once data/raw/evernote/Data\ Science/note.html
uv run python src/watcher.py --once "data/raw/kindle/My Clippings.txt"

# Batch ingest by source (50 at a time, pauses for review)
uv run python src/batch_ingest.py --dir data/raw/notion  --limit 50 --batch-size 50
uv run python src/batch_ingest.py --dir data/raw/gdrive  --limit 50 --batch-size 50
uv run python src/batch_ingest.py --dir data/raw/evernote --limit 50 --batch-size 50
uv run python src/batch_ingest.py --dir data/raw/keep    --limit 50 --batch-size 50
uv run python src/batch_ingest.py --dir data/raw/kindle  # all books in one pass

# Show ingest stats by source
uv run python src/batch_ingest.py --status

# Review pending proposals (all domains)
uv run python src/review_cli.py

# Review pending proposals (one domain)
uv run python src/review_cli.py --domain philosophy

# Review pipeline failures (COMMIT_FAILED notes — re-queue or dismiss)
uv run python src/review_cli.py --errors

# Query
uv run python src/query.py "sua pergunta aqui"

# Structural lint
uv run python src/lint.py --tier structural

# Semantic lint (one domain)
uv run python src/lint.py --tier semantic --domain philosophy

# Recompute centroids (after editing domains.yaml)
uv run python src/classifier.py --precompute

# Check proposal stats
sqlite3 db/brain.sqlite \
  "SELECT domain, decision, COUNT(*) FROM proposals GROUP BY domain, decision ORDER BY domain;"

# Check wiki page count per domain
find wiki/domains/ -name "*.md" ! -name "index.md" | \
  sed 's|wiki/domains/||;s|/.*||' | sort | uniq -c | sort -rn

# Re-queue rejected proposals for fresh Ollama proposals
sqlite3 db/brain.sqlite "UPDATE notes SET status='ingested' WHERE id IN (SELECT note_id FROM proposals WHERE decision='rejected'); DELETE FROM proposals WHERE decision='rejected';"

# Rename a wiki slug (fixes broken accents or long slugs)
uv run python src/wiki_store.py rename <domain> <old-slug> <new-slug>
# Then sync SQLite:
sqlite3 db/brain.sqlite "UPDATE notes SET wiki_page='<new>' WHERE wiki_page='<old>';"
```
