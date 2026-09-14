---
description: "Task list for Better Wiki Slugs — Concept-Based Generation & Retroactive Cleanup"
---

# Tasks: Better Wiki Slugs — Concept-Based Generation & Retroactive Cleanup

**Input**: Design documents from `/specs/011-better-wiki-slugs/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/cli.md, quickstart.md

**Tests**: Included — this project's existing modules (`test_query_exporter.py`, `test_review_undo.py`) all have `tests/unit/` coverage, and `plan.md`'s Project Structure already commits to `tests/unit/test_slug_utils.py` and `tests/unit/test_slug_migrator.py`.

**Organization**: Tasks are grouped by user story (US1/US2/US3 from spec.md) to enable independent implementation and testing of each.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths are exact and relative to the repository root

## Path Conventions

Single project — `src/`, `tests/unit/` at repository root (matches every prior feature in this repo).

---

## Phase 1: Setup

**Purpose**: Create the two new module files this feature adds, empty but importable.

- [X] T001 [P] Create `src/slug_utils.py` with a module docstring ("Shared slug-shaping utilities used by both note-ingestion generation and the retroactive wiki slug migration.") and no logic yet.
- [X] T002 [P] Create `src/slug_migrator.py` with a module docstring, the standard imports (`argparse`, `re`, `sys`, `dataclasses.dataclass`, `pathlib.Path`), and an `if __name__ == "__main__":` block with an `argparse.ArgumentParser(description="Retroactive wiki slug quality migration")` and `sub = parser.add_subparsers(dest="command", required=True)` — no subcommands wired yet, following the exact structure already used in `src/wiki_merger.py`.

**Checkpoint**: Both new files exist and import cleanly (`python -c "import slug_utils, slug_migrator"` from `src/`).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared slug-cleanup logic used by every other phase (US1's generation fix and US2/US3's migration engine both depend on it).

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T003 [P] Write unit tests in `tests/unit/test_slug_utils.py` for `slug_utils.slugify()`, `slug_utils.is_placeholder()`, and `slug_utils.strip_domain_suffix()` (these will fail with `ImportError`/`AttributeError` until T004–T006 are done). Cover, following the style of `tests/unit/test_query_exporter.py`:
  - `slugify()` never truncates mid-word regardless of input length (e.g. a 20-word title never produces a slug ending mid-token).
  - `slugify()` caps output at 4 hyphen-separated words by default.
  - `slugify("Ciência e Fé: A Partícula de Deus")` (or an equivalent colon/dash-heavy title) produces no `--` run and no leading/trailing hyphen.
  - `slugify()` transliterates accented characters (ã→a, ç→c, etc.), matching the current `_slugify()` behavior in `src/ollama_agent.py`.
  - `is_placeholder("")`, `is_placeholder("none")`, `is_placeholder("n-a")` are `True`; `is_placeholder("antifragilidade")` is `False`.
  - `strip_domain_suffix("tribes-leadership-marketing", "marketing")` strips the trailing `-marketing`; a slug not ending in its own domain name is returned unchanged.
- [X] T004 Implement `slugify(text: str, max_words: int = 4) -> str` in `src/slug_utils.py`: NFKD-transliterate and lowercase (reuse the existing approach from `src/ollama_agent.py::_slugify`), strip non-alphanumeric characters, collapse repeated `-` into one, strip leading/trailing `-`, split on `-`, keep only the first `max_words` tokens, and rejoin — must never slice inside a token.
- [X] T005 Implement `is_placeholder(slug: str) -> bool` in `src/slug_utils.py`: returns `True` for an empty string or membership in a shared denylist `{"none", "null", "untitled", "no-proposal", "no-concept", "unknown", "n-a"}` — move this set out of `src/ollama_agent.py`'s local `_INVALID_SLUGS` so generation and migration share one definition.
- [X] T006 Implement `strip_domain_suffix(slug: str, domain: str) -> str` in `src/slug_utils.py`: if `slug` ends with `f"-{domain}"`, remove that trailing segment (and re-strip any resulting trailing hyphen); otherwise return `slug` unchanged.
- [X] T007 Run `pytest tests/unit/test_slug_utils.py -v` from the repo root and confirm all tests pass.

**Checkpoint**: `slug_utils.py` is fully implemented and tested. US1 and US2/US3 can now proceed (in parallel, if desired).

---

## Phase 3: User Story 1 - New Notes Get Concept-Based Slugs (Priority: P1) 🎯 MVP

**Goal**: Every note filed into the wiki from now on gets a short, word-boundary-safe, artifact-free, domain-suffix-free slug — and an unusable LLM slug fails visibly instead of ever producing a placeholder page again.

**Independent Test**: Ingest a batch of notes whose titles are long, punctuation-heavy, or instruction-like, and confirm every resulting wiki page slug is a short, readable concept phrase with no truncation artifacts.

### Tests for User Story 1

- [X] T008 [P] [US1] Write unit tests in `tests/unit/test_ollama_agent.py` for `generate_proposal()`'s slug handling, mocking `ollama_agent._call_ollama` (following the `patch("query_exporter.wiki_store")`-style convention in `tests/unit/test_query_exporter.py`, e.g. `patch("ollama_agent._call_ollama")`). Cover:
  - A mocked LLM response with a 40+-character `proposed_page` value produces a slug with no mid-word truncation.
  - A mocked LLM response whose `proposed_page` embeds the note's own `domain` as a trailing segment (e.g. `"tribes-leadership-{domain}"`) produces a slug with that segment stripped.
  - A mocked LLM response with `proposed_page: "none"` and a usable `note.title` falls back to a title-derived slug (existing behavior, now routed through `slug_utils.is_placeholder`).
  - A mocked LLM response with `proposed_page: "none"` and an empty/unusable `note.title` raises `ValueError` (existing behavior — must still hold after the refactor).
  These tests will fail until T009–T011 are done.

### Implementation for User Story 1

- [X] T009 [US1] In `src/ollama_agent.py`, remove the local `_slugify()` function and the local `_INVALID_SLUGS` set; add `from slug_utils import slugify, is_placeholder, strip_domain_suffix` and update `generate_proposal()` (currently `src/ollama_agent.py:236-242, 258`) to call `slugify()`/`is_placeholder()` in place of the removed local versions, preserving the existing LLM-slug → title-fallback → raise chain.
- [X] T010 [US1] In `src/ollama_agent.py::generate_proposal()`, immediately after computing `proposed_page` (and before the `is_placeholder` re-check), apply `proposed_page = strip_domain_suffix(proposed_page, domain)` so an LLM-produced domain-name-in-slug is corrected without needing a rename.
- [X] T011 [US1] Tighten `PROPOSAL_PROMPT` in `src/ollama_agent.py`: add an explicit line such as "Do not append the domain name to the slug" and strengthen the existing slug rule ("must be 1–4 words...") to also say the slug must name the concept itself, not restate the note's own instructional or prompt-like phrasing.
- [X] T012 [US1] Run `pytest tests/unit/test_ollama_agent.py -v` and confirm all tests pass.

**Checkpoint**: User Story 1 is fully functional and independently testable — this alone is shippable as the MVP (fixes the bug going forward even before any retroactive cleanup runs).

---

## Phase 4: User Story 2 - Existing Wiki Pages Are Re-Slugged (Priority: P2)

**Goal**: A batch tool re-evaluates every existing wiki page (excluding `domains/queries/`), regenerates a concept-based slug for the ones matching a known bad pattern, and applies the rename atomically across the wiki files, the database, and the vector store — safely resumable if interrupted.

**Independent Test**: Run the migration over the live wiki and confirm every page previously identified as having a bad slug (truncated, sentence-like, artifact-laden, or domain-suffix-duplicated) now has a concept-based slug, while pages with already-good slugs are left untouched.

### Tests for User Story 2

- [X] T013 [P] [US2] Write unit tests in `tests/unit/test_slug_migrator.py` for `DB.rename_wiki_page()`, using the `DB(str(tmp_path / "test.sqlite"))` + `init_schema()` fixture pattern from `tests/unit/test_review_undo.py`: after inserting notes with `wiki_page="old-slug"`, calling `db.rename_wiki_page("old-slug", "new-slug")` repoints all of them and leaves unrelated notes untouched. This will fail until T015 is done.
- [X] T014 [P] [US2] In the same `tests/unit/test_slug_migrator.py`, using a `tmp_path`-based fake wiki directory (a couple of `domains/<domain>/*.md` files with front matter, plus one under `domains/queries/`) and `unittest.mock.patch` for the Ollama call and the vector store, write tests for the migration engine covering:
  - The heuristic scan flags a 40-character slug, a slug with more than 4 words, and a slug containing `--`, but leaves a short good slug (e.g. `antifragilidade`) untouched.
  - A page under `domains/queries/` is never flagged or scanned.
  - Two candidates in the same domain that would regenerate to the same slug resolve to distinct slugs (or, if unresolvable, both end up with `status == "collision"`), and neither silently overwrites the other.
  - A page whose current slug already appears as a rename target in a fake `git log` (mocked) is skipped on a second run.
  - `_apply_candidate()` calls `wiki_store.rename_wiki_page`, then `db.rename_wiki_page`, then the vector store's `delete_embedding`/`upsert` pair, in that order, and that a failure in one of them sets `status="error"` with a message without raising out of the batch.
  These tests will fail until T016–T020 are done.

### Implementation for User Story 2

- [X] T015 [P] [US2] Add `DB.rename_wiki_page(self, old_slug: str, new_slug: str) -> None` to `src/db.py` (near the existing `clear_wiki_page` method): `UPDATE notes SET wiki_page=?, modified_at=? WHERE wiki_page=?`, per `data-model.md`.
- [X] T016 [US2] In `src/slug_migrator.py`, define the `MigrationCandidate` dataclass (`domain: str`, `old_slug: str`, `new_slug: Optional[str]`, `reasons: list[str]`, `status: str`, `error: Optional[str]`) and implement `_flag_candidates() -> list[MigrationCandidate]`: iterate `wiki_store.list_all_pages()`, skip any page whose domain directory is `queries`, and flag a page (recording which `reasons` matched) when `len(slug) >= 40`, the slug has more than 4 hyphen-separated words, the slug contains `--`, or the slug ends with `-{own domain}`.
- [X] T017 [US2] Implement `_already_migrated_slugs() -> set[str]` in `src/slug_migrator.py`: run `git -C <wiki_root> log --oneline`, parse lines matching the `rename: <old> → <new>` format produced by `wiki_store.rename_wiki_page()`, and return the set of `<new>` values; have `_flag_candidates()` (T016) exclude any page whose current slug is already in this set.
- [X] T018 [US2] Implement `_regenerate_slug(candidate: MigrationCandidate, page_content: str) -> str` in `src/slug_migrator.py`: build a single-page-scoped prompt (title/heading + body only, no domain index) and call `ollama_agent._call_ollama()` (imported directly, matching how `review_cli.py` already imports private helpers from `wiki_store`), then post-process the result through `slug_utils.slugify()`, `slug_utils.is_placeholder()` (falling back to a title-derived slug on failure, same chain as `generate_proposal`), and `slug_utils.strip_domain_suffix()`.
- [X] T019 [US2] Implement `_resolve_collisions(candidates: list[MigrationCandidate]) -> None` in `src/slug_migrator.py`: group candidates by domain; when two candidates in the same domain share a `new_slug` (or a `new_slug` collides with an existing unflagged page's slug), append a second distinguishing word drawn from the losing candidate's own title and re-check; if still colliding, set that candidate's `status = "collision"` and leave `new_slug` as the unresolved value rather than guessing.
- [X] T020 [US2] Implement `_apply_candidate(candidate: MigrationCandidate, dry_run: bool) -> None` in `src/slug_migrator.py`: if `dry_run` or `candidate.status == "collision"`, do nothing but set the reporting status; otherwise call `wiki_store.rename_wiki_page(candidate.domain, candidate.old_slug, candidate.new_slug)`, then `db.rename_wiki_page(candidate.old_slug, candidate.new_slug)`, then `vector_store.get_vector_store().delete_embedding(candidate.old_slug, candidate.domain)` and `.upsert(candidate.new_slug, page_content, candidate.domain, language)` — wrap each stage so a failure sets `candidate.status = "error"` and `candidate.error = str(e)` without aborting the rest of the batch; on failure, look up a linked note via `db.get_notes_by_wiki_page(candidate.old_slug)` and call `db.log_error()` against it if one exists, otherwise rely on the CLI summary alone (per Constitution Principle V, `errors.note_id` is `NOT NULL`).
- [X] T021 [US2] Implement `cmd_apply(args)` and wire the `apply` subparser (`--path`, `--dry-run`) into the `main()` block created in T002, following `contracts/cli.md`: scan/flag/regenerate/resolve as above, call `_apply_candidate()` for each resolved candidate, print a per-page `OK`/`error`/`needs-manual-review` line, and a final summary line (`Summary: N renamed, N error, N needs-manual-review, N unchanged.`).
- [X] T022 [US2] Run `pytest tests/unit/test_slug_migrator.py -v` and confirm all tests from T013–T014 pass.

**Checkpoint**: User Story 2 is fully functional — `python src/slug_migrator.py apply` (with or without `--dry-run`) safely re-slugs the existing wiki, keeping the wiki files, the database, and the vector store consistent.

---

## Phase 5: User Story 3 - Preview Before Committing to a Mass Rename (Priority: P3)

**Goal**: A dedicated read-only `detect` command shows exactly what US2's `apply` would do, with zero writes, so the mass rename can be reviewed first.

**Independent Test**: Run the migration in preview mode and confirm a report is produced showing old slug → new slug → reason for every page, with zero files, database rows, or vector store entries modified.

### Tests for User Story 3

- [X] T023 [P] [US3] Write unit tests in `tests/unit/test_slug_migrator.py` for `cmd_detect`: using the same fake-wiki fixture as US2, mock `wiki_store.rename_wiki_page`, `db.rename_wiki_page`, and the vector store's `delete_embedding`/`upsert`, run `cmd_detect`, and assert none of those mocks were ever called while the printed report still lists every flagged page's `old_slug`, `new_slug`, and `reasons`. This will fail until T024 is done.

### Implementation for User Story 3

- [X] T024 [US3] Implement `cmd_detect(args)` and wire the `detect` subparser (`--path`) into `main()` in `src/slug_migrator.py`, reusing `_flag_candidates()`, `_regenerate_slug()`, and `_resolve_collisions()` from US2 but never calling `_apply_candidate()`; print the same old→new/reason report format shown in `contracts/cli.md`, ending with a count of how many would be renamed vs. flagged `needs-manual-review`.
- [X] T025 [US3] Run `pytest tests/unit/test_slug_migrator.py -v` and confirm all tests (US2 + US3) pass.

**Checkpoint**: All three user stories are independently functional. `detect` and `apply` together give a safe preview-then-commit workflow for the full retroactive migration.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validate against the real wiki and bring the docs in line with the new tooling.

- [X] T026 [P] Run `uv run python src/slug_migrator.py detect` against the real `wiki/` directory and manually confirm the known bad examples from `spec.md` (e.g. a page matching the `sprint-how-to-solve-big-problems-and-tes`-style 40-char truncation, and a page matching the `ciencia-e-fe---a-particula-de-deus`-style `--` artifact) are flagged with sensible proposed replacements, and that no `domains/queries/` page appears in the report.
- [X] T027 Execute `quickstart.md` end-to-end against the real wiki: preview → `apply --dry-run` → `apply` → verify cross-links/DB/ChromaDB consistency via the commands listed there → confirm re-running `detect` reports 0 of the just-migrated pages as newly flagged.
- [X] T028 [P] Update `RUNBOOK.md`'s "Rename a wiki page slug" section (currently documents the fully manual `wiki_store.py rename` + hand-run `sqlite3 UPDATE` + a `vector_store.py --reindex-slug` flag that does not actually exist in the codebase) to add a new subsection documenting `uv run python src/slug_migrator.py detect` / `apply` for bulk quality-based re-slugging, keeping the existing manual `wiki_store.py rename` command documented separately for one-off, non-quality-driven renames.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup (needs `slug_utils.py` to exist) — BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational only. Fully independent of US2/US3.
- **User Story 2 (Phase 4)**: Depends on Foundational only (does not depend on US1 — `ollama_agent._call_ollama`, which it reuses, already exists today regardless of US1's changes).
- **User Story 3 (Phase 5)**: Depends on US2 (Phase 4) — `cmd_detect` reuses `_flag_candidates`/`_regenerate_slug`/`_resolve_collisions` built in US2.
- **Polish (Phase 6)**: Depends on all three user stories being complete.

### User Story Dependencies

- **US1 (P1)**: No dependency on US2 or US3 — can ship alone as the MVP.
- **US2 (P2)**: No dependency on US1. Depends only on Foundational.
- **US3 (P3)**: Depends on US2's engine functions (`_flag_candidates`, `_regenerate_slug`, `_resolve_collisions`) — cannot be implemented first.

### Parallel Opportunities

- T001 and T002 (Setup) run in parallel — different files.
- T003 (Foundational tests) starts once Setup is done; T004–T006 then proceed sequentially (same file, `src/slug_utils.py`).
- Once Foundational (Phase 2) is complete, **US1 (Phase 3) and US2 (Phase 4) can be implemented fully in parallel** — they touch disjoint files (`ollama_agent.py`/`test_ollama_agent.py` vs. `db.py`/`slug_migrator.py`/`test_slug_migrator.py`).
- Within US2: T013 and T014 are both new test code in the same new file — write together; T015 (DB method, different file) can run in parallel with T016 (candidate scan); T017–T021 all edit `src/slug_migrator.py` and must be sequential.
- US3 (Phase 5) can only start once US2 (Phase 4) is complete.

---

## Parallel Example: Foundational + User Story 1

```bash
# After Setup (T001, T002):
Task: "Write unit tests in tests/unit/test_slug_utils.py for slugify/is_placeholder/strip_domain_suffix"  # T003

# After Foundational (T003-T007) completes, US1 and US2 can run as two parallel workstreams:
Task: "Write unit tests in tests/unit/test_ollama_agent.py for generate_proposal() slug handling"  # T008 (US1)
Task: "Write unit tests in tests/unit/test_slug_migrator.py for DB.rename_wiki_page()"              # T013 (US2)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (blocks everything)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Ingest a few notes with long/messy titles, confirm slugs are clean. This alone fixes the bug going forward.

### Incremental Delivery

1. Setup + Foundational → shared `slug_utils.py` ready
2. Add US1 → generation is fixed → MVP shippable
3. Add US2 → `apply` can retroactively clean up the existing ~627-page wiki
4. Add US3 → `detect` makes that cleanup safe to review before committing
5. Polish → validated against the real wiki, RUNBOOK updated

### Suggested Team Split (if parallelized)

- Developer A: Foundational (Phase 2) → US1 (Phase 3)
- Developer B: waits for Foundational → US2 (Phase 4) → US3 (Phase 5)

---

## Notes

- [P] tasks = different files, no dependencies on incomplete work.
- [Story] label maps every user-story-phase task to US1/US2/US3 for traceability; Setup, Foundational, and Polish tasks carry no story label by design.
- Tests are written before their corresponding implementation tasks in every phase (TDD ordering) — confirm each test file fails for the right reason (missing symbol) before implementing.
- Commit after each task or logical group, consistent with this repo's existing one-concern-per-commit history.
- Stop at either checkpoint (end of Phase 3, end of Phase 4) to validate and ship independently — US1 and US2 are already useful in isolation.
