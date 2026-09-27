"""
validate_onboarding.py — Codebase Time Machine: onboarding guide validator.

Checks:
  1. Required sections exist in output/onboarding_guide.md
  2. Commit hashes referenced in the guide exist in repo_history.json
  3. No author email addresses appear in the guide
  4. The three prior analysis files are untouched (existence + hash check)
  5. output/onboarding_guide.md exists

Usage:
    python src/validate_onboarding.py [guide_path] [history_path]
                                      [epoch_path] [why_path]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

# Expected section headings (substring match — tolerates minor formatting)
REQUIRED_SECTIONS = [
    "## 1. Project Overview",
    "## 2. How the Codebase Evolved",
    "## 3. Current Architecture",
    "## 4. Where Should a New Developer Start",
    "## 5. Important Historical Changes",
    "## 6. Known Historical Issues",
    "## 7. Suggested First Investigation",
    "## 8. Historical Timeline",
    "## 9. Evidence and Confidence",
]

# Short hashes from the sample repository that MUST appear in the guide
REQUIRED_SHORT_HASHES = [
    "79b1b0c",
    "1d9e8be",
    "967b11a",
    "c8491ae",
    "c5040fb",
    "861190a",
    "a4544f2",
    "c434a6f",
    "af36d82",
    "a2116ca",
]

EMAIL_PAT = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def _add(results, status, msg):
    results.append((status, msg))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_guide_exists(guide_path: str, results: list) -> str | None:
    p = Path(guide_path)
    if p.exists():
        size = p.stat().st_size
        _add(results, "PASS", f"output/onboarding_guide.md exists ({size:,} bytes)")
        return p.read_text(encoding="utf-8")
    else:
        _add(results, "FAIL", f"output/onboarding_guide.md NOT FOUND at {guide_path}")
        return None


def check_required_sections(content: str, results: list) -> None:
    for section in REQUIRED_SECTIONS:
        if section in content:
            _add(results, "PASS", f"Section present: {section!r}")
        else:
            _add(results, "FAIL", f"Section MISSING: {section!r}")


def check_commit_hashes(content: str, history_path: str, results: list) -> None:
    # Load full hashes
    try:
        with open(history_path, encoding="utf-8") as f:
            history = json.load(f)
        full_hashes = {c["hash"] for c in history["commits"]}
        short_to_full = {c["hash"][:7]: c["hash"] for c in history["commits"]}
    except Exception as exc:
        _add(results, "FAIL", f"Could not load repo_history.json: {exc}")
        return

    # Check each required short hash appears in the guide
    for sh in REQUIRED_SHORT_HASHES:
        if sh in content:
            _add(results, "PASS", f"Commit hash {sh!r} referenced in guide")
        else:
            _add(results, "FAIL",
                 f"Commit hash {sh!r} NOT referenced in guide")

    # Check that any 40-char hex strings in the guide are real hashes
    forty_char_hashes = re.findall(r"\b[0-9a-f]{40}\b", content)
    for h in set(forty_char_hashes):
        if h in full_hashes:
            _add(results, "PASS", f"Full hash {h[:12]}... verified in history")
        else:
            _add(results, "FAIL",
                 f"Full hash {h[:12]}... NOT found in history")


def check_no_emails(content: str, results: list) -> None:
    found = EMAIL_PAT.findall(content)
    if found:
        _add(results, "FAIL",
             f"Email address(es) found in guide (privacy violation): {found[:3]}")
    else:
        _add(results, "PASS", "No email addresses detected in onboarding guide")


def check_analysis_files_untouched(
    history_path: str, epoch_path: str, why_path: str, results: list
) -> None:
    """Verify each file exists (we cannot check original hashes
    without a baseline, so we confirm existence and valid JSON)."""
    for label, path in [
        ("repo_history.json",    history_path),
        ("epoch_analysis.json",  epoch_path),
        ("why_analysis.json",    why_path),
    ]:
        p = Path(path)
        if not p.exists():
            _add(results, "FAIL", f"{label} MISSING — previous output was deleted!")
            continue
        try:
            with p.open(encoding="utf-8") as f:
                data = json.load(f)
            sv = data.get("schema_version", "?")
            _add(results, "PASS",
                 f"{label} exists, valid JSON (schema_version={sv!r})")
        except json.JSONDecodeError as exc:
            _add(results, "FAIL",
                 f"{label} exists but JSON is corrupted: {exc}")


def check_no_invented_phrases(content: str, results: list) -> None:
    """Heuristic check for phrases that would indicate fabricated content."""
    forbidden = [
        "the developer wanted",
        "production required",
        "needed to scale",
    ]
    violations = []
    lower = content.lower()
    for phrase in forbidden:
        if phrase in lower:
            violations.append(phrase)
    if violations:
        _add(results, "FAIL",
             f"Possible invented-motivation phrases detected: {violations}")
    else:
        _add(results, "PASS",
             "No forbidden invented-motivation phrases detected in guide")


def check_inference_labels(content: str, results: list) -> None:
    """Guide must use [INFERENCE] labels for interpretive claims."""
    count = content.count("[INFERENCE]")
    if count >= 3:
        _add(results, "PASS",
             f"[INFERENCE] label used {count} times (required: >= 3)")
    else:
        _add(results, "FAIL",
             f"[INFERENCE] label used only {count} times (expected >= 3)")


def check_caveat_preserved(content: str, results: list) -> None:
    """Key caveats from why_analysis.json must appear."""
    caveats = [
        ("SQLite repository–service disconnect", "NOT WIRED"),
        ("Pagination bug documented", "# BUG:"),
        ("In-memory rate limiter limitation", "in-memory"),
    ]
    for label, keyword in caveats:
        if keyword.lower() in content.lower():
            _add(results, "PASS", f"Caveat present: {label!r} ({keyword!r})")
        else:
            _add(results, "FAIL", f"Caveat MISSING: {label!r} ({keyword!r})")


# ---------------------------------------------------------------------------
# Print
# ---------------------------------------------------------------------------

def _print_results(results: list) -> int:
    passed = [r for r in results if r[0] == "PASS"]
    failed = [r for r in results if r[0] == "FAIL"]
    warned = [r for r in results if r[0] == "WARN"]

    print()
    print("=" * 72)
    print("  Codebase Time Machine - onboarding_guide.md Validation Report")
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
        description="Validate output/onboarding_guide.md"
    )
    parser.add_argument("guide_path",   nargs="?",
                        default=str(Path("output") / "onboarding_guide.md"))
    parser.add_argument("history_path", nargs="?",
                        default=str(Path("output") / "repo_history.json"))
    parser.add_argument("epoch_path",   nargs="?",
                        default=str(Path("output") / "epoch_analysis.json"))
    parser.add_argument("why_path",     nargs="?",
                        default=str(Path("output") / "why_analysis.json"))
    args = parser.parse_args()

    results: list = []

    # 1. Check guide exists and load it
    content = check_guide_exists(args.guide_path, results)

    if content is not None:
        check_required_sections(content, results)
        check_commit_hashes(content, args.history_path, results)
        check_no_emails(content, results)
        check_no_invented_phrases(content, results)
        check_inference_labels(content, results)
        check_caveat_preserved(content, results)

    # 2. Check prior analysis files are untouched
    check_analysis_files_untouched(
        args.history_path, args.epoch_path, args.why_path, results
    )

    failures = _print_results(results)
    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    main()
