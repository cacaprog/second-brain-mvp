"""
Human review gate for Second Brain v2.
Presents queued proposals as colored diffs and captures keyboard decisions.
Target: under 10 seconds per unambiguous proposal.

Usage:
  python src/review_cli.py [--domain DOMAIN]
  python src/review_cli.py --batch-log [--since YYYY-MM-DD]
  python src/review_cli.py --errors
"""
import json
import os
import subprocess
import sys
from dotenv import load_dotenv

load_dotenv()
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from models import NoteRecord, NoteStatus, Proposal

console = Console()


def _load_settings() -> dict:
    cfg_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


def _get_keystroke() -> str:
    """Read a single keypress without echoing (Unix only)."""
    import tty
    import termios
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch


def _key(k: str) -> str:
    """Return a Rich-formatted key hint: cyan bold [k]."""
    return f"[bold cyan]\\[{k}][/bold cyan]"


def _print_action_bar() -> None:
    """Print the two-row keyboard shortcut bar below a proposal."""
    console.print(Rule(style="dim"))
    console.print(
        f"{_key('a')} approve  "
        f"{_key('e')} edit  "
        f"{_key('f')} fast-track  "
        f"{_key('r')} reject  "
        f"{_key('u')} undo  "
        f"{_key('?')} help"
    )
    console.print(
        f"{_key('s')} skip  "
        f"{_key('d')} domain  "
        f"{_key('b')} batch-rest  "
        f"{_key('q')} quit"
    )


def _render_diff(proposal: Proposal, note: NoteRecord, existing: Optional[str]) -> None:
    """Render the proposal as a colored diff panel."""
    from wiki_store import render_wiki_page

    proposed_content = render_wiki_page(
        existing_content=existing,
        slug=proposal.proposed_page,
        domain=note.domain or "personal",
        summary=proposal.summary,
        source_path=note.source_path,
        links=proposal.proposed_links,
        languages=[note.language] if note.language != "unknown" else [],
        confidence=proposal.confidence,
        edited_content=proposal.edited_content,
    )

    flag = "NEW PAGE" if proposal.is_new_page else ("LINK ONLY" if proposal.link_only else "UPDATE")
    rich_label = "  [bold green]RICH NOTE[/bold green]" if note.note_type == "rich_note" else ""
    console.print(Rule())
    console.print(
        f"[bold cyan]Proposal[/bold cyan]  "
        f"[bold]{proposal.proposed_page}[/bold]  "
        f"[dim]{note.domain}[/dim]  "
        f"[yellow]conf: {proposal.confidence:.2f}[/yellow]  "
        f"[magenta]{flag}[/magenta]"
        f"{rich_label}"
    )
    console.print(
        f"[dim]Note: {Path(note.source_path).name}  lang={note.language}  "
        f"words={note.word_count}[/dim]"
    )

    if proposal.flag_contradiction:
        console.print("[red bold]⚠ Contradiction flagged[/red bold]")
    if proposal.flag_duplicate:
        console.print("[yellow bold]⚠ Duplicate flagged[/yellow bold]")
    if proposal.proposed_links:
        console.print(f"[dim]Links: {', '.join(f'[[{l}]]' for l in proposal.proposed_links)}[/dim]")

    console.print()

    if existing:
        # Show diff-style output
        existing_lines = existing.splitlines()
        new_lines = proposed_content.splitlines()
        _show_diff(existing_lines, new_lines)
    else:
        diff_text = Text()
        for line in proposed_content.splitlines():
            diff_text.append(f"+ {line}\n", style="green")
        console.print(diff_text)

    console.print()
    _print_action_bar()


def _show_diff(old_lines: list[str], new_lines: list[str]) -> None:
    import difflib
    diff = list(difflib.unified_diff(old_lines, new_lines, lineterm=""))
    if not diff:
        console.print("[dim](no changes)[/dim]")
        return
    diff_text = Text()
    for line in diff[2:]:  # skip the ---/+++ header lines
        if line.startswith("+"):
            diff_text.append(line + "\n", style="green")
        elif line.startswith("-"):
            diff_text.append(line + "\n", style="red")
        else:
            diff_text.append(line + "\n", style="dim")
    console.print(diff_text)


def _open_editor(initial_content: str) -> str:
    """Write content to a temp file, open $EDITOR, return saved content."""
    import tempfile
    editor = os.environ.get("EDITOR", "nano")
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False, encoding="utf-8") as f:
        f.write(initial_content)
        tmp_path = f.name
    subprocess.run([editor, tmp_path])
    content = Path(tmp_path).read_text(encoding="utf-8")
    Path(tmp_path).unlink(missing_ok=True)
    return content


def _handle_proposal(
    proposal: Proposal,
    note: NoteRecord,
    skip_queue: list,
    undo_stack: list,
    restored: list,
) -> Optional[str]:
    """
    Display proposal and wait for keypress.
    Returns: 'approved' | 'rejected' | 'skipped' | 'batch' | 'quit' | 'undo'
    undo_stack: mutable list of (Proposal, NoteRecord) pushed on each rejection.
    restored: output list — on undo, the restored Proposal is appended here for
              the caller (run_review) to re-insert into the active queue.
    """
    from wiki_store import read_wiki_page
    from db import get_db
    from commit import commit as do_commit, revert_commit

    db = get_db()
    existing = read_wiki_page(note.domain or "personal", proposal.proposed_page)

    _render_diff(proposal, note, existing)

    while True:
        key = _get_keystroke().lower()

        if key == "a":
            try:
                db.set_proposal_decision(proposal.id, "approved")
                db.set_note_status(note.id, NoteStatus.COMMITTING)
                do_commit(proposal, note)
                console.print("[green]✓ Approved and committed[/green]")
            except Exception as e:
                console.print(f"[red]✗ Commit failed: {e}[/red]")
            return "approved"

        elif key == "e":
            from wiki_store import render_wiki_page, _parse_front_matter
            # Use already-edited content as base if the user edits again
            base = proposal.edited_content or render_wiki_page(
                existing_content=existing,
                slug=proposal.proposed_page,
                domain=note.domain or "personal",
                summary=proposal.summary,
                source_path=note.source_path,
                links=proposal.proposed_links,
                languages=[note.language] if note.language != "unknown" else [],
                confidence=proposal.confidence,
            )
            edited = _open_editor(base)
            if not edited.strip():
                console.print("[yellow]Empty content — edit discarded[/yellow]")
                continue
            proposal.edited_content = edited

            # Sync slug if the user changed it in the front matter
            fm = _parse_front_matter(edited)
            if fm.get("slug") and fm["slug"] != proposal.proposed_page:
                proposal.proposed_page = fm["slug"]

            # Re-render so the user sees the edited version, not the original
            _render_diff(proposal, note, existing)
            console.print(
                f"[bold cyan]↑ Edited version above[/bold cyan] — "
                f"{_key('a')} approve  "
                f"{_key('e')} edit again  "
                f"{_key('r')} reject"
            )
            continue

        elif key == "f":
            try:
                db.set_proposal_decision(proposal.id, "fast_tracked")
                db.set_note_status(note.id, NoteStatus.COMMITTED)
                do_commit(proposal, note)
                console.print(f"[green]✓ Fast-tracked: {proposal.proposed_page}[/green]")
            except Exception as e:
                console.print(f"[red]✗ Fast-track commit failed: {e}[/red]")
            return "fast_tracked"

        elif key == "r":
            console.print("[yellow]Rejection reason: [/yellow]", end="")
            reason = input()
            db.set_proposal_decision(proposal.id, "rejected", rejection_reason=reason)
            db.set_note_status(note.id, NoteStatus.REJECTED)
            undo_stack.append((proposal, note))
            console.print("[red]✗ Rejected[/red]")
            return "rejected"

        elif key == "u":
            if not undo_stack:
                console.print("[dim]Nothing to undo[/dim]")
                continue
            prev_proposal, prev_note = undo_stack.pop()
            try:
                db.undo_rejection(prev_proposal.id, prev_note.id)
                restored.append(prev_proposal)
                console.print("[yellow]↩ Rejection undone — proposal returned to queue[/yellow]")
            except Exception as e:
                console.print(f"[red]✗ Undo failed: {e}[/red]")
                undo_stack.append((prev_proposal, prev_note))
            return "undo"

        elif key == "s":
            skip_queue.append((proposal, note))
            console.print("[dim]Skipped — moved to end of queue[/dim]")
            return "skipped"

        elif key == "d":
            new_domain = _reassign_domain(proposal, note, db)
            if new_domain:
                # Re-render with the updated domain
                existing = read_wiki_page(note.domain or "personal", proposal.proposed_page)
                _render_diff(proposal, note, existing)
            continue

        elif key == "b":
            return "batch"

        elif key == "q":
            return "quit"

        elif key == "?":
            lines = [
                f"{_key('a')} Approve and commit",
                f"{_key('e')} Edit in $EDITOR then approve",
                f"{_key('f')} Fast-track this proposal (manual override)",
                f"{_key('r')} Reject with reason",
                f"{_key('u')} Undo last rejection (this session only)",
                f"{_key('s')} Skip — defer to end of session",
                f"{_key('d')} Reassign to a different domain",
                f"{_key('b')} Batch-approve all remaining fast-track proposals",
                f"{_key('q')} Quit session",
            ]
            console.print(Panel("\n".join(lines), title="Keybindings"))


def _load_known_domains() -> list[str]:
    cfg = _load_settings()
    domains_path = Path(__file__).parent.parent / cfg["domains"]["config_file"]
    import yaml as _yaml
    data = _yaml.safe_load(domains_path.read_text(encoding="utf-8"))
    return sorted(data.get("domains", {}).keys())


def _add_new_domain(domain_name: str) -> None:
    """Append a new domain entry to domains.yaml and create its wiki directory."""
    import yaml as _yaml
    cfg = _load_settings()
    domains_path = Path(__file__).parent.parent / cfg["domains"]["config_file"]
    data = _yaml.safe_load(domains_path.read_text(encoding="utf-8"))

    console.print(f"\nAdding new domain [bold]{domain_name}[/bold].")
    console.print("Enter seed terms (comma-separated, Portuguese/English mixed OK):")
    seeds_raw = input("Seeds: ").strip()
    seeds = [s.strip() for s in seeds_raw.split(",") if s.strip()]
    if not seeds:
        seeds = [domain_name]

    data["domains"][domain_name] = {
        "seeds": seeds,
        "max_pages": cfg["domains"]["max_pages_per_domain"],
    }
    domains_path.write_text(
        _yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    console.print(f"[green]✓ Added domain '{domain_name}' with {len(seeds)} seed term(s)[/green]")

    # Create wiki directory
    wiki_dir = Path(__file__).parent.parent / cfg["paths"]["wiki"] / "domains" / domain_name
    wiki_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[green]✓ Created {wiki_dir}[/green]")

    # Recompute centroids
    console.print("[dim]Recomputing domain centroids (this takes ~1 min)…[/dim]")
    import subprocess
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parent / "classifier.py"), "--precompute"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        console.print("[green]✓ Centroids recomputed[/green]")
    else:
        console.print(f"[yellow]⚠ Centroid recompute warning: {result.stderr.strip()}[/yellow]")


def _reassign_domain(proposal: "Proposal", note: "NoteRecord", db) -> Optional[str]:
    """
    Prompt for a new domain, update note + proposal in-place.
    Returns the new domain name, or None if cancelled.
    """
    known = _load_known_domains()
    console.print(f"\nKnown domains: [cyan]{', '.join(known)}[/cyan]")
    console.print("Enter new domain (existing name or a new one), or blank to cancel:")
    raw = input("Domain: ").strip().lower().replace(" ", "-")
    if not raw:
        return None

    if raw not in known:
        confirm = input(f"'{raw}' is a new domain. Add it? [y/N]: ").strip().lower()
        if confirm != "y":
            return None
        _add_new_domain(raw)

    # Update DB
    db.set_note_domain(note.id, raw, None)
    # Update in-memory objects so the re-render sees the change
    note.domain = raw
    note.secondary_domain = None
    console.print(f"[green]✓ Reassigned to domain '{raw}'[/green]\n")
    return raw


def run_review(domain: Optional[str] = None, note_type: Optional[str] = None) -> None:
    """Main review session loop."""
    from db import get_db
    from commit import commit as do_commit

    db = get_db()
    proposals = db.get_pending_proposals(domain=domain, note_type=note_type)

    if not proposals:
        console.print("[dim]No proposals pending review.[/dim]")
        return

    console.print(f"[bold]Review queue:[/bold] {len(proposals)} proposal(s)")
    skip_queue: list[tuple[Proposal, NoteRecord]] = []
    queue_items = list(proposals)

    undo_stack: list = []
    idx = 0
    while idx < len(queue_items):
        proposal = queue_items[idx]
        note = db.get_note(proposal.note_id)
        if not note:
            idx += 1
            continue

        console.print(f"\n[dim]Proposal {idx + 1}/{len(queue_items)}[/dim]")
        restored: list = []
        action = _handle_proposal(proposal, note, skip_queue, undo_stack, restored)

        if action == "quit":
            break
        elif action == "batch":
            _batch_approve_remaining(queue_items[idx:], db)
            break
        elif action == "undo" and restored:
            queue_items.insert(idx, restored[0])
        else:
            idx += 1

    # Process skipped items at the end
    if skip_queue:
        console.print(f"\n[dim]Processing {len(skip_queue)} skipped proposal(s)...[/dim]")
        for proposal, note in skip_queue:
            _handle_proposal(proposal, note, [], undo_stack, [])

    console.print("\n[bold]Review session complete.[/bold]")


def run_recover_rejected(days: int = 30) -> None:
    """List notes rejected in the last `days` days and allow selective restoration."""
    from db import get_db

    db = get_db()
    entries = db.get_rejected_notes(days)

    if not entries:
        console.print(f"[dim]No rejected notes in the last {days} days.[/dim]")
        return

    console.print(f"[bold]Rejected notes (last {days} days):[/bold] {len(entries)} note(s)\n")

    for i, (note, proposal_id, proposed_page, decided_at) in enumerate(entries):
        date_str = (decided_at or "")[:10]
        console.print(Rule())
        console.print(
            f"[{i + 1}/{len(entries)}] [bold]{note.title}[/bold]  "
            f"[dim]{note.domain}[/dim]  "
            f"rejected: {date_str}"
        )
        console.print(
            f"{_key('r')} recover  "
            f"{_key('n')} next  "
            f"{_key('q')} quit"
        )

        key = _get_keystroke().lower()
        if key == "r":
            try:
                db.undo_rejection(proposal_id, note.id)
                console.print("[green]✓ Recovered — will appear in next review session[/green]")
            except Exception as e:
                console.print(f"[red]✗ Recovery failed: {e}[/red]")
        elif key == "q":
            break

    console.print("\n[bold]Recovery complete.[/bold]")


def _batch_approve_remaining(remaining: list[Proposal], db) -> None:
    """Approve all fast-track-eligible proposals in the remaining queue without display."""
    from commit import commit as do_commit
    from models import NoteStatus

    count = 0
    for proposal in remaining:
        if not proposal.fast_track_eligible:
            continue
        note = db.get_note(proposal.note_id)
        if not note:
            continue
        try:
            db.set_proposal_decision(proposal.id, "fast_tracked")
            db.set_note_status(note.id, NoteStatus.COMMITTED)
            do_commit(proposal, note)
            console.print(f"[green]✓ Batch: {proposal.proposed_page}[/green]")
            count += 1
        except Exception as e:
            console.print(f"[red]✗ Batch commit failed for {proposal.proposed_page}: {e}[/red]")

    console.print(f"[dim]Batch approved {count} proposal(s).[/dim]")


def run_batch_log_review(since: Optional[str] = None) -> None:
    """Review the batch_log.jsonl of fast-tracked proposals."""
    cfg = _load_settings()
    log_path = Path(__file__).parent.parent / cfg["paths"]["batch_log"]

    if not log_path.exists():
        console.print("[dim]No batch log found.[/dim]")
        return

    entries = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line.strip())
            if since and entry.get("committed_at", "") < since:
                continue
            entries.append(entry)

    if not entries:
        console.print("[dim]No batch log entries to review.[/dim]")
        return

    console.print(f"[bold]Batch log review:[/bold] {len(entries)} fast-tracked proposal(s)\n")

    for i, entry in enumerate(entries):
        console.print(
            f"[{i+1}/{len(entries)}] [bold]{entry['slug']}[/bold]  "
            f"conf={entry['confidence']:.2f}  "
            f"model={entry['model']}  "
            f"[dim]{entry['committed_at'][:10]}[/dim]"
        )
        console.print("[bold][r][/bold]evert  [bold][n][/bold]ext  [bold][q][/bold]uit")

        key = _get_keystroke().lower()
        if key == "r":
            try:
                from commit import revert_commit
                revert_commit(entry["proposal_id"])
                console.print(f"[red]↩ Reverted {entry['slug']}[/red]")
            except Exception as e:
                console.print(f"[red]✗ Revert failed: {e}[/red]")
        elif key == "q":
            break
        else:
            continue

    console.print("\n[bold]Batch log review complete.[/bold]")


def run_errors_review() -> None:
    """Review notes stuck in COMMIT_FAILED / errors table.
    Keybindings: r = re-queue for fresh proposal, d = dismiss, q = quit.
    """
    from db import get_db
    from models import NoteStatus

    db = get_db()
    errors = db.get_unresolved_errors()

    if not errors:
        console.print("[dim]No unresolved pipeline errors.[/dim]")
        return

    console.print(f"[bold]Error queue:[/bold] {len(errors)} unresolved failure(s)\n")

    for i, err in enumerate(errors):
        note = db.get_note(err.note_id)
        source_name = Path(note.source_path).name if note else err.note_id[:16]
        console.print(Rule())
        console.print(
            f"[{i+1}/{len(errors)}] [bold red]{err.stage}[/bold red]  "
            f"[bold]{source_name}[/bold]  "
            f"[dim]{err.occurred_at[:10]}[/dim]"
        )
        console.print(f"[yellow]{err.error_message}[/yellow]")
        console.print(
            "[bold][r][/bold]e-queue  "
            "[bold][d][/bold]ismiss  "
            "[bold][q][/bold]uit"
        )

        key = _get_keystroke().lower()
        if key == "r":
            with db._conn() as conn:
                conn.execute(
                    "UPDATE notes SET status=? WHERE id=?",
                    (NoteStatus.PENDING, err.note_id),
                )
                conn.execute(
                    "UPDATE errors SET resolved=1 WHERE id=?",
                    (err.id,),
                )
            console.print(f"[green]✓ Re-queued — run watcher --once on the source file to reprocess[/green]")
        elif key == "d":
            with db._conn() as conn:
                conn.execute("UPDATE errors SET resolved=1 WHERE id=?", (err.id,))
            console.print("[dim]Dismissed[/dim]")
        elif key == "q":
            break

    console.print("\n[bold]Error review complete.[/bold]")


if __name__ == "__main__":
    if "--batch-log" in sys.argv:
        since_arg = None
        if "--since" in sys.argv:
            idx = sys.argv.index("--since")
            if idx + 1 < len(sys.argv):
                since_arg = sys.argv[idx + 1]
        run_batch_log_review(since=since_arg)
    elif "--errors" in sys.argv:
        run_errors_review()
    elif "--recover-rejected" in sys.argv:
        days_arg = 30
        if "--days" in sys.argv:
            idx = sys.argv.index("--days")
            if idx + 1 < len(sys.argv):
                try:
                    days_arg = int(sys.argv[idx + 1])
                except ValueError:
                    pass
        run_recover_rejected(days=days_arg)
    else:
        domain_arg = None
        if "--domain" in sys.argv:
            idx = sys.argv.index("--domain")
            if idx + 1 < len(sys.argv):
                domain_arg = sys.argv[idx + 1]
        note_type_arg = None
        if "--type" in sys.argv:
            idx = sys.argv.index("--type")
            if idx + 1 < len(sys.argv):
                note_type_arg = sys.argv[idx + 1]
        run_review(domain=domain_arg, note_type=note_type_arg)
