# src/git_analyzer.py — Codebase Time Machine: Git History Extraction Layer

## Overview

`git_analyzer.py` reads a local Git repository via the system `git` binary
(invoked through Python `subprocess`) and produces a deterministic, structured
JSON file that describes the repository's full commit history together with
repository-level metadata.

It uses **only the Python standard library** — no external packages are needed.

---

## How It Works

The extraction pipeline runs in five stages:

```
1. verify_repo     Confirm the path is a valid Git repository.
2. parse_log       Run `git log` with a custom record-separated format
                   to collect commit metadata for all commits (oldest-first).
3. get_numstat     For each commit, run `git diff --numstat` to get
                   per-file line-change counts and `git diff --name-status`
                   to get the change status (A / M / D / R / C).
4. get_diff_snip   For each changed file, capture up to 60 hunk lines
                   from `git diff --unified=2` to provide evidence for
                   later analysis without bloating the JSON.
5. build_metadata  Aggregate repository-level statistics across all commits.
```

**Privacy rule:** Author email addresses are collected internally only for
contributor de-duplication. They are stripped from every commit record and
from the repository metadata before the JSON file is written.

---

## Input

| Argument | Required | Description |
|----------|----------|-------------|
| `repo_path` | ✅ | Absolute or relative path to the root of the Git repository |
| `output_path` | ❌ | Destination for the JSON file. Default: `output/repo_history.json` |

---

## Output

The output is a single UTF-8 JSON file (`output/repo_history.json` by default).

---

## JSON Schema

```json
{
  "schema_version": "1.0",
  "generated_at":   "<ISO-8601 UTC timestamp of this run>",

  "repository": {
    "total_commits":        <int>,
    "first_commit_date":    "<ISO-8601>",
    "latest_commit_date":   "<ISO-8601>",
    "total_files_touched":  <int>,
    "contributors":         ["<name>", ...],
    "all_touched_files":    ["<path>", ...]
  },

  "commits": [
    {
      "hash":       "<40-char SHA-1>",
      "short_hash": "<7-char SHA-1>",
      "author":     "<display name — email NOT included>",
      "timestamp":  "<ISO-8601 with timezone offset>",
      "message":    "<full commit message (subject + body)>",
      "parents":    ["<hash>", ...],

      "stats": {
        "files":   <int>,
        "added":   <int>,
        "deleted": <int>
      },

      "files_changed": [
        {
          "path":    "<file path relative to repo root>",
          "status":  "<A|M|D|R|C|?>",
          "added":   <int>,
          "deleted": <int>,
          "diff_snippet": ["<diff hunk line>", ...]   // present only when lines changed > 0
        },
        ...
      ]
    },
    ...
  ]
}
```

### Status letters

| Letter | Meaning |
|--------|---------|
| `A` | Added (new file) |
| `M` | Modified |
| `D` | Deleted |
| `R` | Renamed |
| `C` | Copied |
| `?` | Unknown / could not be determined |

### Diff snippets

- Only present on file entries where `added + deleted > 0`.
- Truncated at **60 lines** per file per commit.
- Extended headers (`---`/`+++`/`index`) are stripped; only `@@` hunk lines
  and change lines are kept.
- A trailing `"... (truncated at 60 lines)"` marker is appended when the
  actual diff exceeded the limit.

---

## How to Run

```bash
# From the project root (IBM/)
python src/git_analyzer.py sample-repository/

# With an explicit output path
python src/git_analyzer.py sample-repository/ output/repo_history.json
```

Requires Python 3.10+ and a system `git` binary on `PATH`.

---

## Error Handling

| Condition | Behaviour |
|-----------|-----------|
| Path does not exist | `ValueError` printed to stderr; exit code 1 |
| Path is not a Git repo | `RuntimeError` printed to stderr; exit code 1 |
| Repository has no commits | `RuntimeError` printed to stderr; exit code 1 |
| `git` not on PATH | `RuntimeError` printed to stderr; exit code 1 |
| Individual commit diff fails | Warning to stderr; commit still included with empty diff |
| Malformed git log block | Warning to stderr; block skipped |

---

## Validation

Run the validation script to confirm the JSON is correct:

```bash
python src/validate_history.py output/repo_history.json
```

The validator checks:
- Exactly 10 commits are present (for our sample repository)
- Every commit has a `hash` and `message`
- Every commit has a `files_changed` list
- Repository-level metadata is present and consistent
