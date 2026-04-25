# Research: Kindle Multi-Domain Ingest

## Decision 1: Classification Granularity

**Decision**: Use Stage 1 (keyword scoring) to classify each individual highlight. Use Stage 2 (centroid embedding) only when classifying a complete domain group if its keyword score is ambiguous.

**Rationale**: The existing `classifier.py` already separates keyword scoring (Stage 1, pure Python, ~0ms per item) from centroid embedding (Stage 2, loads the 570MB bge-m3 model, ~50-200ms per call). Running Stage 2 on every one of 200 highlights would take minutes. Running Stage 1 per highlight costs ~1ms total for the entire book. Stage 2 runs once per group — the same cost as today's per-book classification.

**Alternatives considered**:
- Full `classify()` per highlight — rejected due to embedding model load overhead at scale
- Semantic clustering (embed all highlights, k-means by domain) — rejected as overengineering; keyword scoring is already precise enough for domain assignment and is already the existing Stage 1 mechanism
- Fixed sliding window (chunk N consecutive highlights) — rejected because highlights are not necessarily adjacent in topic; a book chapter may mix domains

---

## Decision 2: Minimum Group Size

**Decision**: `min_group_size = 3` highlights. Groups below this threshold are merged into the domain group with the highest keyword overlap from the same book. If no other group exists, the lone group is retained as-is (single-domain book case).

**Rationale**: Three highlights at ~50-200 words each produces 150-600 words — reliably above the 100-word `link_only_word_threshold`. The LLM needs enough signal to write a coherent 2-3 sentence summary; a single highlight is too thin. The value `3` matches the spec's stated minimum and aligns with the existing `link_only_word_threshold` logic in `ollama_agent.py`.

**Where to configure**: Add `kindle.min_group_size: 3` to `config/settings.yaml`. The parser reads this via the existing `_load_settings()` pattern.

**Alternatives considered**:
- Per-word threshold — rejected because word count varies too much between Kindle clipping styles; 3 highlights is a stable, source-independent unit
- No minimum (1 highlight = 1 record) — rejected because a 1-highlight record would produce a low-quality, near-meaningless wiki proposal

---

## Decision 3: Source Path Format

**Decision**: Change `source_path` from `file_path#book-slug` (old) to `file_path#book-slug#domain` (new). Record `id` hash includes the domain: `SHA-256(book_title + "\n" + domain + "\n" + body)`.

**Rationale**: `source_path` is the `UNIQUE NOT NULL` key in the `notes` table and the primary lookup used by `get_note_by_path()`. Adding the domain segment makes each (book, domain) group uniquely addressable without changing the DB schema.

**Migration path**: Old records have exactly one `#` in `source_path`. New records have two. The `_already_processed` check in `batch_ingest.py` is updated to look for new-format records specifically; old-format records are treated as needing re-ingestion. On re-ingestion, old records are deleted before new ones are inserted, preventing duplicates.

**Alternatives considered**:
- Using a separate `kindle_groups` table — rejected as overengineering; the existing `notes` table handles multi-record sources (it already did this for multiple books per clippings file)
- Side-by-side coexistence of old and new records — rejected; would produce duplicate proposals in the review queue

---

## Decision 4: Title Format

**Decision**: Title becomes `"{book_title} [{domain}]"` for books that produce multiple domain groups. For books that produce only one group, the title remains `"{book_title}"` (no domain suffix needed).

**Rationale**: The review CLI and wiki front matter use the title as a human-readable label. When multiple groups from the same book exist, the domain suffix prevents confusion. Keeping the original title for single-group books avoids unnecessary noise.

---

## Decision 5: Body Character Limit

**Decision**: ~~Keep the existing 4,000-character body limit~~ **Superseded by feature 003-expand-body-limit**: limit raised to 12,000 characters in `src/ollama_agent.py`.

**Rationale**: The original rationale (smaller per-domain groups) held at design time, but 52 Evernote and 26 GDrive notes in the corpus are still truncated at 4,000 chars. Raising to 12,000 covers all notes ≤ ~9,000 words without requiring chunking. Constitution Principle III is satisfied because 12,000 chars (~3,000 tokens) plus the domain index still fits comfortably within qwen3.5:9b's 32k context window.
