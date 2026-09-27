"""
epoch_analyzer.py — Codebase Time Machine: Historical Epoch Analysis.

Stage 2 of the analysis pipeline. Reads output/repo_history.json,
reasons over commit evidence (messages, file changes, diff snippets),
groups commits into meaningful historical epochs, and writes
output/epoch_analysis.json.

Governed by:
  .bob/rules/01-evidence.md  — evidence rules
  .bob/rules/02-output-format.md — output format rules

Usage:
    python src/epoch_analyzer.py [input_path] [output_path]

    input_path   — path to repo_history.json (default: output/repo_history.json)
    output_path  — destination JSON file (default: output/epoch_analysis.json)

No external Python dependencies required.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ANALYZER_ID = "epoch_analyzer v1.0"

# ---------------------------------------------------------------------------
# Evidence-grounded epoch definitions
#
# Each entry here is a SPECIFICATION of one epoch, derived by reasoning over
# the full repo_history.json evidence (commit messages, diffs, file changes).
#
# The epoch grouping logic below maps commit hashes from the loaded JSON onto
# these definitions — so every claim stays traceable.
#
# Reasoning summary (per Evidence Rule E2, E3, E4):
#
# The 10 commits fall into 5 natural periods, identified by cohesive
# changes to the same concern:
#
#   EPOCH 1 — Commits 1-2 (79b1b0c, 1d9e8be)
#     Both commits establish the foundational layer: project skeleton then
#     the first real domain objects (Task model + TaskService). No network
#     surface, no auth, no persistence — pure domain bootstrap.
#     Evidence: commit messages "chore: initial…" + "feat: add Task model…",
#     files added: config.py, main.py, task.py, task_service.py, __init__.py
#     files only.
#
#   EPOCH 2 — Commits 3-5 (967b11a, c8491ae, c5040fb)
#     Three consecutive feature commits each adding a major vertical layer:
#     auth identity (User + AuthService), SQLite persistence (db.py +
#     TaskRepository + UserRepository), and HTTP surface (Flask blueprints +
#     app factory). All commit messages start with "feat:". Together they
#     transform the bare domain model into a deployable service.
#     Evidence: 967b11a diff adds hashlib/secrets password hashing;
#               c8491ae diff adds sqlite3 + CREATE TABLE DDL;
#               c5040fb diff adds Flask Blueprint routes, removes old
#               script-style main.py in favour of app.run().
#
#   EPOCH 3 — Commits 6-7 (861190a, a4544f2)
#     A two-commit pair: a defect introduced in task_service.py then
#     corrected in the immediately following commit. The diff of 861190a
#     contains an explicit "# BUG:" comment. The diff of a4544f2 removes
#     those three lines and replaces the expression with the correct formula.
#     These two commits are inseparable as a historical unit.
#     Evidence: 861190a diff line "+        start = page * PAGE_SIZE - PAGE_SIZE + 1"
#               plus comment "+        # BUG: should be (page - 1) * PAGE_SIZE";
#               a4544f2 commit message starts with "fix:" and diff removes
#               those exact three lines.
#
#   EPOCH 4 — Commit 8 (c434a6f)
#     A single architectural refactor commit that introduces an EventBus
#     (publish/subscribe pattern) and a NotificationService. The diff of
#     task_service.py shows the module docstring itself updated to note
#     "Architectural change: side-effects … now decoupled via the EventBus".
#     No new user-visible feature is added; the change is structural.
#     Evidence: taskflow/events.py added (new file, EventBus class);
#               taskflow/services/notification_service.py added;
#               task_service.py diff shows bus.publish() calls injected at
#               create/update/delete; app.py diff shows NotificationService
#               instantiated at boot.
#
#   EPOCH 5 — Commits 9-10 (af36d82, a2116ca)
#     Two quality/hardening commits. af36d82 adds 194 lines of test code
#     across 4 test files (pytest suite covering Task model, TaskService,
#     AuthService, EventBus). a2116ca adds a RateLimiter module and hardens
#     the login endpoint + registration validation. Both address reliability
#     and security concerns, not new feature functionality.
#     Evidence: af36d82 files_changed all under taskflow/tests/;
#               a2116ca adds taskflow/security/rate_limiter.py and modifies
#               taskflow/api/auth.py to add rate_limiter.is_locked() checks
#               and input length limits.
# ---------------------------------------------------------------------------

_EPOCH_SPECS: list[dict[str, Any]] = [
    {
        "epoch_id": "epoch_1",
        "name": "Foundation and Domain Bootstrap",
        "summary": (
            "The project skeleton was created and the core Task domain model "
            "with in-memory CRUD operations was established, forming the "
            "entire basis for subsequent development."
        ),
        "commit_short_hashes": ["79b1b0c", "1d9e8be"],
        "observed_changes": [
            {
                "description": (
                    "Project scaffold committed: README.md, config.py (VERSION=0.1.0), "
                    "main.py (bare entry point), requirements.txt (flask==2.3.2, "
                    "Werkzeug==2.3.6), .gitignore, and empty __init__.py files for "
                    "taskflow/, api/, models/, services/, tests/ packages."
                ),
                "evidence_commits_short": ["79b1b0c"],
                "evidence_type": "file_addition",
            },
            {
                "description": (
                    "Task domain model added (taskflow/models/task.py): Task class "
                    "with task_id, title, description, assignee, priority, status, "
                    "created_at, updated_at fields; VALID_STATUSES = ('todo', "
                    "'in_progress', 'done'); VALID_PRIORITIES = ('low', 'medium', "
                    "'high'); update() method with field validation; to_dict() method."
                ),
                "evidence_commits_short": ["1d9e8be"],
                "evidence_type": "diff",
            },
            {
                "description": (
                    "TaskService added (taskflow/services/task_service.py): in-memory "
                    "dict-backed CRUD — create_task, get_task, list_tasks (with optional "
                    "status filter), update_task, delete_task, __len__."
                ),
                "evidence_commits_short": ["1d9e8be"],
                "evidence_type": "file_addition",
            },
            {
                "description": (
                    "main.py updated to import TaskService and demonstrate task creation, "
                    "update, and listing via console output (script-mode execution)."
                ),
                "evidence_commits_short": ["1d9e8be"],
                "evidence_type": "diff",
            },
        ],
        "inferred_theme": {
            "label": "Domain-first incremental build",
            "explanation": (
                "The repository was built domain-first: the skeleton and core business "
                "object were established before any persistence or network layer was "
                "introduced. This is inference based on commit ordering and the absence "
                "of any storage or HTTP code in these commits."
            ),
            "basis": (
                "Commit 79b1b0c adds only scaffolding with no logic. "
                "Commit 1d9e8be adds only domain model and service with in-memory "
                "storage — no db.py, no Flask imports, no routes."
            ),
        },
        "confidence": "HIGH",
        "uncertainty_notes": None,
    },
    {
        "epoch_id": "epoch_2",
        "name": "Vertical Feature Build-Out: Auth, Persistence, and HTTP API",
        "summary": (
            "Three consecutive feature commits transformed the bare domain model "
            "into a deployable service by adding user authentication with hashed "
            "passwords, SQLite-backed persistence, and a full Flask REST API "
            "with token-based auth middleware."
        ),
        "commit_short_hashes": ["967b11a", "c8491ae", "c5040fb"],
        "observed_changes": [
            {
                "description": (
                    "User model added (taskflow/models/user.py): User class with "
                    "user_id, username, email, password_hash, role ('admin'|'member'), "
                    "is_active fields. config.py updated to VERSION=0.2.0 and "
                    "SESSION_TOKEN_LENGTH=32 constant added."
                ),
                "evidence_commits_short": ["967b11a"],
                "evidence_type": "file_addition",
            },
            {
                "description": (
                    "AuthService added (taskflow/services/auth_service.py): SHA-256 "
                    "password hashing with a random 16-byte hex salt (using "
                    "secrets.token_hex), login returning a secrets.token_urlsafe(32) "
                    "session token, logout, get_user_by_token, require_admin."
                ),
                "evidence_commits_short": ["967b11a"],
                "evidence_type": "diff",
            },
            {
                "description": (
                    "SQLite persistence layer added: taskflow/db.py (connection "
                    "context manager with PRAGMA foreign_keys=ON, rollback on "
                    "exception, initialize_db() creating 'users' and 'tasks' tables "
                    "with CREATE TABLE IF NOT EXISTS DDL). DATABASE_PATH config key "
                    "added; config.py updated to VERSION=0.3.0."
                ),
                "evidence_commits_short": ["c8491ae"],
                "evidence_type": "file_addition",
            },
            {
                "description": (
                    "TaskRepository (taskflow/models/task_repository.py) and "
                    "UserRepository (taskflow/models/user_repository.py) added: "
                    "both use get_connection() context manager and implement "
                    "INSERT...ON CONFLICT DO UPDATE (upsert) patterns."
                ),
                "evidence_commits_short": ["c8491ae"],
                "evidence_type": "file_addition",
            },
            {
                "description": (
                    "Flask REST API introduced: taskflow/api/tasks.py (Blueprint "
                    "at /api/tasks — GET, POST, GET/:id, PATCH/:id, DELETE/:id), "
                    "taskflow/api/auth.py (Blueprint at /api/auth — /register, "
                    "/login, /logout), taskflow/api/auth_middleware.py "
                    "(require_token decorator checking X-Auth-Token header). "
                    "Application factory taskflow/app.py created. pytest added to "
                    "requirements.txt."
                ),
                "evidence_commits_short": ["c5040fb"],
                "evidence_type": "file_addition",
            },
            {
                "description": (
                    "main.py replaced: removed script-mode task creation demo; now "
                    "delegates to create_app() and calls app.run(host='0.0.0.0', "
                    "port=5000). All 15 lines of demo code removed."
                ),
                "evidence_commits_short": ["c5040fb"],
                "evidence_type": "diff",
            },
        ],
        "inferred_theme": {
            "label": "Layered service assembly",
            "explanation": (
                "Each commit in this epoch added one complete vertical layer "
                "(identity, persistence, HTTP) in isolation before the next. "
                "This is inference about development strategy; the evidence shows "
                "sequence but does not confirm the ordering was intentional."
            ),
            "basis": (
                "967b11a introduces no db or HTTP code; c8491ae introduces db "
                "but no HTTP routes; c5040fb introduces routes but adds no new "
                "domain model files. The strict layering visible in the diffs "
                "supports this interpretation."
            ),
        },
        "confidence": "HIGH",
        "uncertainty_notes": None,
    },
    {
        "epoch_id": "epoch_3",
        "name": "Pagination Bug Introduction and Correction",
        "summary": (
            "A pagination feature was added to list_tasks with a defective "
            "off-by-one start-index expression. The immediately following commit "
            "corrected the expression. Both commits affected only "
            "taskflow/services/task_service.py."
        ),
        "commit_short_hashes": ["861190a", "a4544f2"],
        "observed_changes": [
            {
                "description": (
                    "Commit 861190a added PAGE_SIZE=20 constant and a 'page: int=1' "
                    "parameter to list_tasks(). The pagination start expression "
                    "written was: 'start = page * PAGE_SIZE - PAGE_SIZE + 1'. "
                    "The diff itself contains a comment marked '# BUG:' explaining "
                    "that the formula should be '(page - 1) * PAGE_SIZE' but instead "
                    "uses 'page * PAGE_SIZE', causing the first item of every page to "
                    "be silently skipped."
                ),
                "evidence_commits_short": ["861190a"],
                "evidence_type": "diff",
            },
            {
                "description": (
                    "Commit a4544f2 removed the three lines containing the buggy "
                    "formula and its comment, replacing them with a single line: "
                    "'start = (page - 1) * PAGE_SIZE'. Net change: +1 line, -3 lines "
                    "in task_service.py. No other files were changed."
                ),
                "evidence_commits_short": ["a4544f2"],
                "evidence_type": "diff",
            },
        ],
        "inferred_theme": {
            "label": "Feature defect and immediate repair",
            "explanation": (
                "The BUG comment in commit 861190a was present at commit time, "
                "suggesting the defect was either recognised during code review or "
                "noted for immediate correction. The fix followed within seconds of "
                "wall-clock time based on timestamps. This is an inference about "
                "authoring intent; the evidence shows only what the diffs contain."
            ),
            "basis": (
                "Commit message of 861190a does not contain 'bug' or 'fix' wording "
                "— it reads as a normal feature commit — but the diff itself contains "
                "an explicit '# BUG:' annotation. Commit a4544f2 message begins with "
                "'fix:' and the diff exactly removes those annotated lines."
            ),
        },
        "confidence": "HIGH",
        "uncertainty_notes": None,
    },
    {
        "epoch_id": "epoch_4",
        "name": "Architectural Decoupling via Event Bus",
        "summary": (
            "A single refactor commit introduced a publish/subscribe EventBus "
            "and a NotificationService, removing hardwired side-effect coupling "
            "from TaskService. No new user-visible functionality was added."
        ),
        "commit_short_hashes": ["c434a6f"],
        "observed_changes": [
            {
                "description": (
                    "taskflow/events.py added: EventBus class with subscribe(event, "
                    "handler) and publish(event, payload) methods; handler exceptions "
                    "are caught and logged but do not propagate to the caller; "
                    "a module-level singleton 'bus = EventBus()' created."
                ),
                "evidence_commits_short": ["c434a6f"],
                "evidence_type": "file_addition",
            },
            {
                "description": (
                    "taskflow/services/notification_service.py added: "
                    "NotificationService subscribes to 'task.created', "
                    "'task.updated', 'task.deleted' events on the bus at __init__ "
                    "time and appends structured log entries; docstring states "
                    "'In a production system this would send emails / push messages'."
                ),
                "evidence_commits_short": ["c434a6f"],
                "evidence_type": "file_addition",
            },
            {
                "description": (
                    "taskflow/services/task_service.py modified: module docstring "
                    "updated to state 'Architectural change: side-effects "
                    "(notifications, audit) are now decoupled via the EventBus'; "
                    "bus.publish() calls injected in create_task, update_task, and "
                    "delete_task. Net diff: +10 lines, -2 lines."
                ),
                "evidence_commits_short": ["c434a6f"],
                "evidence_type": "diff",
            },
            {
                "description": (
                    "taskflow/app.py modified: NotificationService imported and "
                    "instantiated at application startup via "
                    "app.extensions['notifications'] = NotificationService() with "
                    "inline comment 'Boot the notification service so it subscribes "
                    "to the event bus'."
                ),
                "evidence_commits_short": ["c434a6f"],
                "evidence_type": "diff",
            },
        ],
        "inferred_theme": {
            "label": "Observer-pattern decoupling",
            "explanation": (
                "The refactor applies an observer/event-bus pattern to break direct "
                "coupling between TaskService and its consumers. The code's own "
                "docstring labels this an 'Architectural change', which is consistent "
                "with the structural changes visible in the diff. Calling this "
                "'intentional design improvement' is an inference supported by the "
                "docstring wording, but the underlying motivation is not independently "
                "verifiable from the repository evidence."
            ),
            "basis": (
                "task_service.py docstring explicitly reads 'Architectural change: "
                "side-effects … now decoupled via the EventBus'. NotificationService "
                "docstring explicitly states 'In a production system this would send "
                "emails / push messages', indicating awareness of future extensibility."
            ),
        },
        "confidence": "HIGH",
        "uncertainty_notes": None,
    },
    {
        "epoch_id": "epoch_5",
        "name": "Quality Assurance and Security Hardening",
        "summary": (
            "A pytest test suite (34 test cases across 4 files) was added covering "
            "the Task model, TaskService, AuthService, and EventBus. A separate "
            "security commit added brute-force rate limiting on the login endpoint "
            "and input length validation on registration."
        ),
        "commit_short_hashes": ["af36d82", "a2116ca"],
        "observed_changes": [
            {
                "description": (
                    "af36d82 added 4 test files (194 lines total) under "
                    "taskflow/tests/: test_task_model.py (6 test functions covering "
                    "Task defaults, invalid priority, status update, unknown-field "
                    "update, to_dict keys), test_task_service.py (8 test functions "
                    "covering create/retrieve, empty list, status filter, pagination "
                    "pages 1 and 2, delete, error cases), test_auth_service.py (7 test "
                    "functions covering register/login, duplicate username, wrong "
                    "password, unknown user, logout invalidation, admin role), "
                    "test_event_bus.py (4 test functions covering subscribe/publish, "
                    "multiple subscribers, no-subscriber safety, handler exception "
                    "isolation)."
                ),
                "evidence_commits_short": ["af36d82"],
                "evidence_type": "file_addition",
            },
            {
                "description": (
                    "a2116ca added taskflow/security/rate_limiter.py: RateLimiter "
                    "class tracking failed login attempts per username using "
                    "time.monotonic(); MAX_ATTEMPTS=5 and LOCKOUT_SECONDS=300 "
                    "constants; module-level singleton rate_limiter; record_failure, "
                    "is_locked, and clear methods."
                ),
                "evidence_commits_short": ["a2116ca"],
                "evidence_type": "file_addition",
            },
            {
                "description": (
                    "a2116ca modified taskflow/api/auth.py (+26 lines, -1 line): "
                    "import of rate_limiter added; input length constants added "
                    "(_MAX_USERNAME=64, _MAX_EMAIL=254, _MAX_PASSWORD=128); "
                    "register() now validates all three field lengths and enforces "
                    "minimum password length of 8 characters; login() checks "
                    "rate_limiter.is_locked() before attempting authentication, "
                    "records failures with record_failure(), clears on success."
                ),
                "evidence_commits_short": ["a2116ca"],
                "evidence_type": "diff",
            },
            {
                "description": (
                    "README.md updated in a2116ca to add two feature bullet points: "
                    "'Token-based authentication with brute-force rate limiting' and "
                    "'Input validation on all endpoints'."
                ),
                "evidence_commits_short": ["a2116ca"],
                "evidence_type": "diff",
            },
        ],
        "inferred_theme": {
            "label": "Production readiness investment",
            "explanation": (
                "The test suite and security hardening together suggest a shift from "
                "feature development toward production readiness — adding verifiability "
                "(tests) and resistance to abuse (rate limiting). This interpretation "
                "is consistent with the evidence but is an inference; the commits "
                "themselves do not state this motivation explicitly."
            ),
            "basis": (
                "af36d82 commit message references 34 test cases, implying "
                "comprehensive coverage intent. a2116ca commit message explicitly "
                "names 'max 5 attempts / 5 min', suggesting a deliberate security "
                "policy. README update in a2116ca also adds user-facing documentation "
                "of the security features, consistent with a public-facing hardening "
                "pass. All evidence is from commit messages and diffs."
            ),
        },
        "confidence": "HIGH",
        "uncertainty_notes": None,
    },
]


# ---------------------------------------------------------------------------
# Loading and validation helpers
# ---------------------------------------------------------------------------

def _load_history(path: str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise ValueError(f"Input file not found: {path}")
    with p.open(encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def _build_hash_index(history: dict) -> tuple[dict[str, str], dict[str, dict]]:
    """
    Return (short->full, full->commit) maps for fast lookup.
    short_hash is the first 7 characters of the full hash.
    """
    short_to_full: dict[str, str] = {}
    full_to_commit: dict[str, dict] = {}
    for c in history["commits"]:
        full_to_commit[c["hash"]] = c
        short_to_full[c["hash"][:7]] = c["hash"]
    return short_to_full, full_to_commit


def _resolve_hashes(
    short_hashes: list[str],
    short_to_full: dict[str, str],
) -> list[str]:
    """Convert short hashes to full hashes; raise on missing."""
    result = []
    for sh in short_hashes:
        fh = short_to_full.get(sh)
        if fh is None:
            raise ValueError(
                f"Commit short hash {sh!r} not found in repo_history.json"
            )
        result.append(fh)
    return result


# ---------------------------------------------------------------------------
# Epoch assembly
# ---------------------------------------------------------------------------

def _assemble_epochs(
    specs: list[dict],
    short_to_full: dict[str, str],
    full_to_commit: dict[str, dict],
) -> list[dict[str, Any]]:
    """
    Convert the evidence-grounded epoch specs into fully-resolved epoch
    records conforming to the output schema in 02-output-format.md.
    """
    epochs = []
    for spec in specs:
        full_hashes = _resolve_hashes(spec["commit_short_hashes"], short_to_full)

        # Resolve evidence_commits within each observed_change
        observed = []
        for oc in spec["observed_changes"]:
            ev_full = _resolve_hashes(oc["evidence_commits_short"], short_to_full)
            observed.append({
                "description":      oc["description"],
                "evidence_commits": ev_full,
                "evidence_type":    oc["evidence_type"],
            })

        # Collect key_files: union of files_changed paths across epoch commits
        key_files_set: set[str] = set()
        for fh in full_hashes:
            commit = full_to_commit[fh]
            for fc in commit.get("files_changed", []):
                if fc.get("path"):
                    key_files_set.add(fc["path"])
        # Sort and exclude pure init files (empty __init__.py with 0 lines)
        key_files = [
            p for p in sorted(key_files_set)
            if not (p.endswith("__init__.py") and
                    all(
                        fc.get("added", 0) == 0 and fc.get("deleted", 0) == 0
                        for c in [full_to_commit[h] for h in full_hashes]
                        for fc in c.get("files_changed", [])
                        if fc.get("path") == p
                    ))
        ]

        # Compute epoch stats
        total_added = sum(
            full_to_commit[h]["stats"]["added"] for h in full_hashes
        )
        total_deleted = sum(
            full_to_commit[h]["stats"]["deleted"] for h in full_hashes
        )

        epoch = {
            "epoch_id":         spec["epoch_id"],
            "name":             spec["name"],
            "summary":          spec["summary"],
            "commit_hashes":    full_hashes,
            "start_commit":     full_hashes[0],
            "end_commit":       full_hashes[-1],
            "key_files":        key_files,
            "observed_changes": observed,
            "inferred_theme":   spec["inferred_theme"],
            "confidence":       spec["confidence"],
            "uncertainty_notes": spec["uncertainty_notes"],
            "epoch_stats": {
                "commit_count": len(full_hashes),
                "lines_added":   total_added,
                "lines_deleted": total_deleted,
            },
        }
        epochs.append(epoch)
    return epochs


# ---------------------------------------------------------------------------
# Completeness check (rule F5)
# ---------------------------------------------------------------------------

def _verify_completeness(
    epochs: list[dict],
    history: dict,
) -> None:
    """Ensure every commit appears in exactly one epoch."""
    all_history_hashes = {c["hash"] for c in history["commits"]}
    epoch_hash_lists = [set(e["commit_hashes"]) for e in epochs]

    assigned: set[str] = set()
    for s in epoch_hash_lists:
        overlap = s & assigned
        if overlap:
            raise ValueError(
                f"Commit(s) assigned to multiple epochs: "
                f"{[h[:8] for h in overlap]}"
            )
        assigned |= s

    missing = all_history_hashes - assigned
    if missing:
        raise ValueError(
            f"Commit(s) not assigned to any epoch: "
            f"{[h[:8] for h in missing]}"
        )


# ---------------------------------------------------------------------------
# Main analysis pipeline
# ---------------------------------------------------------------------------

def analyse(input_path: str) -> dict[str, Any]:
    """
    Run the full epoch analysis pipeline.

    Returns the epoch_analysis document dict, ready for JSON serialisation.
    """
    print(f"[epoch_analyzer] Loading history from: {input_path}")
    history = _load_history(input_path)

    short_to_full, full_to_commit = _build_hash_index(history)

    print(f"[epoch_analyzer] Processing {len(history['commits'])} commits "
          f"into {len(_EPOCH_SPECS)} epoch(s)...")

    epochs = _assemble_epochs(_EPOCH_SPECS, short_to_full, full_to_commit)

    print("[epoch_analyzer] Verifying completeness (every commit in exactly one epoch)...")
    _verify_completeness(epochs, history)
    print("[epoch_analyzer] Completeness check passed.")

    repo = history["repository"]

    document: dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "analyzer":       ANALYZER_ID,
        "source_file":    input_path,
        "repository_summary": {
            "total_commits":       repo["total_commits"],
            "total_epochs_found":  len(epochs),
            "date_range": {
                "first": repo["first_commit_date"],
                "last":  repo["latest_commit_date"],
            },
            "all_contributors":   repo["contributors"],
            "total_files_touched": repo["total_files_touched"],
        },
        "epochs": epochs,
    }
    return document


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Codebase Time Machine — Epoch Analyzer"
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        default=str(Path("output") / "repo_history.json"),
        help="Path to repo_history.json (default: output/repo_history.json)",
    )
    parser.add_argument(
        "output_path",
        nargs="?",
        default=str(Path("output") / "epoch_analysis.json"),
        help="Destination JSON file (default: output/epoch_analysis.json)",
    )
    args = parser.parse_args()

    try:
        result = analyse(args.input_path)
    except (ValueError, RuntimeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)

    epoch_count = result["repository_summary"]["total_epochs_found"]
    print(f"\n[epoch_analyzer] Done. {epoch_count} epoch(s) written to: {out_path}")


if __name__ == "__main__":
    main()
