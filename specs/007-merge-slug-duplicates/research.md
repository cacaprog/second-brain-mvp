# Research: Wiki Slug Duplicate Merger

## Gap Analysis: Existing Modules

### wiki_store.py

**Available (reuse as-is):**
- `read_wiki_page(domain, slug)` — read page content
- `write_wiki_page(domain, slug, content)` — overwrite page
- `_parse_front_matter(content)` — extract YAML metadata
- `update_domain_index(domain, slug, description, languages)` — upsert index row
- `list_all_pages()` — scan all wiki pages with metadata (used for detection)
- `rename_wiki_page()` — reference for git mv pattern

**Missing (must add):**
- `delete_wiki_page(domain, slug)` — delete the `.md` file from disk
- `remove_slug_from_index(domain, slug)` — remove a row from the domain `index.md` table

### vector_store.py

**Available (reuse as-is):**
- `upsert(slug, content, domain, language)` — upsert embedding (call on canonical after merge)

**Missing (must add):**
- `delete_embedding(slug, domain)` — remove a single slug's embedding from ChromaDB collection

### db.py

**Available (reuse as-is):**
- `set_note_status(note_id, status, wiki_page)` — can set wiki_page on existing notes

**Missing (must add):**
- `get_notes_by_wiki_page(wiki_page: str) -> list[str]` — return note IDs with that wiki_page
- `clear_wiki_page(wiki_page: str) -> None` — `UPDATE notes SET wiki_page=NULL WHERE wiki_page=?`

---

## Slug Normalization Rule

Decision: strip leading/trailing dashes; collapse 2+ consecutive dashes to one.

```
normalize(slug) = re.sub(r'-{2,}', '-', slug).strip('-')
```

Rationale: covers all known duplicate patterns in the current wiki (`-` trailing, `--` double-dash). Does not over-normalize (e.g. won't collapse `outcome` ≠ `outcomes` — those are reported as near-duplicates only within same-domain, and the user decides whether to merge them).

Alternatives considered:
- Full unicode normalization (rejected — slugs are already ASCII after ingestion)
- Levenshtein distance threshold (rejected — too many false positives across unrelated short slugs)

---

## Canonical Selection Rules

**Same-domain pair** — canonical = the slug that is already normalized (i.e., `normalize(slug) == slug`). If both are already normalized (edge case), pick the one with higher confidence; ties go alphabetically.

**Cross-domain group** — canonical = the domain/page with the highest `confidence` value in front matter. Ties broken by domain name alphabetically (deterministic).

Rationale: For same-domain, the clean slug is always the right survivor — the dirty one (trailing dash, double dash) was a parser artifact. For cross-domain, confidence reflects how well the page body synthesizes its sources; the strongest synthesis wins.

---

## Body Consolidation Strategy

Reuse `_consolidate(paragraphs, cfg)` from `wiki_cleaner.py` directly (import it). Do not duplicate.

Skip the LLM call when all pages' bodies are identical after stripping whitespace. Identical is defined as normalized text equality (strip + lower).

---

## ChromaDB Cleanup

After deleting a redundant page: call `vector_store.delete_embedding(slug, domain)` for each deleted page.
After writing the merged canonical: call `vector_store.upsert(slug, body, domain, language)` to refresh the embedding with merged content.

ChromaDB collection naming follows the existing pattern in `vector_store.py` (one collection per domain). `delete_embedding` must use `collection.delete(where={"slug": slug})` — ChromaDB supports this filter.

---

## Known Same-Domain Pairs (current wiki)

| Domain | Dirty slug | Canonical slug |
|--------|-----------|----------------|
| behavioral-economics | `a-logica-do-consumo-verdades-e-mentiras-` | `a-logica-do-consumo-verdades-e-mentiras` |
| psychology | `as-consequencias-vem--depois` | `as-consequencias-vem-depois` |
| mental-model | `outcome-over-task-completion` | `outcomes-over-task-completion`* |

*Note: `outcome` vs `outcomes` — these normalize to different strings, so they are NOT detected by the normalization rule. They appear as a cross-domain candidate only if the slugs match exactly. They are separate concepts; this pair should be manually reviewed, not auto-merged.

## Known Cross-Domain Groups (current wiki, sample)

| Slug | Domains |
|------|---------|
| `antifragilidade` | market, mental-model, philosophy, psychology, theology |
| `resolucao-de-problemas` | math, mental-model, tech |
| `cercas-de-mel` | philosophy, theology |
| `a-teimosia-dos-humanos-em-transferir-as-suas-qualidades-para-as-coisas` | behavioral-economics, mental-model, psychology |
| `novas-combinacoes-conhecimento` | data-science, mental-model |
| `simplificacao-ato-intelectual` | mental-model, psychology |
| `candido-ou-o-otimismo` | philosophy, sociology |
| `untitled-keep-note` | psychology, tech, theology |

Full list available from detect mode at runtime.
