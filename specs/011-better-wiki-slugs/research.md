# Phase 0 Research: Better Wiki Slugs

No `NEEDS CLARIFICATION` markers remain in the Technical Context — this feature reuses the project's existing stack end to end. This document instead records the design decisions made by reading the current code, since several of them determine the shape of Phase 1.

## Decision: Extract slug-shaping logic into a shared `slug_utils.py`

**Decision**: Move the transliterate/lowercase/hyphenate/truncate logic out of `ollama_agent.py::_slugify()` into a new `src/slug_utils.py`, and have both `ollama_agent.py` (generation) and the new `slug_migrator.py` (retroactive migration) import it.

**Rationale**: The bug being fixed — character-count truncation (`slug[:40]`) instead of word-boundary truncation — must be fixed once, not duplicated. The migration tool needs the exact same cleanup rules applied to LLM output as generation does, or the two paths will drift and re-introduce the inconsistency this feature exists to remove. `query_exporter.py` already has its own, deliberately different `slugify()` (60-char cap, query-text based) — it is out of scope (spec FR-013) and is left untouched.

**Alternatives considered**: Duplicating the cleanup function in `slug_migrator.py` — rejected, guarantees future drift. Putting it in `wiki_store.py` — rejected; that module is scoped to file I/O and git operations, not text transforms, and `ollama_agent.py` already imports from it (`read_domain_index`, `slug_exists_in_index`), so adding an unrelated concern there would blur its purpose.

## Decision: Word-boundary truncation, not character-count truncation

**Decision**: `slugify(text, max_words=4)` splits the cleaned, hyphenated string on `-`, keeps at most `max_words` tokens, and rejoins — never slicing inside a token. The existing prompt already tells the LLM "1–4 words" (`ollama_agent.py:40`); the cleanup step now actually enforces that on the output side too, which also protects against the LLM ignoring the instruction.

**Rationale**: Every confirmed truncation artifact found in the live wiki (`sprint-how-to-solve-big-problems-and-tes`, `apenas-fiquei-la-e-senti-um-turbilhao-em`) is exactly 40 characters — a direct fingerprint of `slug[:40]`. Bounding by word count instead of character count eliminates the failure mode entirely rather than just moving the cutoff.

**Alternatives considered**: Raising the character cap — rejected, delays the same bug rather than fixing it. Truncating to the last full word before a character limit — rejected as unnecessary complexity once word-count bounding is in place; a 4-word concept slug is already well under any reasonable character budget.

## Decision: Collapse punctuation artifacts instead of just stripping

**Decision**: After stripping non-alphanumeric characters, collapse runs of repeated `-` into one and strip leading/trailing `-`, before word-splitting.

**Rationale**: Confirmed artifact examples (`ciencia-e-fe---a-particula-de-deus`, `semana-3---os-anos-iniciais`) come from titles containing a colon or " - " separator; stripping the punctuation without collapsing the resulting empty segments leaves the `---` in place.

## Decision: Placeholder detection with a visible failure path, no more `none.md`

**Decision**: A proposed slug is treated as unusable if it is empty after cleanup or matches a small denylist (`none`, `n-a`, etc.). On an unusable LLM-proposed slug, fall back to a slug derived from `note.title`. If that also produces an unusable slug, raise rather than silently write a placeholder page.

**Rationale**: The wiki's git history shows this exact failure already happened and required manual cleanup (`Remove none.md pages... invalid slug artifact`, `Remove bad none.md page`). The existing code already has *a* fallback-to-title path (`ollama_agent.py:238-242`) and already raises `ValueError` when both are unusable — this feature keeps that behavior and formalizes the placeholder check via the shared `slug_utils.is_placeholder()` rather than an ad hoc `if not slug` check, so the same guard also covers the migration path. This aligns with Constitution Principle VII (fail visibly rather than degrade).

## Decision: No new domain-suffix disambiguation mechanism — tighten the prompt instead

**Decision**: There is no code in the current pipeline that appends a domain name to a slug (confirmed by search — no `f"{slug}-{domain}"`-shaped logic exists anywhere). The `tribes-we-need-you-to-lead-us-analytics` / `...-marketing` pattern is the LLM itself choosing to include the domain word. The fix is a stronger, explicit negative instruction in `PROPOSAL_PROMPT` ("do not append the domain name to the slug") plus a post-hoc guard in `slug_utils` that strips a trailing segment matching the note's own domain name if the LLM ignores the instruction.

**Rationale**: True slug collisions between *unrelated* concepts in the same domain are already caught by the existing human-review gate — `review_cli.py` shows the diff against any existing page at that slug before a human approves, so a genuine collision surfaces as "this doesn't look like the same concept" rather than silently overwriting. No new generation-time disambiguation logic is needed; the domain-suffix pattern was a symptom of loose prompting, not a missing safety mechanism.

**Alternatives considered**: Auto-appending a numeric or content-based disambiguator at generation time — rejected as unnecessary given the human gate already exists for this exact scenario, and it would reintroduce ugly, unreadable slugs by design.

## Decision: Cheap heuristic pre-filter before any migration LLM call

**Decision**: `slug_migrator.py` scans all existing pages (excluding `domains/queries/`) with pure string checks — `len(slug) >= 40`, more than 4 hyphen-separated words, a `--` run, or a slug ending in `-{own domain}` — and only calls Ollama to regenerate a slug for pages that match at least one flag.

**Rationale**: This gives 100% coverage of the "re-evaluated" requirement (spec SC-003) at near-zero cost, while keeping the expensive LLM regeneration step scoped to the actual bad subset (a few dozen pages, not 627). It mirrors the existing pattern in `wiki_cleaner.py`, which also gates its LLM call behind cheap, deterministic pre-checks ("Only actually repetitive paragraphs trigger LLM consolidation").

**Alternatives considered**: Regenerating every page's slug unconditionally — rejected; wasteful, and risks churning already-good slugs (like `antifragilidade`) on every run due to LLM non-determinism, working against FR-014 ("leave unchanged pages untouched").

## Decision: Single-page-scoped regeneration prompt (no domain index)

**Decision**: The migration's regeneration prompt receives only the flagged page's own title/heading and body — not the domain index used by the ingestion proposal prompt.

**Rationale**: Slug quality is a property of a page's own content, not its relationship to sibling pages. Omitting the domain index also keeps this call cheaper and more tightly bounded than the existing proposal call (Constitution Principle III).

## Decision: Idempotency via existing git history, not a new state file

**Decision**: Before regenerating anything, `slug_migrator.py` reads the wiki's own git log for `rename: <old> → <new>` commit messages (the exact format `wiki_store.rename_wiki_page()` already produces) and treats any page whose *current* slug appears as a target of a prior rename as already migrated for this run, skipping it.

**Rationale**: Every rename already produces its own atomic git commit via the existing `rename_wiki_page()` primitive, so the wiki repository is already a complete, durable log of what has been renamed. Reusing it avoids adding a second, parallel source of truth that could drift from the actual file state — directly serves FR-012 (resumability) without new storage.

**Alternatives considered**: A dedicated `migration-log.jsonl` or a new SQLite table — rejected as redundant with information the wiki git history already records durably.

## Decision: Migration collision handling

**Decision**: If two flagged pages in the same domain would regenerate to the same new slug, the migrator appends a second distinguishing word drawn from the losing page's own title before re-checking; if still colliding, that page is left unrenamed and reported as `needs-manual-review` in the summary rather than guessed at.

**Rationale**: Silently overwriting or auto-numbering (`-2`, `-3`) would reintroduce the same kind of unreadable, low-information slug this feature is meant to eliminate. Surfacing an unresolved collision for manual attention matches Constitution Principle VII.

## Decision: Database and vector store updates reuse existing primitives

**Decision**: `slug_migrator.py` calls `wiki_store.rename_wiki_page()` for the file/front-matter/index/cross-link/git side (already implemented and already used by nothing else in-tree, written in anticipation of exactly this kind of use — its own docstring says "ChromaDB and SQLite caller must update their records separately"), then a new `DB.rename_wiki_page(old_slug, new_slug)` (`UPDATE notes SET wiki_page=? WHERE wiki_page=?`) and the existing `VectorStore.delete_embedding()` + `VectorStore.upsert()` pair — the exact same three-call sequence `wiki_merger.py::_merge_group()` already uses for its own file/DB/vector updates.

**Rationale**: All three primitives already exist and are already proven in production by `wiki_merger.py`; only the `DB` side is missing a rename-shaped method (today it only has `clear_wiki_page`, which nulls the reference rather than repointing it — correct for a merge/delete, wrong for a rename).
