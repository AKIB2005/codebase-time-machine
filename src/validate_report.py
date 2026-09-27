"""
validate_report.py — Codebase Time Machine: evolution_report.html validator.

Checks:
  1.  evolution_report.html exists and is non-empty
  2.  File is self-contained (no external http/https src/href references)
  3.  All 10 commit hashes appear
  4.  All 5 epoch names appear
  5.  All 8 why-analysis change titles appear
  6.  The SQLite NOT WIRED caveat appears
  7.  Onboarding content appears (reading-order + investigation questions)
  8.  No author email addresses appear
  9.  No forbidden invented-motivation phrases
  10. The four existing output files were not modified (existence + valid JSON/MD)

Usage:
    python src/validate_report.py [report_path]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EMAIL_PAT = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
EXTERNAL_PAT = re.compile(r'(?:src|href)\s*=\s*["\']https?://', re.IGNORECASE)

# All 10 short hashes from the sample repository
REQUIRED_HASHES = [
    "79b1b0c", "1d9e8be", "967b11a", "c8491ae", "c5040fb",
    "861190a", "a4544f2", "c434a6f", "af36d82", "a2116ca",
]

# All 5 epoch names (substrings)
REQUIRED_EPOCH_NAMES = [
    "Foundation and Domain Bootstrap",
    "Vertical Feature Build-Out",
    "Pagination Bug Introduction",
    "Architectural Decoupling via Event Bus",
    "Quality Assurance and Security Hardening",
]

# Why-analysis change titles (substrings)
REQUIRED_WHY_CHANGES = [
    "Introduction of user authentication",
    "Introduction of SQLite persistence layer",
    "Introduction of Flask REST API",
    "Pagination introduction",
    "Pagination off-by-one bug correction",
    "EventBus architectural decoupling",
    "Introduction of automated test suite",
    "Login rate limiting",
]

# Critical caveats from why_analysis / onboarding
REQUIRED_CAVEATS = [
    ("SQLite NOT WIRED caveat",       "NOT WIRED"),
    ("Pagination BUG comment",        "# BUG:"),
    ("In-memory rate limiter note",   "in-memory"),
]

# Onboarding markers
REQUIRED_ONBOARDING = [
    ("Reading-order table",           "Recommended Reading Order"),
    ("Investigation questions",       "Open Investigation Questions"),
]

# Invented-motivation forbidden phrases
FORBIDDEN_PHRASES = [
    "the developer wanted",
    "production required",
    "needed to scale",
]

# Files that must not have been modified
PROTECTED_FILES = [
    ("output/repo_history.json",   "json"),
    ("output/epoch_analysis.json", "json"),
    ("output/why_analysis.json",   "json"),
    ("output/onboarding_guide.md", "text"),
]


def _add(results, status, msg):
    results.append((status, msg))


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_exists(report_path: str, results: list) -> str | None:
    p = Path(report_path)
    if not p.exists():
        _add(results, "FAIL", f"evolution_report.html NOT FOUND at {report_path}")
        return None
    size = p.stat().st_size
    if size < 10_000:
        _add(results, "FAIL",
             f"evolution_report.html exists but suspiciously small ({size:,} bytes)")
        return None
    _add(results, "PASS",
         f"evolution_report.html exists ({size:,} bytes / {size//1024} KB)")
    return p.read_text(encoding="utf-8")


def check_self_contained(content: str, results: list) -> None:
    # Should not reference external URLs in src/href attributes
    matches = EXTERNAL_PAT.findall(content)
    if matches:
        _add(results, "FAIL",
             f"External resource references found ({len(matches)}): {matches[:3]}")
    else:
        _add(results, "PASS", "No external src/href references — file is self-contained")

    # Should not have <script src="..."> pointing outside
    ext_script = re.findall(r'<script[^>]+src=["\']https?://', content, re.IGNORECASE)
    if ext_script:
        _add(results, "FAIL",
             f"External <script src> found: {ext_script[:2]}")


def check_commit_hashes(content: str, results: list) -> None:
    for sh in REQUIRED_HASHES:
        if sh in content:
            _add(results, "PASS", f"Commit hash {sh!r} present in report")
        else:
            _add(results, "FAIL", f"Commit hash {sh!r} MISSING from report")


def check_epoch_names(content: str, results: list) -> None:
    for name in REQUIRED_EPOCH_NAMES:
        if name in content:
            _add(results, "PASS", f"Epoch name present: {name!r}")
        else:
            _add(results, "FAIL", f"Epoch name MISSING: {name!r}")


def check_why_changes(content: str, results: list) -> None:
    for change in REQUIRED_WHY_CHANGES:
        if change.lower() in content.lower():
            _add(results, "PASS", f"Why-analysis change present: {change!r}")
        else:
            _add(results, "FAIL", f"Why-analysis change MISSING: {change!r}")


def check_caveats(content: str, results: list) -> None:
    for label, keyword in REQUIRED_CAVEATS:
        if keyword in content:
            _add(results, "PASS", f"Caveat present: {label!r} ({keyword!r})")
        else:
            _add(results, "FAIL", f"Caveat MISSING: {label!r} ({keyword!r})")


def check_onboarding(content: str, results: list) -> None:
    for label, keyword in REQUIRED_ONBOARDING:
        if keyword in content:
            _add(results, "PASS", f"Onboarding content present: {label!r}")
        else:
            _add(results, "FAIL", f"Onboarding content MISSING: {label!r}")


def check_no_emails(content: str, results: list) -> None:
    # Only check outside diff-snippet / code areas — simple heuristic: check
    # the full file but accept emails that appear inside <code> tags as they
    # may be from source code examples.
    # For safety: strip content inside <code>...</code> first.
    stripped = re.sub(r"<code[^>]*>.*?</code>", "", content,
                      flags=re.DOTALL | re.IGNORECASE)
    found = EMAIL_PAT.findall(stripped)
    if found:
        _add(results, "FAIL",
             f"Email address(es) found outside code blocks: {found[:3]}")
    else:
        _add(results, "PASS", "No email addresses found outside code blocks")


def check_no_invented(content: str, results: list) -> None:
    lower = content.lower()
    violations = [p for p in FORBIDDEN_PHRASES if p in lower]
    if violations:
        _add(results, "FAIL",
             f"Forbidden invented-motivation phrases: {violations}")
    else:
        _add(results, "PASS", "No forbidden invented-motivation phrases")


def check_prior_outputs_intact(results: list) -> None:
    for path, kind in PROTECTED_FILES:
        p = Path(path)
        if not p.exists():
            _add(results, "FAIL", f"{path} MISSING — prior output deleted!")
            continue
        if kind == "json":
            try:
                with p.open(encoding="utf-8") as f:
                    data = json.load(f)
                sv = data.get("schema_version", "?")
                _add(results, "PASS",
                     f"{path} intact (schema_version={sv!r}, "
                     f"{p.stat().st_size:,} bytes)")
            except json.JSONDecodeError as exc:
                _add(results, "FAIL", f"{path} corrupted: {exc}")
        else:
            size = p.stat().st_size
            _add(results, "PASS", f"{path} intact ({size:,} bytes)")


# ---------------------------------------------------------------------------
# Print
# ---------------------------------------------------------------------------

def _print_results(results: list) -> int:
    passed = [r for r in results if r[0] == "PASS"]
    failed = [r for r in results if r[0] == "FAIL"]
    warned = [r for r in results if r[0] == "WARN"]

    print()
    print("=" * 72)
    print("  Codebase Time Machine - evolution_report.html Validation")
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
        description="Validate output/evolution_report.html"
    )
    parser.add_argument("report_path", nargs="?",
                        default=str(Path("output") / "evolution_report.html"))
    args = parser.parse_args()

    results: list = []

    content = check_exists(args.report_path, results)
    if content:
        check_self_contained(content, results)
        check_commit_hashes(content, results)
        check_epoch_names(content, results)
        check_why_changes(content, results)
        check_caveats(content, results)
        check_onboarding(content, results)
        check_no_emails(content, results)
        check_no_invented(content, results)

    check_prior_outputs_intact(results)

    failures = _print_results(results)
    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    main()
