"""
validate_history.py — Codebase Time Machine: JSON output validator.

Confirms that the JSON produced by git_analyzer.py satisfies the minimum
structural requirements for the Codebase Time Machine pipeline.

Usage:
    python src/validate_history.py [json_path] [--expected-commits N]

    json_path          Path to the JSON file to validate.
                       Default: output/repo_history.json
    --expected-commits Expected number of commits (default: 10).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_schema_version(data: dict, results: list) -> None:
    if "schema_version" not in data:
        results.append(("FAIL", "Missing top-level key: schema_version"))
    else:
        results.append(("PASS", f"schema_version = {data['schema_version']!r}"))


def check_generated_at(data: dict, results: list) -> None:
    if "generated_at" not in data:
        results.append(("FAIL", "Missing top-level key: generated_at"))
    else:
        results.append(("PASS", f"generated_at present: {data['generated_at']}"))


def check_repository_metadata(data: dict, results: list) -> None:
    repo = data.get("repository")
    if repo is None:
        results.append(("FAIL", "Missing top-level key: repository"))
        return
    required_keys = [
        "total_commits",
        "first_commit_date",
        "latest_commit_date",
        "total_files_touched",
        "contributors",
        "all_touched_files",
    ]
    for key in required_keys:
        if key not in repo:
            results.append(("FAIL", f"repository metadata missing key: {key}"))
        else:
            results.append(("PASS", f"repository.{key} present"))

    # Consistency: total_commits should match len(commits)
    commits = data.get("commits", [])
    if repo.get("total_commits") != len(commits):
        results.append((
            "FAIL",
            f"repository.total_commits ({repo.get('total_commits')}) "
            f"does not match actual commit count ({len(commits)})"
        ))
    else:
        results.append((
            "PASS",
            f"repository.total_commits matches commit list length ({len(commits)})"
        ))

    # contributors must be a non-empty list
    contributors = repo.get("contributors", [])
    if not isinstance(contributors, list) or len(contributors) == 0:
        results.append(("FAIL", "repository.contributors is empty or not a list"))
    else:
        results.append((
            "PASS",
            f"repository.contributors has {len(contributors)} entry/entries: "
            f"{contributors}"
        ))


def check_commit_count(data: dict, expected: int, results: list) -> None:
    commits = data.get("commits", [])
    count = len(commits)
    if count == expected:
        results.append(("PASS", f"Commit count is exactly {expected}"))
    else:
        results.append((
            "FAIL",
            f"Expected {expected} commits, found {count}"
        ))


def check_commits_structure(data: dict, results: list) -> None:
    commits = data.get("commits", [])
    if not commits:
        results.append(("FAIL", "commits list is empty"))
        return

    seen_hashes: set[str] = set()

    for i, c in enumerate(commits):
        label = f"commits[{i}] ({c.get('short_hash', '?')})"

        # hash
        if not c.get("hash"):
            results.append(("FAIL", f"{label}: missing or empty 'hash'"))
        else:
            h = c["hash"]
            if h in seen_hashes:
                results.append(("FAIL", f"{label}: duplicate hash {h[:8]}"))
            else:
                seen_hashes.add(h)

        # message
        if not c.get("message"):
            results.append(("FAIL", f"{label}: missing or empty 'message'"))

        # files_changed
        if "files_changed" not in c:
            results.append(("FAIL", f"{label}: missing 'files_changed'"))
        elif not isinstance(c["files_changed"], list):
            results.append(("FAIL", f"{label}: 'files_changed' is not a list"))

        # stats
        if "stats" not in c:
            results.append(("FAIL", f"{label}: missing 'stats'"))
        else:
            for stat_key in ("files", "added", "deleted"):
                if stat_key not in c["stats"]:
                    results.append((
                        "FAIL", f"{label}: stats missing key '{stat_key}'"
                    ))

        # timestamp
        if not c.get("timestamp"):
            results.append(("FAIL", f"{label}: missing 'timestamp'"))

        # author — email must NOT appear
        if "email" in str(c.get("author", "")):
            results.append(("WARN", f"{label}: author field looks like an email"))

        # Explicitly check no 'email' key in commit record
        if "email" in c:
            results.append(("FAIL", f"{label}: commit record contains 'email' key (privacy violation)"))

    if len(seen_hashes) == len(commits):
        results.append(("PASS", f"All {len(commits)} commit hashes are unique"))


def check_no_emails_in_output(data: dict, results: list) -> None:
    """
    Confirm that author email addresses do not appear in commit metadata.

    We check only the structured metadata fields (author, message, stats)
    rather than diff snippets, because diff content legitimately contains
    email-like strings from source code (e.g. test fixtures).
    """
    import re
    email_pattern = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

    violations: list[str] = []
    for c in data.get("commits", []):
        # Check fields that should never contain email addresses
        for field in ("author", "message", "hash", "short_hash", "timestamp"):
            value = str(c.get(field, ""))
            found = email_pattern.findall(value)
            if found:
                violations.append(
                    f"commit {c.get('short_hash','?')}.{field}: {found}"
                )
        # 'email' key must not exist at commit level
        if "email" in c:
            violations.append(
                f"commit {c.get('short_hash','?')}: top-level 'email' key present"
            )

    # Check repository metadata block
    repo = data.get("repository", {})
    for field in ("contributors", "all_touched_files"):
        for item in repo.get(field, []):
            found = email_pattern.findall(str(item))
            if found:
                violations.append(f"repository.{field} item contains email: {found}")

    if violations:
        results.append((
            "FAIL",
            f"Author email found in metadata fields (privacy violation): "
            f"{violations[:3]}"
        ))
    else:
        results.append((
            "PASS",
            "No author email addresses detected in commit metadata fields"
        ))


def check_diff_snippets(data: dict, results: list) -> None:
    """Verify at least some commits have non-empty diff snippets."""
    commits = data.get("commits", [])
    commits_with_snippets = sum(
        1 for c in commits
        if any("diff_snippet" in f for f in c.get("files_changed", []))
    )
    if commits_with_snippets == 0:
        results.append(("WARN", "No commits have diff_snippet data"))
    else:
        results.append((
            "PASS",
            f"{commits_with_snippets}/{len(commits)} commits contain diff snippets"
        ))


# ---------------------------------------------------------------------------
# Report printer
# ---------------------------------------------------------------------------

def _print_results(results: list[tuple[str, str]]) -> int:
    """Print results table; return number of FAILs."""
    passed = [r for r in results if r[0] == "PASS"]
    failed = [r for r in results if r[0] == "FAIL"]
    warned = [r for r in results if r[0] == "WARN"]

    col_width = max(len(r[1]) for r in results) + 2

    print()
    print("=" * 72)
    print("  Codebase Time Machine - repo_history.json Validation Report")
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
        description="Validate output/repo_history.json for Codebase Time Machine"
    )
    parser.add_argument(
        "json_path",
        nargs="?",
        default=str(Path("output") / "repo_history.json"),
        help="Path to the JSON file (default: output/repo_history.json)",
    )
    parser.add_argument(
        "--expected-commits",
        type=int,
        default=10,
        dest="expected_commits",
        help="Expected number of commits (default: 10)",
    )
    args = parser.parse_args()

    json_path = Path(args.json_path)
    if not json_path.exists():
        print(f"[ERROR] File not found: {json_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with json_path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"[ERROR] JSON parse error: {exc}", file=sys.stderr)
        sys.exit(1)

    results: list[tuple[str, str]] = []

    check_schema_version(data, results)
    check_generated_at(data, results)
    check_repository_metadata(data, results)
    check_commit_count(data, args.expected_commits, results)
    check_commits_structure(data, results)
    check_no_emails_in_output(data, results)
    check_diff_snippets(data, results)

    failures = _print_results(results)
    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    main()
