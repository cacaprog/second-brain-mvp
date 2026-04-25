# Research: Second Brain v2 — Hybrid Zettelkasten Knowledge System

**Phase 0 output** | **Date**: 2026-04-21 | **Branch**: `001-second-brain-v2-system`

---

## 1. LLM Model — Qwen 3.5 9B (actual) vs. original spec

**Decision (original spec)**: Qwen 2.5 7B as primary; Qwen 2.5 14B as quality-upgrade fallback.

**Actual model in use**: `qwen3.5:9b` — pulled instead of `qwen2.5:7b`. Performance
is comparable on Portuguese multilingual tasks; the 9B model fits within the RTX 3060
12 GB VRAM budget alongside the BGE-M3 embedding model.

**Critical difference — thinking model**: Qwen 3.5 is a reasoning/thinking model.
All `ollama.chat()` calls **must** include `think=False` to suppress the hidden
reasoning phase. Without it, thinking tokens consume the entire `num_predict` budget
before any visible content is produced, resulting in empty responses. Additionally,
`format="json"` does not work with thinking models — JSON extraction uses regex
parsing of the raw content string instead.

**Rationale for original choice (still valid)**: Qwen models outperform Mistral 7B
and Llama 3 8B on multilingual quality (Portuguese is a first-class use case) and
structured output reliability. Llama 3.1 8B remains the fallback if Qwen is unavailable.

**In Ollama**: `qwen3.5:9b` at Q4_K_M: ~6 GB VRAM, ~35–50 tok/s on RTX 3060.
The embedding model (BAAI/bge-m3, ~1.5 GB) loads on the same GPU; total VRAM
budget stays under 10 GB.

**Key usage pattern** (with `think=False`):
```python
import ollama

response = ollama.chat(
    model="qwen3.5:9b",
    messages=[{"role": "user", "content": prompt}],
    think=False,
    options={"num_predict": 512}
)
proposal_json = response["message"]["content"]  # regex-extract JSON from this
```

**Alternatives considered**:
- Mistral 7B: weaker Portuguese, no explicit JSON tuning → rejected
- Llama 3.1 8B: decent multilingual, good fallback if Qwen unavailable
- Phi-4 14B: best English reasoning, weaker Portuguese, slower → not worth the
  VRAM cost for this use case

---

## 2. Ollama Python Client

**Decision**: Use the official `ollama` Python package (`pip install ollama`).

**Rationale**: Direct HTTP calls to the Ollama REST API work but add boilerplate.
The Python client wraps the API cleanly and supports streaming, JSON mode, and
model management. Synchronous `ollama.chat()` is sufficient — the pipeline is
sequential per note (no concurrent Ollama calls needed).

**Key usage pattern**:
```python
import ollama

response = ollama.chat(
    model="qwen3.5:9b",
    messages=[{"role": "user", "content": prompt}],
    think=False,
    options={"num_predict": 512}
)
proposal_json = response["message"]["content"]  # regex-extract JSON from this
```

**Timeout handling**: Ollama Python client does not expose a native timeout
parameter. Wrap with `concurrent.futures.ThreadPoolExecutor` and
`future.result(timeout=60)` to enforce the 60s Ollama timeout from config.

---

## 3. ChromaDB — Per-Domain Collections

**Decision**: One ChromaDB collection per domain, named `domain_{name}` (e.g.,
`domain_analytics`, `domain_philosophy`).

**Rationale**: Per-domain collections allow fast single-domain queries without
metadata filtering overhead. ChromaDB collection names must be alphanumeric with
underscores — `domain_` prefix avoids reserved names. Collections persist between
runs via the `PersistentClient`.

**Setup**:
```python
import chromadb

client = chromadb.PersistentClient(path="data/processed/chroma")

def get_collection(domain: str):
    return client.get_or_create_collection(
        name=f"domain_{domain}",
        metadata={"hnsw:space": "cosine"}
    )
```

**Document IDs**: Use the wiki page slug as the ChromaDB document ID. This makes
upserts idempotent — re-running the commit for the same slug overwrites cleanly.

**Metadata stored per document**: `slug`, `domain`, `language`, `updated` (ISO date).
This supports future filtered queries without loading document content.

**Cross-domain search**: Query all collections individually (top-10 per domain),
collect candidates, then run the cross-encoder. ChromaDB returns distances in
cosine space (lower = more similar when `hnsw:space=cosine`). Convert to similarity:
`similarity = 1 - distance`.

---

## 4. Sentence Transformers — GPU Acceleration

**Decision**: Load `SentenceTransformer` with `device="cuda"` explicitly.

**Rationale**: sentence-transformers defaults to CPU if not specified. On RTX 3060,
CUDA inference reduces embedding time from ~200ms to ~15ms per document, which
matters at 18,000 notes.

```python
from sentence_transformers import SentenceTransformer, CrossEncoder

bi_encoder = SentenceTransformer(
    "intfloat/multilingual-e5-large",
    device="cuda"
)
cross_encoder = CrossEncoder(
    "cross-encoder/ms-marco-MiniLM-L-6-v2",
    device="cuda"
)
```

**e5 prefix convention**: multilingual-e5-large requires the `"query: "` prefix
for query embeddings and `"passage: "` prefix for document embeddings. Both must
be applied consistently or retrieval quality degrades significantly.

**Batch encoding**: For ingestion batches, use `bi_encoder.encode(texts, batch_size=32)`
for throughput. Single notes in the pipeline use `.encode(text)` directly.

---

## 5. Watchdog — File Event Handling

**Decision**: Use `watchdog` with a 1-second debounce on `modified` events.

**Rationale**: Most editors (including Notion export tools) fire multiple `modified`
events per save. Without debouncing, the pipeline queues duplicate jobs. A simple
in-memory `dict[str, float]` tracking `{path: last_event_time}` is sufficient —
skip events within 1 second of the previous event for the same path.

**Pattern**:
```python
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

_last_modified: dict[str, float] = {}
DEBOUNCE_SECONDS = 1.0

class RawSourceHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory:
            return
        now = time.time()
        if now - _last_modified.get(event.src_path, 0) < DEBOUNCE_SECONDS:
            return
        _last_modified[event.src_path] = now
        ingest_queue.put(IngestJob(path=event.src_path, event="modify"))
```

**Observer threading**: `Observer` runs in a background thread. The `ingest_queue`
(a `queue.Queue`) is the handoff point to the main pipeline thread. This keeps the
watcher non-blocking.

---

## 6. SQLite — WAL Mode and Commit Coordination

**Decision**: Enable WAL mode; use `BEGIN IMMEDIATE` for commit status updates.

**Rationale**: WAL (Write-Ahead Logging) allows concurrent reads during writes,
which matters because the query layer reads `brain.sqlite` while ingestion may be
writing. `BEGIN IMMEDIATE` acquires a write lock immediately, preventing the SQLITE_BUSY
race condition when two pipeline threads try to update commit status simultaneously.

**Schema creation**: All tables created with `CREATE TABLE IF NOT EXISTS` on startup.
No migration framework needed at this scale — a single `schema.sql` file applied
once is sufficient.

**Startup replay**:
```python
def replay_unfinished_commits(conn):
    rows = conn.execute(
        "SELECT id, proposal_id FROM commits WHERE status='committing'"
    ).fetchall()
    for commit_id, proposal_id in rows:
        proposal = get_proposal(conn, proposal_id)
        note = get_note(conn, proposal.note_id)
        commit(proposal, note)  # idempotent
```

**Backup**: `sqlite3` has a built-in backup API — use `conn.backup(dest)` rather than
`cp` to avoid corruption during active writes.

---

## 7. FastMCP Server

**Decision**: Use `fastmcp` library; run as a sidecar process on `localhost:8765`.

**Rationale**: FastMCP provides the simplest path to an MCP-compatible server in
Python. The `@mcp.resource()` and `@mcp.tool()` decorators map directly to the
two capabilities needed (page retrieval + query). No auth needed — the server
binds only to localhost.

**Install**: `pip install fastmcp`

**Write rejection pattern**: FastMCP tools are read-only by design if they raise on
mutation attempts. Explicitly raise `ValueError("write operations are not permitted")`
for any tool that would modify state, so MCP clients receive a structured error.

**Process management**: Start with `python src/mcp_server.py` in a separate terminal
or systemd unit. The server imports `query.py` and `wiki_store.py` — no shared
mutable state with the ingestion pipeline (SQLite provides consistency).

---

## 8. Language Detection

**Decision**: Use `langdetect` with `DetectorFactory.seed = 0` for reproducibility.

**Rationale**: `langdetect` supports all four required languages (pt, en, fr, es).
Without setting a seed, results are non-deterministic (the underlying Java port uses
random selection among close-confidence results). Setting seed=0 makes detection
reproducible across runs, which matters for the audit trail.

```python
from langdetect import detect
from langdetect import DetectorFactory
DetectorFactory.seed = 0

def detect_language(text: str) -> str:
    try:
        lang = detect(text)
        return lang if lang in ("pt", "en", "fr", "es") else "unknown"
    except Exception:
        return "unknown"
```

**Fallback**: Notes with `language="unknown"` are processed using the embedding
model (which is language-agnostic) and flagged with a warning in the proposal.

---

## 9. Domain Classifier — Two-Stage Design

**Decision**: Keyword scoring (stage 1) → centroid cosine similarity (stage 2, only
when top-2 scores within 0.1 of each other).

**Rationale**: Keyword matching covers the unambiguous majority cheaply (no LLM or
embedding call). The centroid fallback handles boundary cases between semantically
adjacent domains. Centroid embeddings are pre-computed at setup time from the
`domains.yaml` seed terms and cached — no per-note embedding overhead for clear cases.

**Centroid pre-computation**:
```python
def compute_domain_centroids(domains: dict, encoder) -> dict[str, np.ndarray]:
    centroids = {}
    for domain, cfg in domains.items():
        seed_embeddings = encoder.encode(
            [f"passage: {s}" for s in cfg["seeds"]]
        )
        centroids[domain] = seed_embeddings.mean(axis=0)
    return centroids
```

**Multi-domain notes**: If the top-2 domain scores are within 0.05 after stage 2,
assign both as primary and secondary domain. Secondary domain is stored in the note
record and used for future cross-link suggestions but does not affect the proposal
generation domain.

---

## 10. Wiki Index Format

**Decision**: `index.md` per domain is a plain markdown table — one row per page.

**Rationale**: A structured table fits Ollama's context reliably and is human-readable
in Obsidian. One row = slug + one-line description + language tags. At 300 pages ×
~15 tokens per row = ~4,500 tokens — fits within Qwen 3.5 9B's context window.

**Format**:
```markdown
| Slug | Description | Languages |
|------|-------------|-----------|
| antifragility | Systems that gain from disorder and volatility | pt, en |
| via-negativa | Knowing what to avoid rather than what to pursue | pt, en |
```

**Index updates**: After each approved commit, `wiki_store.py` appends the new row
(or updates the existing one) atomically before the git commit step. The index file
is also tracked in git — each version is recoverable.

---

## 11. Git Integration for Wiki Versioning

**Decision**: Use `subprocess.run(["git", "-C", "wiki/", ...])` — no gitpython.

**Rationale**: The SDD already specifies subprocess git. gitpython adds 15MB of
dependencies for capabilities we don't need. Subprocess calls are simpler, debuggable,
and have no version-compatibility concerns. The only git operations needed are
`add`, `commit`, and `revert` — all straightforward via subprocess.

**Commit message format**:
```
ingest: {slug} (confidence={confidence:.2f}, model={model})
```

**Retroactive revert**:
```python
def revert_commit(git_hash: str) -> None:
    subprocess.run(
        ["git", "-C", "wiki/", "revert", "--no-edit", git_hash],
        check=True
    )
```

The git hash is stored in the `commits` table (`git_hash` column) so retroactive
rejects can look it up by proposal ID.

---

## 12. Dedup Threshold — Empirical Basis

**Decision**: Keep the 0.90 cosine similarity threshold from the SDD as the starting
point; tune during calibration sprint.

**Rationale**: 0.90 is conservative — it will catch near-verbatim duplicates and
expansions of the same concept, but is unlikely to false-positive on topically
adjacent but distinct notes. If the calibration sprint shows high false-positive
rates on merge proposals, raise to 0.93. If duplicates are slipping through,
lower to 0.87.

**Dedup scope**: Query all domain collections (not just the classified domain),
since the same concept can appear in multiple domains (e.g., "network effects" in
both analytics and behavioral-economics).
