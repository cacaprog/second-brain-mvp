# Second Brain 🧠

A local-first, multilingual knowledge system that turns 18,000+ scattered notes into a
compiled, cross-linked wiki that thinks alongside you.

Personal notes from Notion, Google Keep, Kindle, Evernote, Google Drive and Obsidian —
in Portuguese, English, French and Spanish — are ingested, classified into knowledge
domains, and synthesized by a local LLM into concept pages. A human approves every new
page and every link. The result is queryable in natural language, browsable as an
Obsidian graph, and available to AI agents over MCP.

Everything runs on your machine. No note, embedding, query, or answer ever leaves it.

---

## How this project started

### It began as a search box

The first version was an MVP: parse the exports from Notion, Keep and Kindle, embed
every note with a multilingual model, drop the vectors into ChromaDB, and put a search
box on top. Ask for "mental models" and it would also surface the Portuguese notes
about "modelos mentais". That part worked.

But it never *synthesized*. Every query started from zero. The system retrieved chunks
and rephrased them — a glorified search box. It could not answer "what is my evolving
view on X?", because that answer lived across dozens of notes and nowhere in
particular. The library did not grow. It just got easier to look things up in.

### Then: Karpathy's LLM wiki

The turn came from an idea Andrej Karpathy published: use an LLM to *maintain a
personal wiki*. Instead of re-deriving answers from raw notes at query time, you let
the model compile the notes into a structured set of concept pages that cross-link with
`[[wikilinks]]` and deepen over time. The wiki is a persistent, compounding artifact —
the connections are already there when you arrive.

That reframed the goal. Not better retrieval. **Accumulation of understanding.**

This is where the three influences meet:

- **Zettelkasten** — atomic notes, explicit links, structure that emerges from the
  links rather than from a predefined hierarchy.
- **Second Brain** — capture from every source, then distil and express; notes are raw
  material for output, not an archive.
- **Karpathy's LLM wiki** — an LLM agent does the distilling, incrementally, into
  Markdown concept pages you can open in Obsidian.

### The breaking point

Karpathy's pattern was validated up to roughly 80–100 articles. Past that, the corpus
no longer fits in a local model's context window. Feed it only a slice and the model
can't see what already exists in the wiki — so it invents connections. It writes a
`[[wikilink]]` to a page that doesn't exist, or worse, to one that does but is wrong.

In a plain RAG system a hallucinated answer is bad but contained. In a Zettelkasten a
hallucinated link is **structural corruption**: it creates a false associative trail
that compounds through every future query that passes over it. At 18,000 notes, the
naive LLM-wiki approach doesn't slow down — it breaks.

### The hybrid

Second Brain v2 layers the two patterns and solves scale with three principles:

1. **Domain sharding.** The corpus is split into 25 bounded domains. The LLM never sees
   the whole corpus — only one domain's index (~3,000 tokens) plus the incoming note.
   This is what makes it scale past 100 notes without hallucinating.
2. **The human gate — the LLM proposes, the human commits.** No LLM output reaches the
   wiki without review. New pages and new links *always* require real-time approval.
   High-confidence updates to existing pages can be fast-tracked, logged, and reverted
   retroactively via git.
3. **Wiki-first indexing.** ChromaDB embeds the *compiled wiki pages*, never the raw
   notes. Search and synthesis run over synthesized, cross-linked knowledge — not over
   the raw pile.

Raw sources stay immutable. The wiki is versioned in git. Every proposal, decision,
commit and error is recorded in SQLite so the whole pipeline can be replayed or
audited.

---

## The goal

1. **Ingest everything** — every note, from every source, in every language, across
   every domain. Nothing stays trapped in a silo; nothing is silently dropped.
2. **A meaningful interface to my notes** — ask questions in natural language and get a
   synthesized answer grounded in my own wiki, with citations; browse the concept graph
   in Obsidian; reach the wiki from Claude Code over MCP.
3. **Amplify the knowledge base** — the wiki compiles raw notes into concept pages that
   get deeper each time a related note is ingested. ~18,000 notes → ~1,100–1,750
   concept pages (a 10–15× compression into reusable understanding).
4. **Create content from my observations** — use the compiled, cited wiki as grounded
   raw material for writing, drafts, and research.

---

## How it works

```
Raw sources (data/raw/)
  notion/  keep/  kindle/  gdrive/  evernote/  obsidian/  articles/  papers/
        │
        │  file watcher  (create / modify / delete)
        ▼
Phase 1 — Automated
  parse → dedup check (ChromaDB) → classify into domain → LLM proposal
  (the LLM sees only that domain's index — bounded context)
        │
        ▼
  Fast-track eligible?   confidence high · no flags · existing page · links exist
     ├── yes ──►  auto-approve + append to batch_log.jsonl  (revertible)
     └── no  ──►  Phase 2 — Human gate
                     review_cli.py: colored diff → approve / edit / reject / skip
        │
        ▼  approved
Commit layer (SQLite-coordinated, atomic, idempotent replay on restart)
  write wiki page → upsert ChromaDB → register cross-links → update domain index
  → git commit → mark note committed
        │
        ├──►  Query layer      bi-encoder retrieval → cross-encoder re-rank
        │                      → LLM synthesis → answer + [[wikilink]] citations
        │                      ( --save writes the answer back as a wiki page )
        │
        ├──►  MCP server       read-only; page-by-slug + natural-language query
        │
        └──►  Lint             structural (daily, deterministic)
                               semantic (monthly, intra-page contradiction check)
```

Read the wiki itself in **Obsidian** — graph view, backlinks and `[[wikilinks]]` work
out of the box because every page is Markdown + YAML front matter.

---

## What's in the box

| | |
|---|---|
| **Sources** | Notion (`.md`), Google Keep (`.json`), Kindle (`My Clippings.txt`), Evernote (`.html`), Google Drive / Obsidian vault (`.md`, recursive), web clippings (`data/raw/articles/`), PDF papers (`data/raw/papers/`) |
| **Languages** | Portuguese, English, French, Spanish (others best-effort). Embeddings are language-agnostic — a Portuguese query surfaces English pages and vice-versa |
| **Domains** | 25, from `analytics` and `philosophy` to `neuroscience`, `theology`, `sociology` and `design` — configurable in `config/domains.yaml` |
| **Note types** | personal notes, multi-domain Kindle books (highlights split by topic), and structured **knowledge cards** for articles, papers and rich notes (Summary · Key Findings · Core Concepts · Questions Raised) |

### Local stack

- **LLM**: Ollama running Qwen 3.5 9B (swappable in `config/settings.yaml`)
- **Bi-encoder**: `BAAI/bge-m3` — 1024-dim multilingual embeddings
- **Cross-encoder**: `BAAI/bge-reranker-v2-m3` — cross-domain re-ranking
- **Vector store**: ChromaDB, one collection per domain
- **Metadata + commit coordinator**: SQLite (`db/brain.sqlite`)
- **Wiki**: Markdown + YAML front matter, versioned in its own git repo, read in Obsidian
- **Review**: `rich`-based CLI with a colored diff and one-key decisions
- **Agents**: read-only MCP server on `localhost:8765`
- **Hardware target**: NVIDIA RTX 3060 12 GB, Python 3.11+ via `uv`

---

## Quick start

Full setup, calibration and operations are in **[RUNBOOK.md](RUNBOOK.md)**. The short
version:

```bash
# 1. Ollama + model
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3.5:9b

# 2. Python deps
uv sync

# 3. Initialize the database and the wiki repo
uv run python src/db.py --init
git init wiki/

# 4. Pre-compute domain centroids (needed by the classifier)
uv run python src/classifier.py --precompute

# 5. Drop a note in and process it end-to-end
cp mynote.md data/raw/notion/
uv run python src/watcher.py --once data/raw/notion/mynote.md
uv run python src/review_cli.py        # press 'a' to approve
uv run python src/query.py "what did I capture about antifragility?"
```

---

## Using it day to day

```bash
# Ingest a source in review-paced batches of 50
uv run python src/batch_ingest.py --dir data/raw/evernote --limit 50 --batch-size 50
uv run python src/batch_ingest.py --dir data/raw/kindle          # all books in one pass

# Review the queue (optionally per-domain)
uv run python src/review_cli.py --domain philosophy
uv run python src/review_cli.py --recover-rejected               # undo accidental rejects

# Ask the wiki
uv run python src/query.py "How do cognitive biases affect financial decisions?"
uv run python src/query.py "O que é antifragilidade?" --domain philosophy
uv run python src/query.py "impact of AI on jobs" --save          # save answer as a wiki page

# Maintenance
uv run python src/lint.py --tier structural
uv run python src/wiki_cleaner.py --dry-run                       # consolidate repetitive pages
uv run python src/wiki_merger.py detect                           # find duplicate slugs
uv run python src/slug_migrator.py detect                         # audit slug quality

# Expose the wiki to Claude Code / MCP agents (read-only)
uv run python src/mcp_server.py
```

Check ingestion completeness any time with `uv run python src/batch_ingest.py --status`.

---

## How it evolved

The system is built spec-first — every change is a numbered spec in
[`specs/`](specs/), planned and implemented in sequence.

| Spec | What it added |
|---|---|
| **001** — second-brain-v2-system | The hybrid Zettelkasten: watcher, parsers, dedup, classifier, LLM proposals, human gate, atomic commit, query layer, two-tier lint, MCP server |
| **002** — kindle-multi-domain | Every highlight in a book is processed (not just the first ~20); one book can produce entries in several domains |
| **003** — expand-body-limit | Proposal generation uses up to 12,000 characters — long Evernote / GDrive notes are fully represented |
| **004** — undo-reject | `u` to undo an accidental rejection in-session; `--recover-rejected` for past sessions |
| **005** — article-knowledge-cards | Web clippings and PDF papers become structured four-section knowledge cards |
| **006** — clean-wiki-notes | One-time cleanup that consolidates pages bloated with near-duplicate paragraphs from pre-calibration ingestion |
| **007** — merge-slug-duplicates | Detect and merge near-identical page slugs within and across domains |
| **008** — smart-wiki-cleaner | The cleaner never touches structured knowledge cards and only acts on proven repetition |
| **009** — rich-note-knowledge-cards | Personal notes of 4+ paragraphs get the same structured knowledge-card treatment as articles |
| **010** — query-export-wiki | `query.py --save` writes a query, its answer and its sources back into the wiki as a valid page |
| **011** — better-wiki-slugs | Concept-based slug generation for new pages, plus a migration that re-slugs the existing wiki |

---

## Design principles

From [`.specify/memory/constitution.md`](.specify/memory/constitution.md):

1. **The human gate** — the LLM proposes, the human commits. New pages and new links are never auto-approved.
2. **Wiki-first indexing** — embed compiled pages, never raw notes.
3. **Domain-bounded context** — one domain index per LLM call; the full corpus is never loaded at once.
4. **Immutable raw sources** — `data/raw/` is append-only; every other artifact is reconstructable from it.
5. **Audit trail first-class** — every proposal, decision, commit and error is in SQLite.
6. **Local and private** — no content, embedding, query or answer leaves the machine; the read-only MCP server is the only external interface.
7. **Fail visibly, recover deterministically** — interrupted commits replay idempotently on restart; failures surface, they don't degrade silently.

---

## Project structure

```
second-brain-mvp/
├── src/
│   ├── watcher.py            # file watcher (create / modify / delete)
│   ├── models.py             # NoteRecord, Proposal, WikiPage
│   ├── *_parser.py           # notion / keep / kindle / evernote / gdrive / obsidian / article / pdf
│   ├── chunker.py            # split long / multi-domain sources
│   ├── dedup.py              # pre-commit near-duplicate check via ChromaDB
│   ├── classifier.py         # keyword + centroid domain classification
│   ├── ollama_agent.py       # proposal engine (calls the local LLM)
│   ├── review_cli.py         # human gate — colored diff + decisions
│   ├── commit.py             # SQLite-coordinated atomic commit
│   ├── wiki_store.py         # read / write wiki markdown, manage wikilinks, rename slugs
│   ├── vector_store.py       # ChromaDB wrapper + cross-encoder re-ranker
│   ├── query.py              # retrieval + synthesis; --save export
│   ├── query_exporter.py     # write query results back as wiki pages
│   ├── lint.py               # structural (daily) + semantic (monthly) checks
│   ├── wiki_cleaner.py       # consolidate repetitive page bodies
│   ├── wiki_merger.py        # merge duplicate slugs
│   ├── slug_migrator.py      # bulk re-slug the wiki
│   └── mcp_server.py         # read-only MCP resource server
├── wiki/                     # compiled wiki — git repo, one dir per domain, read in Obsidian
├── data/
│   ├── raw/                  # immutable source exports
│   └── processed/chroma/     # ChromaDB persistent storage
├── db/                       # brain.sqlite + daily backups
├── config/                   # settings.yaml, domains.yaml
├── specs/                    # numbered feature specs (spec-driven development)
└── RUNBOOK.md                # setup, calibration sprint, operations
```

---

**Built with**: Python 3.11+, Ollama (Qwen 3.5), ChromaDB, Sentence Transformers (BGE-M3),
SQLite, watchdog, rich, FastMCP — and Obsidian for reading the graph.
