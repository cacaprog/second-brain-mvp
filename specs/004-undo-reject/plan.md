# Implementation Plan: Undo Accidental Reject in Review

**Branch**: `004-undo-reject` | **Date**: 2026-04-24 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-undo-reject/spec.md`

## Summary

Add a `u` (undo) keybinding to the review CLI that reverses the most recent rejection within the current session, restoring the proposal to the front of the review queue. Also adds a `--recover-rejected` CLI mode for cross-session recovery of notes rejected within the last 30 days. Both operations work entirely within the existing SQLite schema — no new tables, no new dependencies.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: rich (existing — console output), sqlite3 stdlib (existing — undo DB writes); no new packages
**Storage**: SQLite `db/brain.sqlite` — `proposals` table (`decision`, `rejection_reason` columns) + `notes` table (`status` column)
**Testing**: pytest
**Target Platform**: Linux CLI (single-user, single-threaded interactive session)
**Project Type**: CLI tool — modification to `src/review_cli.py` only
**Performance Goals**: Undo completes in < 1 second (SC-002); `--recover-rejected` list renders in < 2 seconds for up to 1,000 rejected notes
**Constraints**: No new Python dependencies; no new DB tables or columns; all existing keybindings unchanged
**Scale/Scope**: Single user, local; corpus of ~500–2,000 notes; undo stack bounded by session length (typically ≤ 50 rejections per session)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I — Human Gate | ✅ PASS | Feature STRENGTHENS the gate: accidental rejections are now reversible. No LLM output bypasses human review. |
| II — Wiki-First | ✅ PASS | No changes to ChromaDB or wiki indexing. |
| III — Domain-Bounded Context | ✅ PASS | No Ollama calls involved. |
| IV — Immutable Raw Sources | ✅ PASS | `data/raw/` untouched. |
| V — Audit Trail | ✅ PASS | Undo sets `decision=NULL, rejection_reason=NULL` on `proposals` and `status=classified` on `notes`. DB remains the single source of truth. |
| VI — Local and Private | ✅ PASS | Purely local SQLite writes. |
| VII — Fail Visibly | ✅ PASS | DB errors during undo are caught and printed; no silent failures. |

**No violations. Pre-research gate: PASSED.**

## Project Structure

### Documentation (this feature)

```text
specs/004-undo-reject/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/           ← Phase 1 output (keybinding contract)
└── tasks.md             ← Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
src/
└── review_cli.py        ← only file modified (undo stack + recover mode)

tests/
└── unit/
    └── test_review_undo.py   ← new unit tests for undo logic
```

**Structure Decision**: Single-file modification. `review_cli.py` houses the entire review session; the undo stack is an in-memory list passed into `_handle_proposal()`. No new modules, no new abstractions beyond what the task requires.
