"""
Batch ingest script for Second Brain v2.
Processes all .md files in data/raw/notion/ (or a given directory) through the
full pipeline: parse → dedup → classify → propose → queue for review.

Features:
- Skips files already in DB (resumable — safe to Ctrl-C and re-run)
- Processes up to --limit files per run (default: all)
- Shows a rich progress bar
- Pauses between batches for review if --batch-size is set
- Logs failures to stderr without stopping the run

Usage:
  python src/batch_ingest.py                      # process all notion notes
  python src/batch_ingest.py --limit 50           # process first 50 unprocessed
  python src/batch_ingest.py --batch-size 50      # pause every 50 for review
  python src/batch_ingest.py --dir data/raw/keep  # different source dir
  python src/batch_ingest.py --status             # show DB stats only
"""
import sys
import time
from pathlib import Path

import yaml
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

console = Console()


def _load_settings() -> dict:
    cfg_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


def show_status() -> None:
    """Print proposal and note stats from the DB."""
    from db import get_db
    db = get_db()

    with db._conn() as conn:
        proposal_rows = conn.execute("""
            SELECT n.domain,
                   COUNT(*) AS total,
                   SUM(CASE WHEN p.decision='approved'    THEN 1 ELSE 0 END) AS approved,
                   SUM(CASE WHEN p.decision='rejected'    THEN 1 ELSE 0 END) AS rejected,
                   SUM(CASE WHEN p.decision IS NULL       THEN 1 ELSE 0 END) AS pending,
                   ROUND(100.0 * SUM(CASE WHEN p.decision='rejected' THEN 1 ELSE 0 END)
                         / MAX(COUNT(*), 1), 1) AS rejection_pct
            FROM proposals p
            JOIN notes n ON n.id = p.note_id
            GROUP BY n.domain
            ORDER BY n.domain
        """).fetchall()

        note_rows = conn.execute("""
            SELECT status, COUNT(*) FROM notes GROUP BY status ORDER BY status
        """).fetchall()

    t1 = Table(title="Proposals by domain", show_lines=True)
    for col in ("domain", "total", "approved", "rejected", "pending", "rejection %"):
        t1.add_column(col)
    for row in proposal_rows:
        t1.add_row(*[str(v) for v in row])
    console.print(t1)

    t2 = Table(title="Notes by status")
    t2.add_column("status")
    t2.add_column("count")
    for row in note_rows:
        t2.add_row(*[str(v) for v in row])
    console.print(t2)


def _already_processed(file_path: Path, db) -> bool:
    """Return True if this file's notes are already in the DB.

    Kindle .txt files:
      - New format: source_path = file#book-slug#domain (two '#' chars)
      - Old format: source_path = file#book-slug       (one '#' char)
    If only old-format records exist, delete them and return False so the
    file is re-queued with the new multi-domain parser.
    """
    if file_path.suffix == ".txt":
        prefix = str(file_path.resolve()) + "#"
        notes = db.get_notes_by_path_prefix(prefix)
        if not notes:
            return False
        new_format = [n for n in notes if n.source_path.count("#") == 2]
        if new_format:
            return True
        # Only old-format records — migrate: delete them and re-ingest
        for n in notes:
            db.delete_note(n.id)
        return False
    note = db.get_note_by_path(str(file_path.resolve()))
    if note is None:
        return False
    from models import NoteStatus
    return note.status not in (NoteStatus.PENDING, None)


def _process_one(file_path: Path) -> str:
    """
    Run one file through the pipeline.
    Returns 'ok', 'skipped', or 'error:<msg>'.
    """
    from watcher import _process_job
    from models import IngestJob
    try:
        _process_job(IngestJob(path=str(file_path.resolve()), event="create"))
        return "ok"
    except Exception as e:
        return f"error:{e}"


def _source_glob(source_dir: Path) -> list[Path]:
    """Return the right file list for each raw source directory."""
    name = source_dir.name
    if name == "keep":
        return sorted(source_dir.glob("*.json"))
    if name == "kindle":
        return sorted(source_dir.glob("*.txt"))
    if name == "evernote":
        return sorted(
            f for f in source_dir.rglob("*.html")
            if not f.name.startswith(".")
            and not any(p.endswith(" files") or p.endswith("_files") for p in f.parts)
        )
    if name in ("gdrive", "obsidian"):
        return sorted(
            f for f in source_dir.rglob("*.md")
            if not f.name.startswith(".")
            and ".obsidian" not in f.parts
            and not any(p.endswith("_files") or p == "_resources" for p in f.parts)
            and f.stat().st_size > 0
        )
    if name == "articles":
        return sorted(
            f for f in source_dir.glob("*.md")
            if not f.name.startswith(".") and f.stat().st_size > 0
        )
    if name == "papers":
        return sorted(
            f for f in source_dir.glob("*.pdf")
            if not f.name.startswith(".") and f.stat().st_size > 0
        )
    return sorted(source_dir.glob("*.md"))  # notion (default)


def run_batch(
    source_dir: Path,
    limit: int | None,
    batch_size: int | None,
) -> None:
    from db import get_db
    db = get_db()

    files = _source_glob(source_dir)
    if not files:
        ext_map = {"keep": "*.json", "kindle": "*.txt", "evernote": "*.html"}
        ext = ext_map.get(source_dir.name, "*.md")
        console.print(f"[yellow]No {ext} files found in {source_dir}[/yellow]")
        return

    # Filter already processed
    pending_files = [f for f in files if not _already_processed(f, db)]

    if not pending_files:
        console.print("[green]All notes already processed. Nothing to do.[/green]")
        show_status()
        return

    if limit:
        pending_files = pending_files[:limit]

    total = len(pending_files)
    console.print(
        f"\n[bold]Batch ingest[/bold]: {total} notes to process "
        f"({'all' if limit is None else f'limit={limit}'}) "
        f"from [cyan]{source_dir}[/cyan]\n"
    )

    ok = skipped = errors = 0
    batch_num = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("Processing notes…", total=total)

        for i, file_path in enumerate(pending_files):
            progress.update(task, description=f"[cyan]{file_path.name[:55]}[/cyan]")

            result = _process_one(file_path)
            if result == "ok":
                ok += 1
            elif result == "skipped":
                skipped += 1
            else:
                errors += 1
                console.print(f"\n[red][ERROR][/red] {file_path.name}: {result[6:]}")

            progress.advance(task)

            # Pause between batches
            if batch_size and (i + 1) % batch_size == 0 and (i + 1) < total:
                batch_num += 1
                progress.stop()
                console.print(
                    f"\n[bold yellow]── Batch {batch_num} complete "
                    f"({i + 1}/{total} notes) ──[/bold yellow]\n"
                    "Run the review CLI now:\n"
                    "  [bold]uv run python src/review_cli.py[/bold]\n"
                )
                console.input("Press [bold]Enter[/bold] to continue with the next batch… ")
                progress.start()

    console.print(
        f"\n[bold green]Done.[/bold green] "
        f"ok={ok}  skipped={skipped}  errors={errors}\n"
    )
    show_status()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cfg = _load_settings()
    raw_root = Path(__file__).parent.parent / cfg["paths"]["raw_data"]

    args = sys.argv[1:]

    if "--status" in args:
        show_status()
        sys.exit(0)

    source_dir = raw_root / "notion"
    limit = None
    batch_size = None

    if "--dir" in args:
        idx = args.index("--dir")
        source_dir = Path(args[idx + 1])

    if "--limit" in args:
        idx = args.index("--limit")
        limit = int(args[idx + 1])

    if "--batch-size" in args:
        idx = args.index("--batch-size")
        batch_size = int(args[idx + 1])

    run_batch(source_dir, limit=limit, batch_size=batch_size)
