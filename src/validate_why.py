"""
validate_why.py — Codebase Time Machine: why_analysis.json validator.

Checks conformance to .bob/rules/02-output-format.md (F7) and
.bob/rules/01-evidence.md.

Usage:
    python src/validate_why.py [why_path] [history_path]
"""

from __future__ import annotations

import argparse
import json
import re
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


EMAIL_PAT = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_top_level(data: dict, results: list) -> None:
    for k in ["schema_version", "generated_at", "analyzer",
              "source_file", "repository_summary", "analyses"]:
        if k not in data:
            _add(results, "FAIL", f"Missing top-level key: {k!r}")
        else:
            _add(results, "PASS", f"Top-level key present: {k!r}")


def check_repository_summary(data: dict, results: list) -> None:
    rs = data.get("repository_summary", {})
    for k in ["total_commits", "total_analyses", "contributors",
              "total_files_touched"]:
        if k not in rs:
            _add(results, "FAIL", f"repository_summary missing: {k!r}")
        else:
            _add(results, "PASS", f"repository_summary.{k} present")

    stated = rs.get("total_analyses", -1)
    actual = len(data.get("analyses", []))
    if stated != actual:
        _add(results, "FAIL",
             f"total_analyses ({stated}) != len(analyses) ({actual})")
    else:
        _add(results, "PASS",
             f"total_analyses matches analyses list length ({actual})")


def check_ids_unique(data: dict, results: list) -> None:
    ids = [a.get("analysis_id") for a in data.get("analyses", [])]
    if len(ids) == len(set(ids)):
        _add(results, "PASS", f"All {len(ids)} analysis_ids unique")
    else:
        _add(results, "FAIL", f"Duplicate analysis_ids: {ids}")


def check_analyses(data: dict, history_hashes: set, results: list) -> None:
    for a in data.get("analyses", []):
        aid = a.get("analysis_id", "?")

        # Required string fields
        for field in ["analysis_id", "change", "observed_change",
                      "evidence_based_inference", "unknown", "confidence"]:
            if not a.get(field):
                _add(results, "FAIL", f"{aid}: missing/empty {field!r}")

        # change length
        change_len = len(a.get("change", ""))
        if change_len > 80:
            _add(results, "FAIL",
                 f"{aid}: change exceeds 80 chars ({change_len})")
        else:
            _add(results, "PASS", f"{aid}: change length OK ({change_len})")

        # stated_intent may be null
        si = a.get("stated_intent")
        if si is None:
            _add(results, "PASS", f"{aid}: stated_intent is null (acceptable)")
        elif isinstance(si, str) and si:
            _add(results, "PASS", f"{aid}: stated_intent is non-null string")
        else:
            _add(results, "FAIL", f"{aid}: stated_intent is empty string (use null)")

        # confidence
        conf = a.get("confidence")
        if conf not in ("HIGH", "MEDIUM", "LOW"):
            _add(results, "FAIL",
                 f"{aid}: confidence must be HIGH/MEDIUM/LOW, got {conf!r}")
        else:
            _add(results, "PASS", f"{aid}: confidence = {conf}")

        # uncertainty_notes
        un = a.get("uncertainty_notes")
        if conf == "HIGH" and un is not None:
            _add(results, "FAIL",
                 f"{aid}: uncertainty_notes must be null when confidence=HIGH")
        elif conf in ("MEDIUM", "LOW") and not un:
            _add(results, "FAIL",
                 f"{aid}: uncertainty_notes required when confidence={conf}")
        else:
            _add(results, "PASS", f"{aid}: uncertainty_notes rule OK")

        # commit_hashes
        ch = a.get("commit_hashes", [])
        if not ch:
            _add(results, "FAIL", f"{aid}: commit_hashes is empty")
        else:
            unknown_h = [h[:8] for h in ch if h not in history_hashes]
            if unknown_h:
                _add(results, "FAIL",
                     f"{aid}: commit_hashes not in history: {unknown_h}")
            else:
                _add(results, "PASS",
                     f"{aid}: all {len(ch)} commit_hash(es) verified")

        # evidence list
        ev = a.get("evidence", [])
        if not ev:
            _add(results, "FAIL", f"{aid}: evidence list is empty")
        else:
            _add(results, "PASS", f"{aid}: evidence has {len(ev)} entry/entries")
            for idx, e in enumerate(ev):
                if e.get("commit_hash") not in history_hashes:
                    _add(results, "FAIL",
                         f"{aid} evidence[{idx}]: commit_hash not in history")
                if not e.get("files"):
                    _add(results, "FAIL",
                         f"{aid} evidence[{idx}]: files list empty")
                if not e.get("reason"):
                    _add(results, "FAIL",
                         f"{aid} evidence[{idx}]: reason missing")

        # Check [INFERENCE] label present in evidence_based_inference
        ebi = a.get("evidence_based_inference", "")
        if "[INFERENCE]" not in ebi and "[inference]" not in ebi.lower():
            _add(results, "FAIL",
                 f"{aid}: evidence_based_inference must contain [INFERENCE] label")
        else:
            _add(results, "PASS",
                 f"{aid}: [INFERENCE] label present in evidence_based_inference")

        # No emails in key metadata fields
        for field in ("change", "observed_change", "stated_intent",
                      "evidence_based_inference", "unknown"):
            val = str(a.get(field) or "")
            found = EMAIL_PAT.findall(val)
            if found:
                _add(results, "FAIL",
                     f"{aid}.{field}: email address detected: {found[:2]}")


def check_inference_not_invented(data: dict, results: list) -> None:
    """
    Heuristic: evidence_based_inference must NOT contain forbidden
    phrases that indicate invented motivation without evidence.
    """
    forbidden = [
        "the developer wanted",
        "production required",
        "they needed to scale",
        "for performance reasons",   # unless followed by evidence
    ]
    violations = []
    for a in data.get("analyses", []):
        ebi = a.get("evidence_based_inference", "").lower()
        for phrase in forbidden:
            if phrase in ebi:
                violations.append(
                    f"{a.get('analysis_id')}: forbidden phrase '{phrase}'"
                )
    if violations:
        _add(results, "FAIL",
             f"Invented-motivation phrases detected: {violations}")
    else:
        _add(results, "PASS",
             "No forbidden invented-motivation phrases detected")


# ---------------------------------------------------------------------------
# Print
# ---------------------------------------------------------------------------

def _print_results(results: list) -> int:
    passed = [r for r in results if r[0] == "PASS"]
    failed = [r for r in results if r[0] == "FAIL"]
    warned = [r for r in results if r[0] == "WARN"]

    print()
    print("=" * 72)
    print("  Codebase Time Machine - why_analysis.json Validation Report")
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
        description="Validate output/why_analysis.json"
    )
    parser.add_argument("why_path", nargs="?",
                        default=str(Path("output") / "why_analysis.json"))
    parser.add_argument("history_path", nargs="?",
                        default=str(Path("output") / "repo_history.json"))
    args = parser.parse_args()

    data    = _load(args.why_path)
    history = _load(args.history_path)
    history_hashes = {c["hash"] for c in history.get("commits", [])}

    results: list = []
    check_top_level(data, results)
    check_repository_summary(data, results)
    check_ids_unique(data, results)
    check_analyses(data, history_hashes, results)
    check_inference_not_invented(data, results)

    failures = _print_results(results)
    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    main()
