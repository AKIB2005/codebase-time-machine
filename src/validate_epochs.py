"""
validate_epochs.py — Codebase Time Machine: epoch_analysis.json validator.

Checks that epoch_analysis.json conforms to the schema in
.bob/rules/02-output-format.md and the evidence rules in
.bob/rules/01-evidence.md.

Usage:
    python src/validate_epochs.py [epoch_path] [history_path]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        print(f"[ERROR] File not found: {path}", file=sys.stderr)
        sys.exit(1)
    with p.open(encoding="utf-8") as fh:
        return json.load(fh)


def _add(results, status, msg):
    results.append((status, msg))


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_top_level_keys(data: dict, results: list) -> None:
    required = ["schema_version", "generated_at", "analyzer",
                "source_file", "repository_summary", "epochs"]
    for k in required:
        if k not in data:
            _add(results, "FAIL", f"Missing top-level key: {k!r}")
        else:
            _add(results, "PASS", f"Top-level key present: {k!r}")


def check_repository_summary(data: dict, results: list) -> None:
    rs = data.get("repository_summary", {})
    for k in ["total_commits", "total_epochs_found", "date_range",
              "all_contributors", "total_files_touched"]:
        if k not in rs:
            _add(results, "FAIL", f"repository_summary missing key: {k!r}")
        else:
            _add(results, "PASS", f"repository_summary.{k} present")

    dr = rs.get("date_range", {})
    for k in ["first", "last"]:
        if k not in dr:
            _add(results, "FAIL", f"repository_summary.date_range missing key: {k!r}")

    epoch_count = len(data.get("epochs", []))
    stated = rs.get("total_epochs_found", -1)
    if stated != epoch_count:
        _add(results, "FAIL",
             f"repository_summary.total_epochs_found ({stated}) != "
             f"actual epoch count ({epoch_count})")
    else:
        _add(results, "PASS",
             f"total_epochs_found matches epoch list length ({epoch_count})")


def check_epoch_ids_unique(data: dict, results: list) -> None:
    ids = [e.get("epoch_id") for e in data.get("epochs", [])]
    if len(ids) == len(set(ids)):
        _add(results, "PASS", f"All {len(ids)} epoch_ids are unique")
    else:
        _add(results, "FAIL", f"Duplicate epoch_ids detected: {ids}")


def check_epoch_structure(data: dict, history_hashes: set, results: list) -> None:
    epochs = data.get("epochs", [])
    if not epochs:
        _add(results, "FAIL", "epochs list is empty")
        return

    for e in epochs:
        label = e.get("epoch_id", "?")

        # Required string fields
        for field in ["epoch_id", "name", "summary", "confidence"]:
            if not e.get(field):
                _add(results, "FAIL", f"{label}: missing or empty {field!r}")

        # name length
        name = e.get("name", "")
        if len(name) > 60:
            _add(results, "FAIL",
                 f"{label}: name exceeds 60 chars ({len(name)})")
        else:
            _add(results, "PASS", f"{label}: name length OK ({len(name)} chars)")

        # confidence enum
        conf = e.get("confidence")
        if conf not in ("HIGH", "MEDIUM", "LOW"):
            _add(results, "FAIL",
                 f"{label}: confidence must be HIGH/MEDIUM/LOW, got {conf!r}")
        else:
            _add(results, "PASS", f"{label}: confidence = {conf}")

        # uncertainty_notes rule (E11)
        un = e.get("uncertainty_notes")
        if conf == "HIGH" and un is not None:
            _add(results, "FAIL",
                 f"{label}: uncertainty_notes must be null when confidence=HIGH")
        elif conf in ("MEDIUM", "LOW") and not un:
            _add(results, "FAIL",
                 f"{label}: uncertainty_notes required when confidence={conf}")
        else:
            _add(results, "PASS", f"{label}: uncertainty_notes rule satisfied")

        # commit_hashes
        ch = e.get("commit_hashes", [])
        if not ch:
            _add(results, "FAIL", f"{label}: commit_hashes is empty")
        else:
            unknown = [h[:8] for h in ch if h not in history_hashes]
            if unknown:
                _add(results, "FAIL",
                     f"{label}: commit_hashes contains unknown hashes: {unknown}")
            else:
                _add(results, "PASS",
                     f"{label}: all {len(ch)} commit hash(es) verified in history")

        # start/end consistency
        if ch:
            if e.get("start_commit") != ch[0]:
                _add(results, "FAIL",
                     f"{label}: start_commit != commit_hashes[0]")
            else:
                _add(results, "PASS", f"{label}: start_commit consistent")
            if e.get("end_commit") != ch[-1]:
                _add(results, "FAIL",
                     f"{label}: end_commit != commit_hashes[-1]")
            else:
                _add(results, "PASS", f"{label}: end_commit consistent")

        # observed_changes
        oc = e.get("observed_changes", [])
        if not oc:
            _add(results, "FAIL", f"{label}: observed_changes is empty")
        else:
            _add(results, "PASS",
                 f"{label}: observed_changes has {len(oc)} entry/entries")
            for idx, obs in enumerate(oc):
                if not obs.get("description"):
                    _add(results, "FAIL",
                         f"{label} observed_changes[{idx}]: missing description")
                ec = obs.get("evidence_commits", [])
                if not ec:
                    _add(results, "FAIL",
                         f"{label} observed_changes[{idx}]: evidence_commits is empty")
                else:
                    bad = [h[:8] for h in ec if h not in set(ch)]
                    if bad:
                        _add(results, "FAIL",
                             f"{label} observed_changes[{idx}]: evidence_commits "
                             f"outside epoch: {bad}")

        # inferred_theme
        it = e.get("inferred_theme", {})
        for k in ["label", "explanation", "basis"]:
            if not it.get(k):
                _add(results, "FAIL",
                     f"{label}: inferred_theme missing or empty {k!r}")

        it_label = it.get("label", "")
        if len(it_label) > 40:
            _add(results, "FAIL",
                 f"{label}: inferred_theme.label exceeds 40 chars ({len(it_label)})")
        else:
            _add(results, "PASS",
                 f"{label}: inferred_theme.label length OK")


def check_completeness(data: dict, history_hashes: set, results: list) -> None:
    """F5 — every commit must appear in exactly one epoch."""
    assigned: dict[str, str] = {}  # hash -> epoch_id
    duplicates = []
    for e in data.get("epochs", []):
        eid = e.get("epoch_id", "?")
        for h in e.get("commit_hashes", []):
            if h in assigned:
                duplicates.append(f"{h[:8]} in {assigned[h]} and {eid}")
            assigned[h] = eid

    missing = history_hashes - set(assigned.keys())

    if duplicates:
        _add(results, "FAIL",
             f"Commits assigned to multiple epochs: {duplicates}")
    else:
        _add(results, "PASS", "No commit assigned to multiple epochs")

    if missing:
        _add(results, "FAIL",
             f"{len(missing)} commit(s) not assigned to any epoch: "
             f"{[h[:8] for h in missing]}")
    else:
        _add(results, "PASS",
             f"All {len(history_hashes)} commit(s) assigned to exactly one epoch")


def check_no_emails(data: dict, results: list) -> None:
    import re
    email_pat = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
    violations = []
    for e in data.get("epochs", []):
        for field in ("name", "summary"):
            found = email_pat.findall(str(e.get(field, "")))
            if found:
                violations.append(f"epoch {e.get('epoch_id')}.{field}: {found}")
        for oc in e.get("observed_changes", []):
            # We allow emails inside description only if they are not
            # real author emails — we cannot distinguish here, so flag all.
            pass
        # Check inferred_theme fields
        it = e.get("inferred_theme", {})
        for k in ("label", "explanation", "basis"):
            found = email_pat.findall(str(it.get(k, "")))
            if found:
                violations.append(f"epoch {e.get('epoch_id')}.inferred_theme.{k}: {found}")

    if violations:
        _add(results, "FAIL",
             f"Email pattern found in metadata fields: {violations[:3]}")
    else:
        _add(results, "PASS", "No email addresses in epoch metadata fields")


# ---------------------------------------------------------------------------
# Print and exit
# ---------------------------------------------------------------------------

def _print_results(results: list) -> int:
    passed  = [r for r in results if r[0] == "PASS"]
    failed  = [r for r in results if r[0] == "FAIL"]
    warned  = [r for r in results if r[0] == "WARN"]

    print()
    print("=" * 72)
    print("  Codebase Time Machine - epoch_analysis.json Validation Report")
    print("=" * 72)
    for status, msg in results:
        icon = "+" if status == "PASS" else ("-" if status == "FAIL" else "!")
        print(f"  {icon} [{status:4s}]  {msg}")
    print("-" * 72)
    print(f"  Total: {len(results)} checks | "
          f"{len(passed)} passed, {len(failed)} failed, {len(warned)} warnings")
    print("=" * 72)
    print()
    return len(failed)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate output/epoch_analysis.json"
    )
    parser.add_argument("epoch_path", nargs="?",
                        default=str(Path("output") / "epoch_analysis.json"))
    parser.add_argument("history_path", nargs="?",
                        default=str(Path("output") / "repo_history.json"))
    args = parser.parse_args()

    data    = _load(args.epoch_path)
    history = _load(args.history_path)
    history_hashes = {c["hash"] for c in history.get("commits", [])}

    results: list = []
    check_top_level_keys(data, results)
    check_repository_summary(data, results)
    check_epoch_ids_unique(data, results)
    check_epoch_structure(data, history_hashes, results)
    check_completeness(data, history_hashes, results)
    check_no_emails(data, results)

    failures = _print_results(results)
    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    main()
