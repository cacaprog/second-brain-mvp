"""
Two-tier wiki integrity lint for Second Brain v2.

Tier 1 — Structural (Python only, no LLM, runs daily):
  Checks orphan pages, broken links, stale pages, deleted-source orphans,
  failed commits, domain over-limit, page size ceiling.

Tier 2 — Semantic (Ollama, monthly, recent pages only):
  Flags internal contradictions and unsupported claims within each page.

Usage:
  python src/lint.py --tier structural [--domain DOMAIN]
  python src/lint.py --tier semantic --domain DOMAIN
  python src/lint.py --after-commits N
"""
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import yaml


def _load_settings() -> dict:
    cfg_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


def _load_domains() -> dict:
    cfg = _load_settings()
    domains_path = Path(__file__).parent.parent / cfg["domains"]["config_file"]
    with open(domains_path) as f:
        return yaml.safe_load(f)["domains"]


def _wiki_root() -> Path:
    cfg = _load_settings()
    return Path(__file__).parent.parent / cfg["paths"]["wiki"]


def _parse_front_matter(content: str) -> dict:
    import re
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}


def _word_count(content: str) -> int:
    import re
    body_match = re.search(r"^---\n.*?^---\n(.*)", content, re.DOTALL | re.MULTILINE)
    text = body_match.group(1) if body_match else content
    return len(text.split())


SEMANTIC_LINT_PROMPT = """Read the following wiki page and identify:
1. internal_contradictions: statements within this page that directly contradict
   each other (logical contradiction only — not differing perspectives or views).
2. unsupported_claims: assertions with no source reference in the Sources section.

Scope: intra-page only. Do not compare against other pages.
Return JSON only, no preamble, no markdown fences.

Page: {slug}
Content:
{body}

{{
  "internal_contradictions": [
    {{"statement_a": "...", "statement_b": "..."}}
  ],
  "unsupported_claims": ["..."]
}}"""


# ---------------------------------------------------------------------------
# Structural lint
# ---------------------------------------------------------------------------

def run_structural(domain_filter: Optional[str] = None) -> dict:
    """Run structural lint. Returns report dict and writes JSON to wiki/lint/."""
    from db import get_db

    cfg = _load_settings()
    db = get_db()
    wiki = _wiki_root()
    domains_cfg = _load_domains()
    stale_days = cfg["lint"]["stale_days"]
    page_max_words = cfg["lint"]["page_max_words"]
    today = date.today()
    issues = []

    # Collect all pages
    all_pages = []
    for page in wiki.glob("domains/*/*.md"):
        if page.name == "index.md":
            continue
        if domain_filter and page.parent.name != domain_filter:
            continue
        all_pages.append(page)

    all_slugs = {p.stem for p in all_pages}

    # Build inbound link map from cross-links.md
    inbound: dict[str, int] = {s: 0 for s in all_slugs}
    cl_path = wiki / "cross-links.md"
    if cl_path.exists():
        for line in cl_path.read_text(encoding="utf-8").splitlines():
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2 and not parts[0].startswith("-") and parts[0] != "Source":
                target = parts[1]
                if target in inbound:
                    inbound[target] = inbound.get(target, 0) + 1

    # Also count from page links[] front matter
    for page in all_pages:
        content = page.read_text(encoding="utf-8")
        meta = _parse_front_matter(content)
        for link in (meta.get("links") or []):
            if link in inbound:
                inbound[link] = inbound.get(link, 0) + 1

    # Check each page
    domains_checked = set()
    for page in all_pages:
        domain = page.parent.name
        slug = page.stem
        domains_checked.add(domain)
        content = page.read_text(encoding="utf-8")
        meta = _parse_front_matter(content)

        # Orphan page
        if inbound.get(slug, 0) == 0:
            issues.append({
                "type": "orphan_page", "severity": "warning",
                "slug": slug, "domain": domain,
                "detail": "No inbound links in cross-links.md or any wiki page",
            })

        # Missing concept (broken link)
        for link in (meta.get("links") or []):
            if link not in all_slugs:
                issues.append({
                    "type": "missing_concept", "severity": "error",
                    "slug": link, "domain": domain,
                    "referenced_from": slug,
                    "detail": f"Slug referenced in links[] but no corresponding file exists",
                })

        # Stale page
        updated_str = meta.get("updated", "")
        if updated_str:
            try:
                updated = date.fromisoformat(str(updated_str))
                days_stale = (today - updated).days
                if days_stale > stale_days and inbound.get(slug, 0) >= 2:
                    issues.append({
                        "type": "stale_page", "severity": "warning",
                        "slug": slug, "domain": domain,
                        "last_updated": str(updated),
                        "days_stale": days_stale,
                        "inbound_link_count": inbound.get(slug, 0),
                        "detail": f"Not updated in > {stale_days} days, has {inbound.get(slug,0)} inbound links",
                    })
            except (ValueError, TypeError):
                pass

        # Deleted-source orphan
        sources = meta.get("sources") or []
        if sources:
            all_deleted = all(
                _source_is_deleted(src, db) for src in sources
            )
            if all_deleted:
                issues.append({
                    "type": "deleted_source_orphan", "severity": "warning",
                    "slug": slug, "domain": domain,
                    "detail": "All source notes have status=deleted; wiki page may be outdated",
                })

        # Low confidence
        if meta.get("confidence", 1.0) < 0.6:
            issues.append({
                "type": "low_confidence_page", "severity": "warning",
                "slug": slug, "domain": domain,
                "confidence": meta.get("confidence"),
                "detail": "All source proposals had confidence < 0.6",
            })

        # Page too large
        wc = _word_count(content)
        if wc > page_max_words:
            issues.append({
                "type": "page_too_large", "severity": "warning",
                "slug": slug, "domain": domain,
                "word_count": wc, "limit": page_max_words,
                "detail": f"Page exceeds word count ceiling; may overflow query context window",
            })

    # Domain over-limit
    for domain_name, domain_cfg in domains_cfg.items():
        if domain_filter and domain_name != domain_filter:
            continue
        max_pages = domain_cfg.get("max_pages", cfg["domains"]["max_pages_per_domain"])
        page_count = sum(1 for p in (wiki / "domains" / domain_name).glob("*.md")
                         if p.name != "index.md") if (wiki / "domains" / domain_name).exists() else 0
        if page_count > max_pages:
            issues.append({
                "type": "domain_over_limit", "severity": "error",
                "domain": domain_name, "page_count": page_count, "limit": max_pages,
                "detail": f"Domain exceeds maximum page count; split into sub-domains required",
            })

    # Failed commits > 24h unresolved
    failed = db.get_commits_by_status("failed")
    for c in failed:
        started = datetime.fromisoformat(c.started_at)
        if (datetime.now(timezone.utc) - started).total_seconds() > 86400:
            issues.append({
                "type": "failed_commit", "severity": "error",
                "commit_id": c.id,
                "proposal_id": c.proposal_id,
                "hours_unresolved": int((datetime.now(timezone.utc) - started).total_seconds() / 3600),
                "detail": "Commit in status=failed for > 24h",
            })

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tier": "structural",
        "summary": {
            "total_pages": len(all_pages),
            "total_issues": len(issues),
            "domains_checked": sorted(domains_checked),
        },
        "issues": issues,
    }

    _write_report(report, "structural", domain_filter)
    return report


def _source_is_deleted(source_slug: str, db) -> bool:
    from models import NoteStatus
    note = db.get_note_by_path(source_slug)
    if note is None:
        return False
    return note.status == NoteStatus.DELETED


# ---------------------------------------------------------------------------
# Semantic lint
# ---------------------------------------------------------------------------

def run_semantic(domain: str) -> dict:
    """Run semantic lint on recently modified pages in a domain."""
    import ollama
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

    cfg = _load_settings()
    model = cfg["ollama"]["model"]
    timeout = cfg["ollama"]["timeout_seconds"]
    lookback_days = cfg["lint"]["semantic_lookback_days"]
    cutoff = date.today() - timedelta(days=lookback_days)

    wiki = _wiki_root()
    issues = []
    pages_checked = 0

    for page in (wiki / "domains" / domain).glob("*.md"):
        if page.name == "index.md":
            continue
        content = page.read_text(encoding="utf-8")
        meta = _parse_front_matter(content)

        updated_str = meta.get("updated", "")
        try:
            updated = date.fromisoformat(str(updated_str))
        except (ValueError, TypeError):
            continue
        if updated < cutoff:
            continue

        slug = page.stem
        pages_checked += 1

        prompt = SEMANTIC_LINT_PROMPT.format(slug=slug, body=content[:6000])

        try:
            def _call():
                r = ollama.chat(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    think=False,
                )
                return r["message"]["content"]

            with ThreadPoolExecutor(max_workers=1) as executor:
                raw = executor.submit(_call).result(timeout=timeout)
            # Strip <think> blocks and markdown fences, extract first JSON object
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
            raw = re.sub(r"```(?:json)?", "", raw).strip()
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                raw = m.group(0)
            data = json.loads(raw)
        except Exception as e:
            print(f"[LINT] semantic error on {slug}: {e}")
            continue

        for contradiction in data.get("internal_contradictions", []):
            if contradiction.get("statement_a") and contradiction.get("statement_b"):
                issues.append({
                    "type": "internal_contradiction", "slug": slug, "domain": domain,
                    "statement_a": contradiction["statement_a"],
                    "statement_b": contradiction["statement_b"],
                    "detail": "These statements directly contradict each other within the page body.",
                })

        for claim in data.get("unsupported_claims", []):
            if claim:
                issues.append({
                    "type": "unsupported_claim", "slug": slug, "domain": domain,
                    "claim": claim,
                    "detail": "Assertion has no source reference in the Sources section.",
                })

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tier": "semantic",
        "domain": domain,
        "model": model,
        "lookback_days": lookback_days,
        "pages_checked": pages_checked,
        "summary": {"total_issues": len(issues)},
        "issues": issues,
    }

    _write_report(report, "semantic", domain)
    return report


def _write_report(report: dict, tier: str, domain: Optional[str]) -> None:
    wiki = _wiki_root()
    lint_dir = wiki / "lint"
    lint_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    suffix = f"-{domain}" if domain and tier == "semantic" else ""
    path = lint_dir / f"{tier}-{today}{suffix}.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    n = report["summary"]["total_issues"]
    status = "✓ No issues" if n == 0 else f"⚠ {n} issue(s)"
    print(f"[LINT] {tier.title()} lint complete: {status} → {path.name}")


if __name__ == "__main__":
    tier = "structural"
    domain_arg = None
    after_commits = None

    if "--tier" in sys.argv:
        idx = sys.argv.index("--tier")
        if idx + 1 < len(sys.argv):
            tier = sys.argv[idx + 1]

    if "--domain" in sys.argv:
        idx = sys.argv.index("--domain")
        if idx + 1 < len(sys.argv):
            domain_arg = sys.argv[idx + 1]

    if "--after-commits" in sys.argv:
        idx = sys.argv.index("--after-commits")
        if idx + 1 < len(sys.argv):
            after_commits = int(sys.argv[idx + 1])

    if tier == "structural":
        report = run_structural(domain_filter=domain_arg)
        sys.exit(0 if report["summary"]["total_issues"] == 0 else 1)
    elif tier == "semantic":
        if not domain_arg:
            print("--domain required for semantic lint")
            sys.exit(2)
        report = run_semantic(domain=domain_arg)
        sys.exit(0 if report["summary"]["total_issues"] == 0 else 1)
    else:
        print(f"Unknown tier: {tier}")
        sys.exit(2)
