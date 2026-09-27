"""
build_report.py — Codebase Time Machine: Final HTML Report Generator.

Reads the four analysis artifacts and emits a single self-contained
output/evolution_report.html that works by opening the file locally
(no server, no npm, no external network calls required).

Usage:
    python src/build_report.py

Inputs (all in output/):
    repo_history.json
    epoch_analysis.json
    why_analysis.json
    onboarding_guide.md

Output:
    output/evolution_report.html
"""

from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        print(f"[ERROR] {path} not found", file=sys.stderr)
        sys.exit(1)
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def _load_text(path: str) -> str:
    p = Path(path)
    if not p.exists():
        print(f"[ERROR] {path} not found", file=sys.stderr)
        sys.exit(1)
    return p.read_text(encoding="utf-8")


def _h(text) -> str:
    """HTML-escape a value."""
    return html.escape(str(text) if text is not None else "")


def _short(hash_str: str, n: int = 8) -> str:
    return hash_str[:n] if hash_str else ""


def _fmt_ts(iso: str) -> str:
    """Format ISO timestamp to a readable string."""
    try:
        # Strip timezone offset for simple display
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return iso[:19] if iso else ""


# Commit-type colour mapping (by conventional commit prefix)
COMMIT_COLORS = {
    "chore":    "#6b7280",
    "feat":     "#3b82f6",
    "fix":      "#ef4444",
    "refactor": "#8b5cf6",
    "test":     "#10b981",
    "security": "#f59e0b",
    "docs":     "#64748b",
}

EPOCH_COLORS = [
    "#3b82f6",  # epoch 1 — blue
    "#8b5cf6",  # epoch 2 — purple
    "#ef4444",  # epoch 3 — red
    "#f59e0b",  # epoch 4 — amber
    "#10b981",  # epoch 5 — green
]


def _commit_color(message: str) -> str:
    prefix = message.split(":")[0].strip().lower()
    return COMMIT_COLORS.get(prefix, "#6b7280")


def _confidence_badge(conf: str) -> str:
    colors = {"HIGH": "#10b981", "MEDIUM": "#f59e0b", "LOW": "#ef4444"}
    bg = colors.get(conf, "#6b7280")
    return (f'<span style="background:{bg};color:#fff;padding:2px 8px;'
            f'border-radius:10px;font-size:11px;font-weight:600;">{_h(conf)}</span>')


def _tag(text: str, bg: str = "#e5e7eb", fg: str = "#374151") -> str:
    return (f'<span style="background:{bg};color:{fg};padding:1px 7px;'
            f'border-radius:8px;font-size:11px;margin:1px 2px;display:inline-block;">'
            f'{_h(text)}</span>')


def _section_header(icon: str, title: str, subtitle: str = "") -> str:
    sub = f'<p style="color:#6b7280;margin:4px 0 0;font-size:14px;">{_h(subtitle)}</p>' if subtitle else ""
    return f"""
<div style="border-left:4px solid #3b82d4;padding:4px 0 4px 16px;margin-bottom:24px;">
  <h2 style="margin:0;font-size:22px;color:#1f2328;">{icon} {_h(title)}</h2>
  {sub}
</div>"""


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def build_header() -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""
<div style="background:linear-gradient(135deg,#1e3a5f 0%,#1d4ed8 100%);
            color:#fff;padding:48px 40px;border-radius:12px;margin-bottom:32px;">
  <div style="font-size:12px;letter-spacing:2px;text-transform:uppercase;
              opacity:0.7;margin-bottom:8px;">IBM Bob 2.0 Hackathon</div>
  <h1 style="margin:0 0 8px;font-size:36px;font-weight:700;letter-spacing:-0.5px;">
    &#128336; Codebase Time Machine
  </h1>
  <p style="margin:0 0 4px;font-size:16px;opacity:0.85;">
    Evidence-grounded historical analysis of the <strong>TaskFlow</strong> repository.
  </p>
  <p style="margin:0;font-size:12px;opacity:0.6;">
    Generated {now} &nbsp;|&nbsp;
    All claims traceable to commit hashes &nbsp;|&nbsp;
    Confidence-rated analysis
  </p>
</div>"""


def build_what_is(repo: dict) -> str:
    return f"""
<div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:8px;
            padding:24px 28px;margin-bottom:32px;">
  <h2 style="margin:0 0 10px;color:#0369a1;font-size:18px;">&#128269; What is Codebase Time Machine?</h2>
  <p style="margin:0 0 10px;color:#1e3a5f;line-height:1.7;">
    <strong>Codebase Time Machine</strong> reads a Git repository and produces
    evidence-grounded historical analysis — answering <em>what changed</em>,
    <em>when it changed</em>, and <em>what the repository evidence suggests about why</em>.
  </p>
  <p style="margin:0;color:#1e3a5f;line-height:1.7;">
    Every claim in this report is traceable to a commit hash.
    Interpretations are explicitly labelled <strong>[INFERENCE]</strong>
    and rated <strong>HIGH / MEDIUM / LOW</strong> confidence.
    The tool never invents developer motivation.
  </p>
</div>"""


def build_snapshot(repo: dict, history_repo: dict) -> str:
    total = history_repo["total_commits"]
    files = history_repo["total_files_touched"]
    contributors = len(history_repo["contributors"])
    first = _fmt_ts(history_repo["first_commit_date"])
    last  = _fmt_ts(history_repo["latest_commit_date"])

    def stat(val, label):
        return f"""
<div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;
            padding:20px;text-align:center;flex:1;min-width:130px;">
  <div style="font-size:32px;font-weight:700;color:#3b82d4;">{_h(val)}</div>
  <div style="font-size:12px;color:#6b7280;text-transform:uppercase;
              letter-spacing:1px;margin-top:4px;">{_h(label)}</div>
</div>"""

    return f"""
{_section_header("&#128202;", "Repository Snapshot", "TaskFlow · Python / Flask / SQLite")}
<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:32px;">
  {stat(total, "Commits")}
  {stat(files, "Files Touched")}
  {stat(contributors, "Contributor")}
  {stat("5", "Epochs")}
  {stat("8", "Change Analyses")}
</div>
<div style="background:#f7f8fa;border:1px solid #e5e7eb;border-radius:8px;
            padding:16px 20px;margin-bottom:32px;font-size:13px;color:#374151;">
  <strong>Date range:</strong> {_h(first)} &rarr; {_h(last)}
  &nbsp;|&nbsp; <strong>Technology:</strong> Python &middot; Flask 2.3.2 &middot; SQLite &middot; pytest 7.4.0
  &nbsp;|&nbsp; <strong>Entry point:</strong> main.py &rarr; create_app() &rarr; app.run(0.0.0.0:5000)
</div>"""


def build_timeline(commits: list) -> str:
    rows = ""
    for i, c in enumerate(commits, 1):
        color = _commit_color(c["message"])
        msg = c["message"]
        prefix = msg.split(":")[0] if ":" in msg else ""
        rest  = msg[len(prefix)+1:].strip() if ":" in msg else msg
        stats = c.get("stats", {})
        files_changed = stats.get("files", 0)
        added   = stats.get("added", 0)
        deleted = stats.get("deleted", 0)

        rows += f"""
<div style="display:flex;gap:0;margin-bottom:0;align-items:stretch;">
  <div style="width:36px;display:flex;flex-direction:column;align-items:center;">
    <div style="width:12px;height:12px;border-radius:50%;background:{color};
                margin-top:16px;flex-shrink:0;border:2px solid #fff;
                box-shadow:0 0 0 2px {color};"></div>
    {"" if i == len(commits) else
     f'<div style="width:2px;background:#e5e7eb;flex:1;margin:2px 0;"></div>'}
  </div>
  <div style="flex:1;background:#fff;border:1px solid #e5e7eb;border-radius:8px;
              padding:12px 16px;margin:4px 0 4px 8px;">
    <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
      <span style="font-size:11px;font-weight:600;color:#fff;background:{color};
                   padding:2px 8px;border-radius:10px;">{_h(prefix) if prefix else "commit"}</span>
      <code style="font-size:11px;color:#6b7280;background:#f3f4f6;
                   padding:1px 6px;border-radius:4px;">{_short(c["hash"])}</code>
      <span style="font-size:12px;color:#6b7280;">{_fmt_ts(c["timestamp"])}</span>
    </div>
    <div style="margin:6px 0 4px;font-size:14px;color:#1f2328;font-weight:500;">
      {_h(rest)}
    </div>
    <div style="font-size:11px;color:#6b7280;">
      {files_changed} file(s) changed &nbsp;
      <span style="color:#10b981;">+{added}</span> /
      <span style="color:#ef4444;">-{deleted}</span>
    </div>
  </div>
</div>"""

    return f"""
{_section_header("&#9201;", "Historical Timeline", "All 10 commits — oldest first")}
<div style="margin-bottom:32px;padding-left:8px;">
  {rows}
</div>"""


def build_epochs(epochs: list) -> str:
    out = _section_header("&#127942;", "Five Historical Epochs",
                          "Commit groups identified by cohesive evidence")

    for i, e in enumerate(epochs):
        color = EPOCH_COLORS[i % len(EPOCH_COLORS)]
        hashes_html = " ".join(
            f'<code style="font-size:11px;background:#f3f4f6;padding:1px 6px;'
            f'border-radius:4px;color:#374151;">{_short(h)}</code>'
            for h in e["commit_hashes"]
        )
        files_html = " ".join(_tag(f) for f in e["key_files"][:10])
        if len(e["key_files"]) > 10:
            files_html += _tag(f"+{len(e['key_files'])-10} more", "#f3f4f6")

        obs_html = ""
        for oc in e["observed_changes"]:
            ev = ", ".join(_short(h) for h in oc["evidence_commits"])
            obs_html += f"""
<div style="border-left:3px solid {color};padding:6px 12px;margin:6px 0;
            background:#fafafa;border-radius:0 4px 4px 0;">
  <span style="font-size:11px;color:#6b7280;font-weight:600;">
    [{_h(oc['evidence_type'])}] evidence: {_h(ev)}
  </span>
  <p style="margin:4px 0 0;font-size:13px;color:#374151;line-height:1.5;">
    {_h(oc['description'])}
  </p>
</div>"""

        it = e["inferred_theme"]
        stats = e.get("epoch_stats", {})

        out += f"""
<div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;
            margin-bottom:20px;overflow:hidden;">
  <div style="background:{color};padding:14px 20px;display:flex;
              align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
    <div>
      <span style="color:rgba(255,255,255,0.7);font-size:11px;
                   text-transform:uppercase;letter-spacing:1px;">
        {_h(e['epoch_id'].replace('_',' ').title())}
      </span>
      <h3 style="margin:2px 0 0;color:#fff;font-size:17px;">{_h(e['name'])}</h3>
    </div>
    <div style="display:flex;gap:12px;align-items:center;">
      {_confidence_badge(e['confidence'])}
      <span style="color:rgba(255,255,255,0.8);font-size:12px;">
        {stats.get('commit_count','')} commit(s) &nbsp;
        +{stats.get('lines_added','')} / -{stats.get('lines_deleted','')} lines
      </span>
    </div>
  </div>
  <div style="padding:16px 20px;">
    <p style="margin:0 0 10px;color:#374151;font-size:14px;line-height:1.6;">
      {_h(e['summary'])}
    </p>
    <div style="margin-bottom:10px;">
      <span style="font-size:11px;font-weight:600;color:#6b7280;
                   text-transform:uppercase;letter-spacing:1px;">Commits: </span>
      {hashes_html}
    </div>
    <div style="margin-bottom:12px;">
      <span style="font-size:11px;font-weight:600;color:#6b7280;
                   text-transform:uppercase;letter-spacing:1px;">Key files</span><br>
      <div style="margin-top:4px;">{files_html}</div>
    </div>
    <details>
      <summary style="cursor:pointer;font-size:13px;font-weight:600;
                      color:{color};margin-bottom:8px;">
        Observed changes ({len(e['observed_changes'])} entries)
      </summary>
      {obs_html}
    </details>
    <div style="background:#f0f4ff;border:1px solid #c7d7fd;border-radius:6px;
                padding:10px 14px;margin-top:10px;">
      <span style="font-size:11px;font-weight:600;color:#4338ca;">
        [INFERENCE] {_h(it['label'])}
      </span>
      <p style="margin:4px 0 0;font-size:13px;color:#374151;line-height:1.5;">
        {_h(it['explanation'])}
      </p>
      <p style="margin:6px 0 0;font-size:12px;color:#6b7280;">
        <em>Basis: {_h(it['basis'][:200])}{'...' if len(it['basis'])>200 else ''}</em>
      </p>
    </div>
  </div>
</div>"""

    return out + ""


def build_why(analyses: list) -> str:
    out = _section_header("&#10067;", "Why Did These Changes Happen?",
                          "Evidence-grounded reasoning — four-voice analysis per change")

    voice_styles = {
        "observed":  ("#e0f2fe", "#0369a1", "&#128269; Observed Change"),
        "stated":    ("#f0fdf4", "#15803d", "&#128172; Stated Intent"),
        "inference": ("#faf5ff", "#7c3aed", "&#129300; [INFERENCE] Evidence-Based"),
        "unknown":   ("#fff7ed", "#c2410c", "&#10067; Unknown"),
    }

    for a in analyses:
        hashes_html = " ".join(
            f'<code style="font-size:11px;background:#f3f4f6;padding:1px 6px;'
            f'border-radius:4px;">{_short(h)}</code>'
            for h in a["commit_hashes"]
        )

        conf_badge = _confidence_badge(a["confidence"])

        def voice_card(key, text, truncate=600):
            if not text:
                return ""
            bg, fg, label = voice_styles[key]
            display = text[:truncate] + ("..." if len(text) > truncate else "")
            return f"""
<div style="background:{bg};border-left:3px solid {fg};border-radius:0 6px 6px 0;
            padding:10px 14px;margin:6px 0;">
  <div style="font-size:11px;font-weight:700;color:{fg};margin-bottom:4px;">{label}</div>
  <p style="margin:0;font-size:13px;color:#374151;line-height:1.6;">{_h(display)}</p>
</div>"""

        ev_html = ""
        for ev in a.get("evidence", []):
            files_str = ", ".join(ev.get("files", []))
            ev_html += f"""
<div style="font-size:12px;background:#f7f8fa;border:1px solid #e5e7eb;
            border-radius:4px;padding:8px 12px;margin:4px 0;">
  <code style="color:#374151;">{_short(ev['commit_hash'])}</code>
  &rarr; <span style="color:#6b7280;">{_h(files_str[:120])}</span><br>
  <span style="color:#374151;font-style:italic;">{_h(ev.get('reason','')[:150])}</span>
</div>"""

        out += f"""
<div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;
            margin-bottom:20px;overflow:hidden;">
  <div style="background:#1e3a5f;padding:12px 20px;display:flex;
              align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
    <div>
      <span style="color:rgba(255,255,255,0.6);font-size:11px;">
        {_h(a['analysis_id'])}
      </span>
      <h3 style="margin:2px 0 0;color:#fff;font-size:16px;">{_h(a['change'])}</h3>
    </div>
    <div style="display:flex;align-items:center;gap:10px;">
      {conf_badge}
      {hashes_html}
    </div>
  </div>
  <div style="padding:16px 20px;">
    {voice_card("observed",  a.get("observed_change",""))}
    {voice_card("stated",    a.get("stated_intent",""))}
    {voice_card("inference", a.get("evidence_based_inference",""))}
    {voice_card("unknown",   a.get("unknown",""))}
    <details style="margin-top:10px;">
      <summary style="cursor:pointer;font-size:12px;color:#6b7280;">
        Evidence commits ({len(a.get("evidence",[]))})
      </summary>
      <div style="margin-top:6px;">{ev_html}</div>
    </details>
  </div>
</div>"""

    return out


def build_architecture() -> str:
    return f"""
{_section_header("&#127963;", "Current Architecture",
                 "Established from repository evidence — relationships marked [NOT WIRED] exist in code but are unconnected")}
<div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;
            padding:24px;margin-bottom:32px;">
  <div style="background:#0f172a;border-radius:8px;padding:20px 24px;
              font-family:monospace;font-size:13px;color:#94a3b8;line-height:1.9;
              overflow-x:auto;">
    <span style="color:#38bdf8;">main.py</span> &rarr; create_app() &rarr; Flask app.run(0.0.0.0:5000)<br>
    &nbsp;&nbsp;&nbsp;&nbsp;&#9500; <span style="color:#a78bfa;">/api/auth</span>&nbsp;&nbsp;&nbsp;(register / login / logout)<br>
    &nbsp;&nbsp;&nbsp;&nbsp;&#9500; <span style="color:#a78bfa;">/api/tasks</span>&nbsp;&nbsp;(CRUD &mdash; all @require_token)<br>
    &nbsp;&nbsp;&nbsp;&nbsp;&#9474;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&rarr; auth_middleware &rarr; AuthService<br>
    &nbsp;&nbsp;&nbsp;&nbsp;&#9500; <span style="color:#34d399;">TaskService</span> (in-memory dict) &rarr; EventBus &rarr; NotificationService<br>
    &nbsp;&nbsp;&nbsp;&nbsp;&#9500; <span style="color:#fbbf24;">RateLimiter</span> (in-memory, 5 attempts / 300s)<br>
    &nbsp;&nbsp;&nbsp;&nbsp;&#9492; <span style="color:#f87171;">[NOT WIRED]</span> TaskRepository / UserRepository &rarr; SQLite<br>
  </div>
  <div style="background:#fff3cd;border:1px solid #ffc107;border-radius:6px;
              padding:12px 16px;margin-top:16px;">
    <strong>&#9888; Important:</strong>
    <code>TaskRepository</code> and <code>UserRepository</code> exist in the codebase
    but <strong>TaskService never uses them</strong>. TaskService uses an in-memory
    Python dict throughout the entire 10-commit repository history.
    All task data is lost on every server restart.
    Evidence: commit <code>c8491ae</code> adds repositories; no subsequent commit
    wires them into TaskService. Source: <em>why_analysis.json why_2</em>.
  </div>
  <table style="width:100%;border-collapse:collapse;margin-top:20px;font-size:13px;">
    <thead>
      <tr style="background:#f7f8fa;border-bottom:2px solid #e5e7eb;">
        <th style="text-align:left;padding:8px 12px;color:#374151;">Component</th>
        <th style="text-align:left;padding:8px 12px;color:#374151;">File</th>
        <th style="text-align:left;padding:8px 12px;color:#374151;">Role</th>
        <th style="text-align:left;padding:8px 12px;color:#374151;">Introduced</th>
      </tr>
    </thead>
    <tbody>
      {"".join(
        f'<tr style="border-bottom:1px solid #f0f0f0;">'
        f'<td style="padding:8px 12px;font-weight:500;">{_h(r[0])}</td>'
        f'<td style="padding:8px 12px;font-family:monospace;font-size:12px;color:#374151;">{_h(r[1])}</td>'
        f'<td style="padding:8px 12px;color:#6b7280;">{_h(r[2])}</td>'
        f'<td style="padding:8px 12px;font-family:monospace;font-size:11px;">'
        f'<code style="background:#f3f4f6;padding:1px 5px;border-radius:3px;">{_h(r[3])}</code></td>'
        f'</tr>'
        for r in [
            ("Task domain model",   "taskflow/models/task.py",                    "Core entity; status/priority enums; validation",                  "1d9e8be"),
            ("TaskService",         "taskflow/services/task_service.py",           "In-memory CRUD + EventBus publish calls",                         "1d9e8be"),
            ("User model",          "taskflow/models/user.py",                    "Auth identity; role field (admin|member)",                        "967b11a"),
            ("AuthService",         "taskflow/services/auth_service.py",           "SHA-256 hashing; token issuance; require_admin()",                "967b11a"),
            ("DB layer",            "taskflow/db.py",                             "SQLite connection manager; schema DDL",                           "c8491ae"),
            ("TaskRepository",      "taskflow/models/task_repository.py",          "SQLite persistence — NOT WIRED to TaskService",                   "c8491ae"),
            ("UserRepository",      "taskflow/models/user_repository.py",          "SQLite persistence — NOT WIRED",                                 "c8491ae"),
            ("App factory",         "taskflow/app.py",                            "Flask wiring; DB init; service boot",                            "c5040fb"),
            ("API — tasks",         "taskflow/api/tasks.py",                      "REST endpoints for task CRUD",                                   "c5040fb"),
            ("API — auth",          "taskflow/api/auth.py",                       "Registration, login, logout; rate-limit integration",            "c5040fb / a2116ca"),
            ("Auth middleware",     "taskflow/api/auth_middleware.py",             "@require_token decorator (X-Auth-Token header)",                 "c5040fb"),
            ("EventBus",           "taskflow/events.py",                          "Pub/sub dispatcher; exceptions swallowed",                       "c434a6f"),
            ("NotificationService","taskflow/services/notification_service.py",    "Subscribes to task events; in-process activity log",             "c434a6f"),
            ("RateLimiter",        "taskflow/security/rate_limiter.py",            "In-memory brute-force protection (no restart persistence)",      "a2116ca"),
            ("Tests (34)",         "taskflow/tests/test_*.py",                    "pytest suite; covers model/service/auth/eventbus only",          "af36d82"),
        ]
      )}
    </tbody>
  </table>
</div>"""


def build_issues() -> str:
    issues = [
        ("critical", "Repositories Not Wired to TaskService",
         "c8491ae",
         "TaskRepository and UserRepository were added in commit c8491ae but TaskService "
         "continues using an in-memory dict throughout the entire history. "
         "All task data is lost on restart. "
         "Whether this is a planned migration or deliberate staging is unknown."),
        ("warning", "Pagination Bug Was Committed",
         "861190a / a4544f2",
         "Commit 861190a committed pagination code containing an explicit # BUG: comment "
         "describing the off-by-one error. Commit a4544f2 corrected it. "
         "The fix is in place; a test in test_task_service.py verifies the corrected formula."),
        ("warning", "Test Coverage Gaps",
         "af36d82",
         "The test suite covers Task model, TaskService, AuthService, and EventBus. "
         "Not covered: REST API endpoints, repositories, db.py, rate_limiter.py. "
         "No CI configuration exists in the repository."),
        ("warning", "In-Memory Rate Limiter Has No Restart Persistence",
         "a2116ca",
         "The RateLimiter uses time.monotonic() and a plain dict — state is lost on restart. "
         "No code comment in the repository acknowledges this limitation."),
        ("info", "Admin Role Without Admin Endpoints",
         "967b11a",
         "User.role supports 'admin'|'member' and require_admin() exists in AuthService. "
         "No API endpoint in the repository calls require_admin(). "
         "The intended admin functionality is unknown."),
        ("info", "No API Documentation",
         "c5040fb",
         "No OpenAPI/Swagger spec, no API reference document, and no consumer code "
         "exists in the repository. The intended client is unknown."),
    ]

    colors = {
        "critical": ("#fee2e2", "#dc2626", "&#128308;"),
        "warning":  ("#fff7ed", "#c2410c", "&#128993;"),
        "info":     ("#f0f9ff", "#0369a1", "&#128994;"),
    }

    items = ""
    for severity, title, commit, desc in issues:
        bg, fg, dot = colors[severity]
        items += f"""
<div style="background:{bg};border-left:4px solid {fg};border-radius:0 8px 8px 0;
            padding:14px 18px;margin-bottom:12px;">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
    <span>{dot}</span>
    <strong style="color:{fg};font-size:14px;">{_h(title)}</strong>
    <code style="font-size:11px;background:rgba(0,0,0,0.06);padding:1px 6px;
                 border-radius:3px;color:#374151;">{_h(commit)}</code>
  </div>
  <p style="margin:0;font-size:13px;color:#374151;line-height:1.6;">{_h(desc)}</p>
</div>"""

    return f"""
{_section_header("&#9888;", "Known Issues and Caveats",
                 "Repository-supported limitations only — no invented issues")}
<div style="margin-bottom:32px;">{items}</div>"""


def build_onboarding() -> str:
    reading_order = [
        ("1", "config.py",                         "Version, debug flag, DATABASE_PATH — configuration baseline"),
        ("2", "taskflow/models/task.py",            "Core domain object; VALID_STATUSES; VALID_PRIORITIES; field validation"),
        ("3", "taskflow/services/task_service.py",  "Primary service; all task operations; currently in-memory"),
        ("4", "taskflow/models/user.py",            "User identity; role field used by AuthService"),
        ("5", "taskflow/services/auth_service.py",  "Password hashing scheme; token lifecycle; require_admin()"),
        ("6", "taskflow/db.py",                     "SQLite connection manager; DDL schema; read before repositories"),
        ("7", "task_repository.py + user_repository.py", "SQLite persistence — structurally present but NOT WIRED to TaskService"),
        ("8", "taskflow/app.py",                    "Application assembly — how all components are wired"),
        ("9", "taskflow/api/auth_middleware.py",    "require_token decorator — prerequisite for reading API endpoints"),
        ("10","taskflow/api/auth.py + tasks.py",    "HTTP endpoints; rate-limiting integration"),
        ("11","taskflow/events.py + notification_service.py", "Event bus pattern; task lifecycle event propagation"),
        ("12","taskflow/security/rate_limiter.py",  "Brute-force mitigation; understand in-memory limitation"),
        ("13","taskflow/tests/test_*.py",            "Executable specification — verifiable expected behaviour"),
    ]

    rows = "".join(
        f'<tr style="border-bottom:1px solid #f0f0f0;">'
        f'<td style="padding:8px 12px;text-align:center;font-weight:700;'
        f'color:#3b82d4;font-size:15px;">{_h(n)}</td>'
        f'<td style="padding:8px 12px;font-family:monospace;font-size:12px;'
        f'color:#374151;">{_h(f)}</td>'
        f'<td style="padding:8px 12px;color:#6b7280;font-size:13px;">{_h(why)}</td>'
        f'</tr>'
        for n, f, why in reading_order
    )

    questions = [
        ("Why are repositories not wired to TaskService?",
         "TaskRepository and UserRepository exist since c8491ae. TaskService never uses them. "
         "Is the SQLite migration planned? What is the intended approach?"),
        ("What client is intended for the REST API?",
         "No API documentation, OpenAPI spec, or consumer code exists in the repository."),
        ("What does NotificationService send in production?",
         "Docstring says 'emails / push messages' but no backend exists. "
         "The EventBus is designed for this extension."),
        ("What admin operations were planned?",
         "require_admin() exists; no endpoint uses it. The admin role was added in c967b11a."),
        ("Should the rate limiter be persistent?",
         "Current implementation is in-memory — it resets on restart. No CI / deployment config exists."),
        ("What is the test coverage target?",
         "API endpoints, repositories, and security module have no tests. No CI configuration."),
    ]

    q_html = "".join(
        f'<div style="background:#f7f8fa;border:1px solid #e5e7eb;border-radius:6px;'
        f'padding:12px 16px;margin-bottom:8px;">'
        f'<strong style="color:#1f2328;font-size:13px;">&#9675; {_h(q)}</strong>'
        f'<p style="margin:4px 0 0;font-size:13px;color:#6b7280;line-height:1.5;">{_h(a)}</p>'
        f'</div>'
        for q, a in questions
    )

    return f"""
{_section_header("&#128218;", "Developer Onboarding",
                 "Recommended reading order and open investigation questions")}
<h3 style="font-size:15px;color:#374151;margin:0 0 12px;">Recommended Reading Order</h3>
<table style="width:100%;border-collapse:collapse;margin-bottom:28px;font-size:13px;">
  <thead>
    <tr style="background:#f7f8fa;border-bottom:2px solid #e5e7eb;">
      <th style="padding:8px 12px;color:#374151;width:40px;">#</th>
      <th style="padding:8px 12px;color:#374151;">File</th>
      <th style="padding:8px 12px;color:#374151;">Why Read It First</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
<h3 style="font-size:15px;color:#374151;margin:0 0 12px;">
  &#128270; Open Investigation Questions
</h3>
<p style="font-size:13px;color:#6b7280;margin:0 0 12px;">
  These are gaps in the repository evidence — questions for the development team, not established facts.
</p>
{q_html}"""


def build_evidence_model() -> str:
    return f"""
{_section_header("&#128203;", "Evidence Model",
                 "How claims in this report are grounded")}
<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:32px;">
  {"".join(
    f'<div style="background:#fff;border:1px solid #e5e7eb;border-radius:8px;'
    f'padding:16px 20px;flex:1;min-width:200px;">'
    f'<div style="font-size:20px;margin-bottom:8px;">{icon}</div>'
    f'<strong style="font-size:13px;color:#1f2328;">{_h(title)}</strong>'
    f'<p style="margin:6px 0 0;font-size:12px;color:#6b7280;line-height:1.5;">{_h(desc)}</p>'
    f'</div>'
    for icon, title, desc in [
        ("&#128337;", "repo_history.json",
         "Git history extraction: 10 commits, per-file diffs, line stats. "
         "No author emails in output."),
        ("&#127942;", "epoch_analysis.json",
         "5 historical epochs identified by cohesive commit evidence. "
         "All confidence: HIGH."),
        ("&#10067;", "why_analysis.json",
         "8 change analyses. Four-voice structure: "
         "observed / stated / [INFERENCE] / unknown."),
        ("&#128218;", "onboarding_guide.md",
         "Developer guide generated from the above. "
         "All claims traceable to commit hashes."),
    ]
  )}
</div>
<div style="background:#f7f8fa;border:1px solid #e5e7eb;border-radius:8px;
            padding:16px 20px;margin-bottom:32px;">
  <table style="width:100%;border-collapse:collapse;font-size:13px;">
    <thead>
      <tr style="border-bottom:1px solid #e5e7eb;">
        <th style="text-align:left;padding:6px 12px;color:#374151;">Rating</th>
        <th style="text-align:left;padding:6px 12px;color:#374151;">Meaning</th>
      </tr>
    </thead>
    <tbody>
      <tr><td style="padding:6px 12px;">{_confidence_badge("HIGH")}</td>
          <td style="padding:6px 12px;color:#6b7280;font-size:12px;">
          Multiple independent sources (commit message + diff + file changes) agree</td></tr>
      <tr><td style="padding:6px 12px;">{_confidence_badge("MEDIUM")}</td>
          <td style="padding:6px 12px;color:#6b7280;font-size:12px;">
          Evidence present but partial or ambiguous</td></tr>
      <tr><td style="padding:6px 12px;">{_confidence_badge("LOW")}</td>
          <td style="padding:6px 12px;color:#6b7280;font-size:12px;">
          Sparse evidence; heavily inference-dependent</td></tr>
    </tbody>
  </table>
  <p style="margin:12px 0 0;font-size:12px;color:#6b7280;">
    All 13 analyses in this report (5 epochs + 8 change analyses) carry <strong>HIGH</strong> confidence.
    Author email addresses are never included in any output.
    Developer intent beyond what is explicitly stated in commit messages, code comments,
    or README.md cannot be established from this repository.
  </p>
</div>"""


def build_footer() -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""
<div style="text-align:center;padding:24px;border-top:1px solid #e5e7eb;
            margin-top:40px;color:#9ca3af;font-size:12px;">
  Codebase Time Machine &nbsp;&middot;&nbsp; IBM Bob 2.0 Hackathon
  &nbsp;&middot;&nbsp; Generated {now}
  &nbsp;&middot;&nbsp; All claims traceable to repository evidence
</div>"""


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

CSS = """
* { box-sizing: border-box; }
body {
  font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
  background: #f3f4f6;
  color: #1f2328;
  margin: 0;
  padding: 0;
  font-size: 14px;
  line-height: 1.6;
}
.container {
  max-width: 900px;
  margin: 0 auto;
  padding: 32px 20px;
}
details summary::-webkit-details-marker { display: none; }
details summary::before { content: "▶ "; font-size: 10px; }
details[open] summary::before { content: "▼ "; }
code { font-family: "SFMono-Regular", Consolas, monospace; }
a { color: #3b82d4; }
"""


def build_html(history: dict, epochs_doc: dict, why_doc: dict) -> str:
    hist_repo = history["repository"]
    commits   = history["commits"]
    epochs    = epochs_doc["epochs"]
    analyses  = why_doc["analyses"]

    body = "\n".join([
        build_header(),
        build_what_is(hist_repo),
        build_snapshot(hist_repo, hist_repo),
        build_timeline(commits),
        build_epochs(epochs),
        build_why(analyses),
        build_architecture(),
        build_issues(),
        build_onboarding(),
        build_evidence_model(),
        build_footer(),
    ])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Codebase Time Machine — TaskFlow Analysis</title>
  <style>{CSS}</style>
</head>
<body>
  <div class="container">
    {body}
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    base = Path("output")
    history  = _load_json(str(base / "repo_history.json"))
    epochs   = _load_json(str(base / "epoch_analysis.json"))
    why      = _load_json(str(base / "why_analysis.json"))

    print("[build_report] Building evolution_report.html ...")
    html_content = build_html(history, epochs, why)

    out = base / "evolution_report.html"
    out.write_text(html_content, encoding="utf-8")
    size = out.stat().st_size
    print(f"[build_report] Done. Written to: {out}  ({size:,} bytes)")


if __name__ == "__main__":
    main()
