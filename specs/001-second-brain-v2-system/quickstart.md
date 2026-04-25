# Quickstart: Second Brain v2

**Phase 1 output** | **Date**: 2026-04-21

This guide validates that the system is correctly set up and operational.
Run these steps in order after completing the initial implementation.

---

## Prerequisites

- Python 3.11+ (`python --version`)
- NVIDIA GPU with CUDA drivers installed (`nvidia-smi`)
- Ollama installed and running (`ollama --version`, `ollama serve`)
- Git installed (`git --version`)

---

## Step 1 — Install Dependencies

```bash
pip install -r requirements.txt
```

Expected packages: `ollama`, `chromadb`, `sentence-transformers`, `watchdog`,
`rich`, `fastmcp`, `langdetect`, `pyyaml`

---

## Step 2 — Pull the LLM Model

```bash
ollama pull qwen3.5:9b
```

Verify GPU offload:
```bash
ollama run qwen3.5:9b "Reply with: GPU OK"
```

The Ollama server log should show CUDA device allocation. If it shows CPU, check
that CUDA drivers are correctly installed.

---

## Step 3 — Initialize the Project

```bash
# Initialize brain.sqlite with schema
python src/db.py --init

# Initialize wiki git repo
git init wiki/
git -C wiki/ commit --allow-empty -m "init: wiki repository"

# Create required directories
mkdir -p data/raw/notion data/raw/keep data/raw/kindle
mkdir -p data/processed/chroma
mkdir -p db/backups
mkdir -p wiki/domains wiki/lint
mkdir -p config

# Copy default config
cp config/settings.yaml.example config/settings.yaml
cp config/domains.yaml.example config/domains.yaml
echo "qwen3.5:9b" > config/ollama_model.txt
```

---

## Step 4 — Pre-compute Domain Centroids

```bash
python src/classifier.py --precompute
```

This reads `config/domains.yaml` and computes centroid embeddings for each domain.
Expected output: one line per domain, e.g. `[OK] analytics centroid computed`.

GPU usage should be visible during this step (`nvidia-smi` in a second terminal).

---

## Step 5 — Smoke Test: Single Note Ingestion

```bash
# Create a minimal test note
cat > /tmp/test-note.md << 'EOF'
# Antifragility Test Note

Antifragilidade é a propriedade de sistemas que se beneficiam de choques.
Diferente da resiliência, que apenas sobrevive, o antifrágil se fortalece.

Tags: filosofia, taleb
EOF

# Copy to raw sources
cp /tmp/test-note.md data/raw/notion/test-note.md

# Process it directly (no daemon)
python src/watcher.py --once data/raw/notion/test-note.md
```

**Expected output**:
```
[PARSE]   OK: test-note.md → NoteRecord (lang=pt, words=32)
[DEDUP]   No duplicates found
[CLASSIFY] domain=philosophy (keyword match)
[PROPOSE]  Proposal created: antifragility (confidence=0.xx, new_page=True)
[GATE]    Proposal queued for review (new page → human gate required)
```

---

## Step 6 — Review Queue

```bash
python src/review_cli.py
```

**Expected**: The test note proposal appears as a colored diff. Press `a` to approve.

**Expected after approval**:
```
[COMMIT]  Writing wiki/domains/philosophy/antifragility.md
[VECTOR]  ChromaDB upserted: antifragility (domain_philosophy)
[INDEX]   Updated wiki/domains/philosophy/index.md
[GIT]     Committed: ingest: antifragility (confidence=0.xx)
[DB]      Note status → committed
```

---

## Step 7 — Query Test

```bash
python src/query.py "O que é antifragilidade?"
```

**Expected**: A synthesized answer citing `[[antifragility]]` with source attribution.

---

## Step 8 — Lint Test

```bash
python src/lint.py --tier structural
```

**Expected**: `wiki/lint/structural-{today}.json` created with 0 errors (the test
page is new, properly linked, and under size limits).

---

## Step 9 — MCP Server Test

```bash
# Terminal 1: start the MCP server
python src/mcp_server.py

# Terminal 2: test resource retrieval
curl -s http://localhost:8765/resources/wiki://antifragility | head -20

# Terminal 3: test query tool
curl -s -X POST http://localhost:8765/tools/query_knowledge_base \
  -H "Content-Type: application/json" \
  -d '{"question": "O que é antifragilidade?"}'
```

**Expected**: The wiki page content and a synthesized answer are returned.

---

## Step 10 — File Watcher Daemon Test

```bash
# Start the watcher in background
python src/watcher.py &
WATCHER_PID=$!

# Drop a second note
cp /tmp/test-note.md data/raw/notion/test-note-2.md

# Wait for detection (< 60s)
sleep 5

# Check that the proposal was queued
python src/db.py --status

# Stop watcher
kill $WATCHER_PID
```

**Expected**: The second note appears in the proposals table with `status=classified`.

---

## Validation Checklist

- [ ] Ollama runs on GPU (confirmed via `nvidia-smi` during `ollama run`)
- [ ] Single note processed end-to-end without errors
- [ ] Review CLI renders colored diff and captures approval
- [ ] Commit writes wiki file + ChromaDB + git commit atomically
- [ ] Query returns answer with `[[wikilink]]` citations
- [ ] Structural lint runs without errors
- [ ] MCP server responds to resource requests and tool calls
- [ ] File watcher detects new file and queues proposal

All items must pass before beginning the calibration sprint.

---

## Calibration Sprint Entry Criteria

Before processing the first 500 production notes:

1. All Quickstart validation items are checked.
2. `config/domains.yaml` has at least the initial 9 domains configured with seed terms.
3. Fast-track is **disabled** in `config/settings.yaml`:
   ```yaml
   ingestion:
     fast_track_confidence: 1.01   # Set above 1.0 to disable fast-track entirely
   ```
4. A baseline structural lint report has been generated and reviewed.
