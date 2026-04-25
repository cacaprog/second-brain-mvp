# Feature Specification: Undo Accidental Reject in Review

**Feature Branch**: `004-undo-reject`
**Created**: 2026-04-24
**Status**: Draft
**Input**: User description: "I want to introduce option after type accidentally 'R' - reject - when review process. Many notes were rejected without my intention"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Undo Last Rejection Within the Same Session (Priority: P1) 🎯 MVP

Cairo is in a review session, presses `r` by mistake on a note he intended to approve, then immediately realizes the error. He can press `u` to undo the last rejection and return the note to the front of the review queue, as if the rejection never happened.

**Why this priority**: This is the core pain point — accidental rejections happen during fast-paced review sessions. The undo should be instant, require no typing, and work within the same uninterrupted session. One `u` keypress should fully reverse the mistake.

**Independent Test**: Open a review session with at least 2 pending proposals. Press `r` on the first, enter a reason. Immediately press `u`. Verify that the previously rejected proposal reappears as the next item in the queue with its status restored to pending.

**Acceptance Scenarios**:

1. **Given** a proposal just rejected in this session, **When** the user presses `u`, **Then** the proposal's rejection is reversed and it reappears as the next item to review.
2. **Given** a proposal just rejected in this session, **When** the user presses `u`, **Then** the rejection reason entered is discarded and the note's status is restored to awaiting review.
3. **Given** no rejection has been made yet in this session, **When** the user presses `u`, **Then** the system shows "Nothing to undo" and remains on the current proposal.
4. **Given** the user has rejected two proposals in a row, **When** the user presses `u` twice, **Then** both rejections are undone in reverse order (most recent first).
5. **Given** a proposal that was approved (not rejected), **When** the user presses `u`, **Then** only rejections are undone — approvals are not affected.

---

### User Story 2 - Recover Recently Rejected Notes from a Past Session (Priority: P2)

Cairo accidentally rejected several notes yesterday before noticing the mistake. He runs the review tool with a `--recover-rejected` flag to list notes rejected in recent sessions and selectively re-queue them for review.

**Why this priority**: The in-session undo only works if the user notices the mistake before quitting. If the user quits first and returns later, they need a way to find and recover rejected notes from a previous session.

**Independent Test**: Reject 3 notes and quit the review session. Re-launch the tool with `--recover-rejected`. Verify all 3 rejected notes appear in a recoverable list and that selecting one restores it to the pending review queue.

**Acceptance Scenarios**:

1. **Given** notes were rejected in a previous session, **When** the user runs the tool with `--recover-rejected`, **Then** a list of rejected notes is shown with title, domain, and rejection date.
2. **Given** the rejected notes list is shown, **When** the user selects a note to recover, **Then** the note's status is changed back to pending and it enters the review queue.
3. **Given** the rejected notes list is shown, **When** the user presses `q`, **Then** the list is dismissed without changes.
4. **Given** no notes have been rejected, **When** the user runs `--recover-rejected`, **Then** the system shows "No rejected notes to recover."
5. **Given** a note was rejected more than 30 days ago, **When** the user runs `--recover-rejected`, **Then** the note does not appear in the default list (old rejections are considered intentional).

---

### Edge Cases

- Pressing `u` at the start of a session (before any action): shows "Nothing to undo" — no crash.
- Undo after an edit-then-reject sequence: the note returns to pending, the edited content is discarded along with the rejection.
- Multiple rapid `r` presses on the same note (e.g., key repeat): only one rejection is recorded; one `u` reverses it.
- Rejecting the last note in the queue then pressing `u`: the note reappears and the session continues normally rather than ending.
- A note recovered via `--recover-rejected` is re-queued without a new proposal being generated — it goes back into the existing proposal queue with its existing proposal.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The review interface MUST accept a `u` keypress at any point during an active session to undo the most recent rejection.
- **FR-002**: Undoing a rejection MUST fully reverse the note's status to its pre-rejection state (pending review) and remove the rejection reason.
- **FR-003**: The undo history MUST cover all rejections made within the current session, with undo applied in reverse chronological order (most recent first).
- **FR-004**: When no rejection is available to undo, pressing `u` MUST display a "Nothing to undo" message without error.
- **FR-005**: The review tool MUST support a `--recover-rejected` mode that lists all notes rejected in recent sessions (within the last 30 days by default).
- **FR-006**: In `--recover-rejected` mode, the user MUST be able to select individual notes to restore to pending review status.
- **FR-007**: All existing review keybindings (`a`, `e`, `f`, `r`, `s`, `d`, `b`, `q`) MUST remain unchanged — the `u` key is additive only.
- **FR-008**: The `u` key MUST be listed in the `?` help panel.

### Key Entities

- **Rejection record**: A note's rejection decision, rejection reason, and the timestamp of rejection — all reversible within the constraints above.
- **Undo stack**: An ordered, in-memory record of rejections made during the current session, used to drive the undo operation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of rejections made within the current session can be undone before the session ends — zero data loss from accidental in-session rejections.
- **SC-002**: The undo operation completes in under 1 second and the recovered note appears as the next item without requiring the user to navigate manually.
- **SC-003**: Notes rejected up to 30 days ago are recoverable via `--recover-rejected` — zero permanently lost notes due to accidental rejection within that window.
- **SC-004**: Zero regressions to existing keybindings — all prior review actions (`a`, `e`, `f`, `r`, `s`, `d`, `b`, `q`) behave identically after this change.

## Assumptions

- The undo stack is in-memory only — it does not persist across sessions. Closing and restarting the tool clears the undo history (the `--recover-rejected` flag serves the cross-session case).
- The `--recover-rejected` list defaults to the last 30 days. This window covers realistic accident recovery without surfacing intentional old rejections.
- A recovered note returns to the existing proposal queue with the proposal that was already generated — no new LLM call is required.
- The `u` key was not previously assigned to any function in the review CLI.
- Undo applies only to rejections, not to approvals or fast-track actions (approvals write to the wiki and are harder to reverse safely — that is a separate concern).
