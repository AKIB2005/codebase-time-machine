"""
git_analyzer.py — Codebase Time Machine: Git history extraction layer.

Reads a Git repository via subprocess calls to the system `git` binary and
produces a deterministic, structured JSON file describing the full commit
history plus repository-level metadata.

No external Python dependencies are required.

Usage:
    python src/git_analyzer.py <repo_path> [output_path]

    repo_path   — path to the root of the Git repository to analyse
    output_path — (optional) destination for the JSON file
                  defaults to output/repo_history.json relative to CWD

JSON schema: see src/README.md
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum number of diff lines captured per file per commit.
# Keeps the JSON manageable while preserving enough context for analysis.
MAX_DIFF_LINES_PER_FILE = 60

# ---------------------------------------------------------------------------
# Low-level Git helpers
# ---------------------------------------------------------------------------

def _run(args: list[str], cwd: str) -> str:
    """Run a git command, return stdout as a string.

    Raises:
        RuntimeError if the process exits with a non-zero code.
    """
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        raise RuntimeError(
            "git executable not found. "
            "Ensure Git is installed and available on PATH."
        )
    if result.returncode != 0:
        raise RuntimeError(
            f"git command failed (exit {result.returncode}):\n"
            f"  cmd : {' '.join(args)}\n"
            f"  stderr: {result.stderr.strip()}"
        )
    return result.stdout


def _verify_repo(repo_path: str) -> str:
    """Confirm repo_path contains a valid Git repository.

    Returns the absolute, resolved path.
    Raises ValueError for bad paths; RuntimeError for Git errors.
    """
    resolved = str(Path(repo_path).resolve())
    if not os.path.isdir(resolved):
        raise ValueError(f"Repository path does not exist: {resolved}")
    try:
        _run(["git", "rev-parse", "--git-dir"], cwd=resolved)
    except RuntimeError:
        raise RuntimeError(
            f"Not a Git repository (or no Git history found): {resolved}"
        )
    return resolved


# ---------------------------------------------------------------------------
# Commit list — get hashes only
# ---------------------------------------------------------------------------

def _get_commit_hashes(repo_path: str) -> list[str]:
    """Return all commit hashes, oldest-first."""
    raw = _run(
        ["git", "log", "--reverse", "--format=%H"],
        cwd=repo_path,
    )
    hashes = [h.strip() for h in raw.splitlines() if h.strip()]
    if not hashes:
        raise RuntimeError("Repository has no commits.")
    return hashes


# ---------------------------------------------------------------------------
# Per-commit metadata via individual git show calls
# ---------------------------------------------------------------------------

def _get_commit_meta(repo_path: str, commit_hash: str) -> dict[str, Any]:
    """
    Retrieve metadata for a single commit using separate git calls.
    Returns a dict with keys: author_name, author_email, timestamp,
    parents, subject, body.
    """
    # Use NUL-delimited format printed to stdout — avoids shell escaping issues.
    # Format: each placeholder on its own line using --format with individual runs.
    def _field(fmt: str) -> str:
        return _run(
            ["git", "show", "-s", f"--format={fmt}", commit_hash],
            cwd=repo_path,
        ).strip()

    author_name  = _field("%an")
    author_email = _field("%ae")
    timestamp    = _field("%aI")
    parents_raw  = _field("%P")
    subject      = _field("%s")
    body         = _field("%b")

    parents = [p for p in parents_raw.split() if p]
    message = f"{subject}\n\n{body}".strip() if body else subject

    return {
        "author_name":  author_name,
        "author_email": author_email,
        "timestamp":    timestamp,
        "parents":      parents,
        "message":      message,
        "short_hash":   commit_hash[:7],
    }


# ---------------------------------------------------------------------------
# Per-commit file stats (numstat + name-status)
# ---------------------------------------------------------------------------

def _get_numstat(repo_path: str, commit_hash: str,
                 parents: list[str]) -> list[dict[str, Any]]:
    """
    Return per-file diff stats for a commit.

    For merge commits (multiple parents) we diff against the first parent.
    For the root commit (no parents) we diff against the empty tree.
    """
    EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    base = parents[0] if parents else EMPTY_TREE

    numstat_raw = _run(
        ["git", "diff", "--numstat", f"{base}..{commit_hash}"],
        cwd=repo_path,
    )
    name_status_raw = _run(
        ["git", "diff", "--name-status", f"{base}..{commit_hash}"],
        cwd=repo_path,
    )

    # Build status map: path -> status letter
    status_map: dict[str, str] = {}
    for line in name_status_raw.splitlines():
        line = line.strip()
        if not line:
            continue
        cols = line.split("\t")
        status_letter = cols[0][0]
        path = cols[-1].strip()
        status_map[path] = status_letter

    files: list[dict[str, Any]] = []
    for line in numstat_raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue

        added_raw, deleted_raw, path = parts[0], parts[1], parts[2].strip()

        try:
            added   = int(added_raw)
            deleted = int(deleted_raw)
        except ValueError:
            added   = 0
            deleted = 0

        files.append({
            "path":    path,
            "status":  status_map.get(path, "?"),
            "added":   added,
            "deleted": deleted,
        })

    return files


# ---------------------------------------------------------------------------
# Diff snippet capture
# ---------------------------------------------------------------------------

def _get_diff_snippets(repo_path: str, commit_hash: str,
                       parents: list[str],
                       file_entries: list[dict]) -> dict[str, list[str]]:
    """
    Return a dict mapping file_path -> list of diff lines (truncated).
    Only captures files with actual line changes.
    """
    EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    base = parents[0] if parents else EMPTY_TREE

    snippets: dict[str, list[str]] = {}

    for entry in file_entries:
        path = entry["path"]
        if entry["added"] == 0 and entry["deleted"] == 0:
            continue

        try:
            diff_raw = _run(
                [
                    "git", "diff",
                    "--unified=2",
                    f"{base}..{commit_hash}",
                    "--", path,
                ],
                cwd=repo_path,
            )
        except RuntimeError:
            continue

        lines = diff_raw.splitlines()
        hunk_start = next(
            (i for i, l in enumerate(lines) if l.startswith("@@")), None
        )
        if hunk_start is None:
            continue

        hunk_lines = lines[hunk_start:]
        if len(hunk_lines) > MAX_DIFF_LINES_PER_FILE:
            hunk_lines = hunk_lines[:MAX_DIFF_LINES_PER_FILE]
            hunk_lines.append(f"... (truncated at {MAX_DIFF_LINES_PER_FILE} lines)")

        snippets[path] = hunk_lines

    return snippets


# ---------------------------------------------------------------------------
# Repository-level metadata
# ---------------------------------------------------------------------------

def _build_metadata(commits: list[dict]) -> dict[str, Any]:
    """Compute repository-level summary statistics from processed commits."""
    all_files: set[str] = set()
    contributor_map: dict[str, str] = {}  # email -> display_name

    for c in commits:
        for f in c.get("files_changed", []):
            all_files.add(f["path"])
        email = c.get("_author_email", "")
        name  = c.get("_author_name", "unknown")
        if email:
            contributor_map[email] = name

    first_ts = commits[0]["timestamp"]  if commits else None
    last_ts  = commits[-1]["timestamp"] if commits else None

    return {
        "total_commits":       len(commits),
        "first_commit_date":   first_ts,
        "latest_commit_date":  last_ts,
        "total_files_touched": len(all_files),
        "contributors":        sorted(set(contributor_map.values())),
        "all_touched_files":   sorted(all_files),
    }


# ---------------------------------------------------------------------------
# Main extraction pipeline
# ---------------------------------------------------------------------------

def extract(repo_path: str) -> dict[str, Any]:
    """
    Full extraction pipeline.

    Returns a dict with keys:
        schema_version  — str
        generated_at    — ISO-8601 UTC timestamp of this run
        repository      — metadata dict
        commits         — list of commit dicts, oldest-first

    Author email addresses are NEVER written to the returned dict.
    """
    repo_path = _verify_repo(repo_path)

    print(f"[git_analyzer] Extracting history from: {repo_path}")
    hashes = _get_commit_hashes(repo_path)
    print(f"[git_analyzer] Found {len(hashes)} commit(s). Processing...")

    processed: list[dict[str, Any]] = []

    for i, h in enumerate(hashes, 1):
        try:
            meta = _get_commit_meta(repo_path, h)
        except RuntimeError as exc:
            print(f"[WARN] meta failed for {h[:8]}: {exc}", file=sys.stderr)
            continue

        parents = meta["parents"]

        try:
            file_entries = _get_numstat(repo_path, h, parents)
        except RuntimeError as exc:
            print(f"[WARN] numstat failed for {h[:8]}: {exc}", file=sys.stderr)
            file_entries = []

        try:
            diff_snippets = _get_diff_snippets(repo_path, h, parents, file_entries)
        except RuntimeError as exc:
            print(f"[WARN] diff failed for {h[:8]}: {exc}", file=sys.stderr)
            diff_snippets = {}

        for entry in file_entries:
            snippet = diff_snippets.get(entry["path"])
            if snippet:
                entry["diff_snippet"] = snippet

        commit_record: dict[str, Any] = {
            "hash":          h,
            "short_hash":    meta["short_hash"],
            "author":        meta["author_name"],
            "timestamp":     meta["timestamp"],
            "message":       meta["message"],
            "parents":       parents,
            "files_changed": file_entries,
            "stats": {
                "files":   len(file_entries),
                "added":   sum(f["added"]   for f in file_entries),
                "deleted": sum(f["deleted"] for f in file_entries),
            },
            # Private — for metadata aggregation only, stripped before output
            "_author_email": meta["author_email"],
            "_author_name":  meta["author_name"],
        }

        processed.append(commit_record)
        print(f"  [{i:>2}/{len(hashes)}] {h[:8]}  {meta['message'][:60]}")

    metadata = _build_metadata(processed)

    # Strip private fields
    for c in processed:
        c.pop("_author_email", None)
        c.pop("_author_name",  None)

    return {
        "schema_version": "1.0",
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "repository":     metadata,
        "commits":        processed,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Codebase Time Machine — Git history extractor"
    )
    parser.add_argument(
        "repo_path",
        help="Path to the root of the Git repository to analyse",
    )
    parser.add_argument(
        "output_path",
        nargs="?",
        default=str(Path("output") / "repo_history.json"),
        help="Destination JSON file (default: output/repo_history.json)",
    )
    args = parser.parse_args()

    try:
        history = extract(args.repo_path)
    except (ValueError, RuntimeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(history, fh, indent=2, ensure_ascii=False)

    commit_count = history["repository"]["total_commits"]
    print(f"\n[git_analyzer] Done. {commit_count} commit(s) written to: {out_path}")


if __name__ == "__main__":
    main()
