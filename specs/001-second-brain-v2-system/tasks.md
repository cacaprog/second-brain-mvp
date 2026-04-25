---
description: "Task list for Second Brain v2 — Hybrid Zettelkasten Knowledge System"
---

# Tasks: Second Brain v2 — Hybrid Zettelkasten Knowledge System

**Input**: Design documents from `/specs/001-second-brain-v2-system/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/

**Organization**: Tasks are grouped by user story for independent implementation.
No test tasks generated (not requested in spec).

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no shared state dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Exact file paths are included in all task descriptions

## Path Conventions

- Source: `src/` at repository root
- Wiki: `wiki/` (separate git repo)
- Raw data: `data/raw/{notion,keep,kindle}/`
- Vector store: `data/processed/chroma/`
- Database: `db/brain.sqlite`
- Config: `config/`

---

## Phase 1: Setup

**Purpose**: Directory structure, dependency manifest, configuration templates, and
wiki git repository. No code logic — just scaffolding.

- [x] T001 Create directory structure: `src/`, `wiki/domains/`, `wiki/lint/`,
  `data/raw/notion/`, `data/raw/keep/`, `data/raw/kindle/`,
  `data/processed/chroma/`, `db/backups/`, `config/`
- [x] T002 [P] Initialize `wiki/` as a standalone git repository with an empty
  initial commit (`git init wiki/ && git -C wiki/ commit --allow-empty -m "init: wiki repository"`)
- [x] T003 [P] Create `requirements.txt` with all dependencies: `ollama`,
  `chromadb`, `sentence-transformers`, `watchdog`, `rich`, `fastmcp`,
  `langdetect`, `pyyaml`
- [x] T004 [P] Create `config/settings.yaml` with all runtime configuration
  from plan.md: paths, ollama model/timeout/min_confidence, ingestion thresholds,
  embeddings models, reranker, domains, lint schedule, backup retention, languages, mcp
- [x] T005 [P] Create `config/domains.yaml` with initial 9 domains
  (analytics, philosophy, data-science, behavioral-economics, fiction,
  neuroscience, personal, marketing, career) and their seed terms

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data structures, database layer, vector store, and wiki file I/O
that ALL user stories depend on. No user story work can begin until this phase is done.

**⚠️ CRITICAL**: Phases 3–7 cannot start until Phase 2 is complete.

- [x] T006 Create `src/models.py` with all dataclasses from data-model.md:
  `NoteRecord` (all fields including `secondary_domain`, `word_count`), `Proposal`
  (all fields including `edited_content`), `WikiPage`, `IngestJob`, `CommitRecord`,
  `ErrorRecord`, `DomainConfig`; include the NoteRecord status enum as a set of
  constants
- [x] T007 [P] Create `src/db.py` — SQLite wrapper with WAL mode enabled on
  connection open; `init_schema()` applying the full schema from data-model.md
  (notes, proposals, commits, errors tables + all indexes); CRUD methods for all
  tables; NoteRecord state machine transitions (`set_note_status()`,
  `begin_commit()`, `finish_commit()`, `fail_commit()`, `log_error()`);
  `get_commits_by_status()` for startup replay; `mark_deleted()` for deletion events
- [x] T008 [P] Create `src/vector_store.py` — `chromadb.PersistentClient` at
  `data/processed/chroma/`; `get_collection(domain)` returning named collection
  `domain_{name}` with `hnsw:space=cosine`; `SentenceTransformer("BAAI/bge-m3", device="cuda")`
  (no query/passage prefix needed); `CrossEncoder("BAAI/bge-reranker-v2-m3", device="cuda")`;
  `upsert(slug, content, metadata)` idempotent by slug ID; `search(query, domain, n_results)`
  for single-domain bi-encoder retrieval; `cross_domain_search(query, n_results)` for
  bi-encoder + cross-encoder re-ranking across all domains; `query_similar(embedding, threshold)`
  for dedup check across all collections returning the closest slug if similarity ≥ threshold
- [x] T009 [P] Create `src/wiki_store.py` — `read_domain_index(domain)` returning
  markdown table string from `wiki/domains/{domain}/index.md`; `read_wiki_page(domain, slug)`
  returning full page content; `read_wiki_page_by_slug(slug)` scanning all domains;
  `write_wiki_page(domain, slug, content)` overwriting idempotently; `update_domain_index(domain, slug, description)`
  upserting a row in the index table; `register_cross_link(source, target)` upserting
  in `wiki/cross-links.md`; `wiki_page_exists(domain, slug)` checking file existence;
  `list_all_pages()` returning `list[dict]` of all pages across domains with slug/domain/metadata;
  `git_commit_wiki(page_path, slug, confidence, model)` running subprocess git add + commit

**Checkpoint**: Foundation ready when `src/models.py`, `src/db.py`, `src/vector_store.py`,
and `src/wiki_store.py` all import cleanly and `python src/db.py --init` creates
`db/brain.sqlite` with all tables.

---

## Phase 3: User Story 1 — Automatic Note Detection and Proposal (Priority: P1) 🎯 MVP

**Goal**: A raw note file dropped into `data/raw/` triggers the full pipeline:
parse → dedup check → domain classify → Ollama proposal → queued for review.

**Independent Test**: `python src/watcher.py --once data/raw/notion/test.md` produces
a Proposal row in `brain.sqlite` with a valid domain, slug, summary, proposed_links,
and confidence score — without any manual pipeline trigger.

### Implementation for User Story 1

- [x] T010 [P] [US1] Create `src/notion_parser.py` — parse Notion markdown export
  files into `NoteRecord`; extract H1 as title (fallback to filename); detect language
  via `langdetect` (DetectorFactory.seed=0); extract `#tag` and YAML front-matter
  tags; set `source="notion"`, `source_path`, `created_at`/`modified_at` from file
  metadata; compute `id` as SHA-256 of file content; compute `word_count`
- [x] T011 [P] [US1] Create `src/keep_parser.py` — parse Google Keep JSON export
  (`takeout-*.json` format); map `title`, `textContent` to `NoteRecord`; extract
  labels as tags; set `source="keep"`; handle archived and trashed items (skip trashed);
  detect language; compute SHA-256 id and word_count
- [x] T012 [P] [US1] Create `src/kindle_parser.py` — parse Kindle clippings
  (`My Clippings.txt`) format; group highlights by book title; each book becomes one
  `NoteRecord` with all highlights as body; set `source="kindle"`; extract book title
  and author as title; detect language; compute SHA-256 id and word_count
- [x] T013 [P] [US1] Create `src/classifier.py` — `classify(note: NoteRecord)`
  returning `(primary_domain, secondary_domain | None)`; stage 1: keyword scoring
  against `domains.yaml` seed terms (case-insensitive substring match, score = match
  count / total seeds); stage 2: if top-2 scores within 0.10, compute cosine similarity
  against pre-computed domain centroid embeddings; `precompute_centroids(domains, encoder)`
  computing mean embedding of seed terms per domain and caching to
  `config/centroids.pkl`; `--precompute` CLI flag; secondary domain set when top-2
  scores within 0.05 after stage 2
- [x] T014 [P] [US1] Create `src/dedup.py` — `check_duplicate(note: NoteRecord)`
  embedding the note body with `"query: "` prefix, calling
  `vector_store.query_similar()` across all domain collections, returning the closest
  existing wiki page slug if cosine similarity ≥ `DUPLICATE_THRESHOLD` (from
  settings.yaml, default 0.90), else `None`; if duplicate found, generate merge
  proposal description comparing both page texts
- [x] T015 [US1] Create `src/ollama_agent.py` — `generate_proposal(note, domain_index)`
  calling `ollama.chat(model, messages, format="json")` with `PROPOSAL_PROMPT` from
  contracts/proposal-schema.md; enforce 60s timeout via `concurrent.futures.ThreadPoolExecutor`;
  apply all post-processing from proposal-schema.md (link validation, confidence
  penalty, min_confidence gate, fast_track_eligible determination, link_only override);
  retry once on JSON parse error with stricter prompt suffix; send to `errors` table
  on second failure or timeout; `link_only` flag set when `word_count < 100` and
  `is_new_page=False`
- [x] T016 [US1] Create `src/watcher.py` — `RawSourceHandler(FileSystemEventHandler)`
  with 1-second debounce (per-path `_last_modified` dict); `on_created`, `on_modified`
  enqueuing `IngestJob` to `queue.Queue`; `on_deleted` calling `db.mark_deleted()`;
  pipeline worker thread: parse by source type → dedup check → domain classify →
  propose → route to fast-track or pending queue; fast-track path: `db.begin_commit` +
  `commit.commit()` + append to `batch_log.jsonl`; `--once PATH` flag for single-file
  processing without daemon; `--replay` flag calling `commit.replay_unfinished_commits()`
  on startup; main loop: start `watchdog.Observer`, process `IngestJob` queue

**Checkpoint**: `python src/watcher.py --once data/raw/notion/test.md` completes
without errors and `brain.sqlite` contains a Proposal row with `decision=None`.

---

## Phase 3b: User Story 1 — Additional Sources (Google Drive, Evernote, Obsidian)

**Goal**: Extend the ingestion pipeline to cover the three remaining raw source
directories already present in `data/raw/`. Each new parser follows the same
`parse_to_record()` / `parse_to_records()` interface as existing parsers. After
this phase, all five raw source directories are fully wired into `watcher.py` and
`batch_ingest.py`.

**Prerequisite**: Phase 3 complete (T016 merged with C1/C2/H1 fixes already applied).

**Independent Test**: Drop one file from each new source into its directory and
run `python src/watcher.py --once <path>` — a `Proposal` row appears in
`brain.sqlite` with `source` set to `gdrive`, `evernote`, or `obsidian`.

### Implementation for Phase 3b

- [x] T026 [P] [US1] Create `src/gdrive_parser.py` — `GDriveParser.parse_to_record(file_path)`
  returning `NoteRecord`; skip files where first 200 bytes contain
  `excalidraw-plugin: parsed` (return `None`); parse YAML frontmatter if present
  (`---` block) to extract `title`, `created`, `updated`, `source` URL, and `tags`
  list; fallback title: first H1 heading → filename stem; body: file content with
  frontmatter block stripped; set `source="gdrive"`, `source_path` as absolute
  path; detect language via `langdetect`; compute SHA-256 of file content as id;
  compute `word_count`; `GDriveParser.parse_directory_to_records(directory)` globbing
  `**/*.md` recursively, skipping hidden files (`name.startswith('.')`), skipping
  files inside `_resources/` or `*_files/` attachment subdirectories

- [x] T027 [P] [US1] Create `src/evernote_parser.py` — `EvernoteParser.parse_to_record(html_path)`
  returning `NoteRecord`; skip hidden files (`name.startswith('.')`); use
  `BeautifulSoup(content, "lxml")`; extract title from `<meta itemprop="title">`;
  extract created/updated from `<meta itemprop="created">` / `<meta itemprop="updated">`
  (ISO 8601 format `20220704T221453Z` → `datetime`); extract body text from
  `<en-note>` tag if present, else `<body>`; call `.get_text(separator="\n", strip=True)`;
  extract tags from `<li data-target="tag-name">` elements (or equivalent Evernote
  HTML tag markup); set `source="evernote"`, `source_path` as absolute path; detect
  language; compute SHA-256 of raw bytes as id; compute `word_count`;
  `EvernoteParser.parse_directory_to_records(directory)` globbing `**/*.html`
  recursively, skipping hidden files and files inside `*_files/` attachment
  subdirectories (directory name ending in ` files` or `_files`)

- [x] T028 [P] [US1] Create `src/obsidian_parser.py` — `ObsidianParser.parse_to_record(file_path)`
  returning `NoteRecord`; parse YAML frontmatter block (`---`) for `title`, `tags`,
  `created`, `updated`; strip `[[wikilink]]` and `![[embedded]]` syntax from body
  (replace with the display text only, e.g. `[[Page Title]]` → `Page Title`);
  extract `#hashtag` tokens from body as additional tags (exclude code blocks);
  skip `.obsidian/` config files and template files; set `source="obsidian"`,
  `source_path` as absolute path; detect language; compute SHA-256 of file content
  as id; compute `word_count`; `ObsidianParser.parse_directory_to_records(directory)`
  globbing `**/*.md` recursively, skipping hidden files and the `.obsidian/`
  config directory

- [x] T029 [US1] Extend `src/watcher.py` and `src/batch_ingest.py` to route new
  sources: in `_parse_note()` add `elif` branches for `gdrive` (`.md` →
  `GDriveParser.parse_to_record`, returns `[]` if skipped), `evernote` (`.html` →
  `EvernoteParser.parse_to_record`, returns `[]` if skipped), and `obsidian` (`.md` →
  `ObsidianParser.parse_to_record`, returns `[]` if skipped); in
  `batch_ingest._source_glob()` add `"evernote": "**/*.html"` using `rglob` (Evernote
  notes are nested in topic subdirectories) and `"gdrive": "**/*.md"` and
  `"obsidian": "**/*.md"` — note that gdrive and evernote require recursive glob
  unlike notion/keep which are flat; update the `_already_processed` note to handle
  recursive paths correctly (source_path is already absolute, so no change needed)

**Checkpoint**: `python src/batch_ingest.py --status` shows notes from `gdrive`,
`evernote`, and `obsidian` sources after running `--once` on one file from each.

---

## Phase 4: User Story 2 — Human Review Gate (Priority: P1)

**Goal**: A user runs the review CLI, sees a colored diff of the queued proposal,
approves it, and all 7 commit steps complete atomically. Interrupted commits replay
correctly on restart.

**Independent Test**: Queue a proposal, run `python src/review_cli.py`, press `a`,
and verify: wiki page file written, ChromaDB upserted, cross-links.md updated, domain
index.md updated, git commit created, brain.sqlite note status = "committed" — all
from a single keypress.

### Implementation for User Story 2

- [x] T017 [US2] Create `src/commit.py` — `commit(proposal, note)` executing all 7
  steps from data-model.md in order (begin_commit, write_wiki_page,
  vector_store.upsert, register_cross_links, update_domain_index, git_commit_wiki,
  finish_commit); all steps 1–6 idempotent; `db.finish_commit()` always last;
  exception handler calls `db.fail_commit()` and `db.log_error()`; `replay_unfinished_commits()`
  querying `commits WHERE status='committing'` and replaying each; `revert_commit(git_hash)`
  running `git -C wiki/ revert --no-edit {git_hash}` for retroactive rejections;
  `render_wiki_page(existing_content, proposal, note)` generating markdown + YAML
  front matter with all fields from data-model.md WikiPage schema
- [x] T018 [US2] Create `src/review_cli.py` — `rich`-based TUI; load pending proposals
  from `brain.sqlite` (status=classified, not fast-tracked, ordered by created_at ASC);
  render colored diff using `rich.syntax` or `rich.console` (green additions, red
  removals; full content as additions for new pages); display header: proposal index,
  slug, domain, confidence, note source, new/existing flag; keybindings from
  cli-contract.md (a/e/r/s/b/q/?); `e` opens `$EDITOR` with proposed content,
  commits the saved result; `r` prompts for rejection reason text before recording;
  `b` approves all remaining fast_track_eligible proposals without display; batch log
  mode (`--batch-log`): list fast-tracked entries, keybinding `r` triggers
  `commit.revert_commit(git_hash)`; `--domain DOMAIN` filter flag

**Checkpoint**: Full end-to-end flow works: watcher detects file → proposal queued →
review CLI displays diff → `a` triggers commit → all 7 commit steps verified in logs.

---

## Phase 5: User Story 3 — Natural Language Query (Priority: P2)

**Goal**: A user runs a query in Portuguese (or any supported language) and receives
a synthesized answer with `[[wikilink]]` citations, grounded exclusively in the
compiled wiki.

**Independent Test**: With ≥ 10 compiled wiki pages across 2 domains, run
`python src/query.py "O que é antifragilidade?"` and verify the response contains
`[[antifragility]]` and no information absent from the retrieved pages.

### Implementation for User Story 3

- [x] T019 [US3] Create `src/query.py` — `search_and_synthesize(question, domain=None)`
  implementing the full retrieval flow from plan.md: language detection via langdetect;
  if `domain` given: single-domain `vector_store.search()`; if no domain: cross-domain
  `vector_store.cross_domain_search()`; build `QUERY_PROMPT` from contracts/proposal-schema.md
  with retrieved pages; call `ollama.chat()` for synthesis (no `format="json"`, free
  text response); return answer string with `[[wikilink]]` citations; explicit "not
  found" message when no pages retrieved; `--domain` CLI flag; print response to
  stdout with source slugs listed below

**Checkpoint**: `python src/query.py "question"` returns a synthesized answer within
2 seconds on GPU for single-domain queries. Cross-domain query with no `--domain`
flag returns re-ranked results.

---

## Phase 6: User Story 4 — Wiki Integrity Maintenance (Priority: P2)

**Goal**: Daily structural lint runs in < 60 seconds and produces a JSON report with
all 7 issue types. Monthly semantic lint flags intra-page contradictions in recently
modified pages.

**Independent Test**: With ≥ 1 orphan page and ≥ 1 broken slug reference in the wiki,
run `python src/lint.py --tier structural` and verify both issues appear in the output
JSON report with correct issue types and page slugs.

### Implementation for User Story 4

- [x] T020 [US4] Create `src/lint.py` — structural tier (Python only, no LLM):
  `run_structural(domain=None)` scanning all wiki pages via `wiki_store.list_all_pages()`,
  checking all 7 issue types from lint-report-schema.md (orphan_page, missing_concept,
  stale_page, low_confidence_page, deleted_source_orphan, failed_commit, domain_over_limit,
  page_too_large); write JSON report to `wiki/lint/structural-{YYYY-MM-DD}.json`;
  semantic tier (Ollama): `run_semantic(domain)` loading pages modified in last
  `semantic_lookback_days` days, calling `ollama.chat()` with `SEMANTIC_LINT_PROMPT`
  per page, collecting contradiction and unsupported-claim findings; write JSON report
  to `wiki/lint/semantic-{YYYY-MM-DD}-{domain}.json`; CLI args: `--tier structural|semantic`,
  `--domain DOMAIN`, `--after-commits N`; exit code 0 (no issues) or 1 (issues found);
  print summary to stdout

**Checkpoint**: `python src/lint.py --tier structural` completes in < 60 seconds on
a 100-page wiki and writes a valid JSON report matching lint-report-schema.md.

---

## Phase 7: User Story 5 — AI Agent Access via MCP (Priority: P3)

**Goal**: The MCP server runs as a sidecar and responds to wiki page requests and
knowledge base queries from Claude Code within 2 seconds. All write attempts are
rejected.

**Independent Test**: Start `python src/mcp_server.py`, then verify: (1) a page
request returns full wiki page content; (2) a query returns a synthesized answer
with citations; (3) a write attempt returns the `WRITE_FORBIDDEN` error.

### Implementation for User Story 5

- [x] T021 [US5] Create `src/mcp_server.py` — `FastMCP("second-brain")` server;
  `@mcp.resource("wiki://{slug}")` calling `wiki_store.read_wiki_page_by_slug(slug)`,
  returning `"Page '{slug}' not found in wiki"` error when missing;
  `@mcp.tool() query_knowledge_base(question, domain=None)` calling
  `query.search_and_synthesize()`; `@mcp.tool() list_domains()` returning JSON array
  from `wiki_store.list_all_pages()` aggregated by domain; `@mcp.tool() list_pages(domain)`
  returning JSON array of page summaries; write rejection: `ValueError("write operations are not permitted")` raised in any tool that would mutate state; `mcp.run(port=8765, host="localhost")`;
  `--port` and `--host` CLI flags

**Checkpoint**: MCP server starts without errors, page retrieval responds in < 2s,
and `curl` tests from quickstart.md Step 9 all pass.

---

## Final Phase: Polish & Cross-Cutting Concerns

**Purpose**: Backup automation, example config files, optional UI, and quickstart
validation.

- [x] T022 [P] Create `db/backups/backup.sh` — daily backup script: `sqlite3`
  backup API via Python or `cp db/brain.sqlite db/backups/brain-{date}.sqlite`;
  `tar -czf db/backups/chroma-{date}.tar.gz data/processed/chroma/`;
  `find db/backups/ -mtime +30 -delete` for 30-day retention; cron-installable
- [x] T023 [P] Create `config/settings.yaml.example` and `config/domains.yaml.example`
  as template files (copies of the working configs with placeholder values);
  required by quickstart.md Step 3
- [x] T024 [P] Create `src/app.py` — optional Gradio UI with a single query
  interface: text input for question, domain dropdown, submit button, response
  display with wikilink formatting; calls `query.search_and_synthesize()`
- [ ] T025 Run quickstart.md validation end-to-end (Steps 1–10) and verify all
  10 checklist items pass; fix any issues found during validation
  *(deferred: requires Ollama running with `ollama pull qwen3.5:9b`)*

---

## Phase 3c: Slug Quality & Rename

**Purpose**: Fix slug generation for non-ASCII languages and provide a safe rename
workflow for already-committed pages with broken or overly long slugs.

- [x] T030 [P] Fix `_slugify()` in `src/ollama_agent.py` — replace bare `re.sub`
  character-strip with `unicodedata.normalize("NFKD") + encode("ascii","ignore")`
  so accented characters transliterate instead of being deleted
  (ã→a, ç→c, ê→e, ó→o, etc.); reduce max slug length from 80 to 60 chars;
  add slug brevity rule to `PROPOSAL_PROMPT`: "1–4 words, lowercase-hyphenated,
  max 40 chars"

- [x] T031 Implement `rename_wiki_page(domain, old_slug, new_slug)` in
  `src/wiki_store.py` — atomically: (1) `git mv` the page file; (2) update
  `slug:` field in the page's own YAML front matter; (3) rewrite matching row
  in `wiki/domains/{domain}/index.md`; (4) rewrite all occurrences in
  `wiki/cross-links.md`; (5) scan every other wiki page and rewrite front-matter
  links pointing to the old slug; (6) `git commit -m "rename: old → new"`;
  add `__main__` entry point so it is callable as
  `uv run python src/wiki_store.py rename <domain> <old> <new>`;
  note: ChromaDB and SQLite updates are the caller's responsibility (documented
  in RUNBOOK.md §4 "Rename a wiki page slug")

---

## Phase 3d: Review UX & Auto-Throttle

**Purpose**: Reduce manual review friction for low-risk proposals that just miss the
auto-track threshold, and give the reviewer a one-key escape hatch to fast-track the
current proposal without approving everything remaining.

**Prerequisite**: Phase 4 complete (T018 — review CLI exists).

- [x] T032 [P] [US2] Add `f` fast-track key to `src/review_cli.py` — in
  `_handle_proposal()` add `elif key == "f":` branch that (1) calls
  `db.set_proposal_decision(proposal.id, "fast_tracked")`; (2) calls
  `db.set_note_status(note.id, NoteStatus.COMMITTED)`; (3) calls
  `do_commit(proposal, note)` inside a try/except; (4) prints
  `[green]✓ Fast-tracked: {proposal.proposed_page}[/green]`; (5) returns
  `"fast_tracked"`; update the help bar and `?` panel to include
  `[bold][f][/bold]ast-track`; `f` works regardless of `fast_track_eligible`
  flag — it is a manual override by the human reviewer

- [x] T033 [P] [US2] Add `link_only_fast_track_confidence` to
  `config/settings.yaml` under `ingestion:` (value: `0.75`) and update
  `_is_fast_track()` in `src/ollama_agent.py` to use it: when
  `proposal.link_only is True` compare against
  `cfg["ingestion"]["link_only_fast_track_confidence"]` instead of
  `fast_track_confidence`; this lets LINK ONLY proposals at ≥ 0.75 confidence
  auto-commit without hitting the review queue, matching the lower risk profile
  of link-only changes (no new pages, no new cross-references)

**Checkpoint**: Press `f` on a pending proposal and verify it commits and moves to the
next without prompting. Set `link_only_fast_track_confidence: 0.75` and confirm a
LINK ONLY proposal with conf 0.80 is fast-tracked automatically by the watcher.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately; T002–T005 are all [P]
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories;
  T006 must complete before T007, T008, T009 (all [P] with each other after T006)
- **US1 (Phase 3)**: Depends on Phase 2 — T010–T014 are all [P] with each other;
  T015 depends on T013 (needs classifier for domain context); T016 depends on T015
- **US1 (Phase 3b)**: Depends on Phase 3 — T026, T027, T028 all [P] with each other;
  T029 depends on T026 + T027 + T028
- **Slug quality (Phase 3c)**: Depends on Phase 3 — T030 and T031 are [P] with each
  other; can run alongside any phase without blocking
- **US2 (Phase 4)**: Depends on Phase 2 + Phase 3 (needs watcher to produce proposals);
  Phase 3b can run in parallel with Phase 4 (additional sources don't block review CLI)
- **US3 (Phase 5)**: Depends on Phase 2 + Phase 4 (needs a populated wiki to query)
- **US4 (Phase 6)**: Depends on Phase 2 + Phase 4 (needs wiki pages + SQLite data)
- **US5 (Phase 7)**: Depends on Phase 5 + Phase 6 (MCP wraps query + wiki_store)
- **Polish (Final)**: Depends on all user story phases

### User Story Dependencies

- **US1 (P1)**: Starts after Phase 2 — no dependency on other user stories
- **US2 (P1)**: Starts after US1 — needs proposal queue to exist
- **US3 (P2)**: Starts after US2 — needs a populated wiki to return results
- **US4 (P2)**: Can start in parallel with US3 after US2 — both depend on US2 only
- **US5 (P3)**: Starts after US3 + US4 — wraps both query and lint contexts

### Within Each User Story

- US1: T010–T014 parallel → T015 → T016; then T026/T027/T028 parallel → T029
- US2: T017 → T018
- US3: T019 (single task)
- US4: T020 (single task)
- US5: T021 (single task)

### Parallel Opportunities

- All Phase 1 tasks T002–T005 can run in parallel after T001
- Phase 2: T007, T008, T009 run in parallel after T006
- US1: T010, T011, T012, T013, T014 all run in parallel; T015 after T013; T016 after T015
- US3 and US4 run in parallel after US2
- Final Phase: T022, T023, T024 all run in parallel before T025

---

## Parallel Example: US1

```bash
# After Phase 2 completes:
Task: "Create src/notion_parser.py"     # T010 [P]
Task: "Create src/keep_parser.py"       # T011 [P]
Task: "Create src/kindle_parser.py"     # T012 [P]
Task: "Create src/classifier.py"        # T013 [P]
Task: "Create src/dedup.py"             # T014 [P]

# After T013 completes:
Task: "Create src/ollama_agent.py"      # T015

# After T015 completes:
Task: "Create src/watcher.py"           # T016
```

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 1: Setup (T001–T005)
2. Complete Phase 2: Foundational (T006–T009)
3. Complete Phase 3: US1 — file detection + proposal generation (T010–T016)
4. **STOP and VALIDATE**: `python src/watcher.py --once` produces a queued proposal
5. Complete Phase 4: US2 — review CLI + atomic commit (T017–T018)
6. **STOP and VALIDATE**: full end-to-end flow, verify all 7 commit steps

At this point the calibration sprint can begin on the first 500 notes.

### Incremental Delivery

1. MVP (US1 + US2) → calibration sprint → tune thresholds
2. Add US3 (query) → test multilingual retrieval on populated wiki
3. Add US4 (lint) in parallel with US3 → establish integrity baseline
4. Add US5 (MCP) → enable Claude Code integration
5. Polish → backup automation, optional UI

### Calibration Sprint Gate (between MVP and US3)

Before enabling fast-track and proceeding to US3:
- Set `fast_track_confidence: 1.01` in settings.yaml (disables fast-track)
- Process first 500 notes manually through review CLI
- Measure rejection rate per domain
- Enable fast-track only when rejection rate < 15% per domain

---

## Notes

- [P] tasks = different files, no shared-state dependencies — safe to run in parallel
- [Story] labels map tasks to spec.md user stories for traceability
- Tests not included (not requested in spec); add TDD workflow via `/speckit.tdd` if desired
- Fast-track is **disabled by default** in settings.yaml (threshold > 1.0); enable only after calibration sprint passes
- The `wiki/` directory is a separate git repo from the project repo — initialize separately in T002
- `db.py --init` flag required for first-run schema creation; call from quickstart
- GPU (CUDA) is assumed for sentence-transformers; `device="cuda"` must be explicit
- Commit after each task or logical group; stop at phase checkpoints to validate
