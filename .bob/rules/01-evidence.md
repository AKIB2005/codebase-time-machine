# 01-evidence.md — Codebase Time Machine: Evidence Rules

These rules govern ALL analysis produced by the Codebase Time Machine
historical analysis pipeline. They are binding for every stage:
epoch analysis, change narrative, and developer-intent inference.

---

## E1 — Never Invent Historical Events

Do not describe, imply, or suggest any event that did not occur in the
repository. Every event in the analysis must correspond to at least one
real commit in `repo_history.json`. If an event cannot be traced to a
commit hash, it must not appear in the output.

## E2 — Every Factual Claim Must Be Traceable

Every sentence that asserts a historical fact (what was added, changed,
removed, fixed, or introduced) MUST include one or more supporting
commit hash references in the `evidence_commits` field of the relevant
JSON object. A claim without a traceable hash is not a fact — it is
speculation and must be labelled as such.

## E3 — Distinguish Observed Facts from Interpretation

Use separate fields in the output schema to separate what was directly
observed from what was inferred:

- `observed_changes` — statements directly supported by diff content,
  file names, and commit messages. These are facts.
- `inferred_theme`   — interpretive summary that explains the "why" or
  the "what this means". This is inference, not fact.

Never mix observation and interpretation in the same field.

## E4 — Do Not Infer Developer Intent Without Evidence

Do not claim that a developer intended to achieve a goal, solve a
problem, or make a trade-off unless the repository evidence (commit
message, diff, or comment in code) explicitly supports that claim.
Vague proximity in time is not evidence of intent.

## E5 — Insufficient Evidence Must Be Declared

If the available evidence is not sufficient to support a claim, write:
"Insufficient evidence to determine [X]."
Do not fill gaps with plausible-sounding assumptions.

## E6 — Bug-Fix Claims Require Diff Evidence

Do not claim that commit X fixed a problem unless:
(a) the commit message uses fix/bug/correct/patch language, AND
(b) the diff shows removal or replacement of the defective code.
Both conditions must be satisfied. Satisfying only (a) is not sufficient.

## E7 — Commit Messages Are Evidence, Not Proof of Motivation

A commit message is evidence of the author's stated intent at commit
time. It does not automatically prove that the stated goal was actually
achieved, nor that the motivation was as stated. When using commit
message content, flag it as "as stated in commit message" rather than
as verified fact.

## E8 — Use Diff Information as Supporting Evidence

Where diff snippets are available in `repo_history.json`, use the actual
changed lines as supporting evidence for claims about what the code does.
Prefer diff evidence over commit message paraphrasing where they differ.

## E9 — Do Not Expose Author Email Addresses

Author email addresses must never appear in any analysis output field,
display string, epoch summary, or report. Use only the author display
name. This rule supersedes all other formatting instructions.

## E10 — Assign a Confidence Level to Every Epoch

Every epoch in `epoch_analysis.json` must carry one of these values in
the `confidence` field:

| Value  | Meaning |
|--------|---------|
| HIGH   | Multiple independent evidence sources (commit message + diff + file changes) all agree. |
| MEDIUM | Evidence is present but partial — e.g., commit message is clear but diff is truncated or ambiguous. |
| LOW    | Evidence is sparse, indirect, or relies heavily on inference. |

## E11 — Include Uncertainty Notes When Confidence Is Not HIGH

Whenever `confidence` is `MEDIUM` or `LOW`, the `uncertainty_notes`
field MUST be populated with a specific explanation of what evidence is
missing, ambiguous, or in tension. An empty `uncertainty_notes` on a
non-HIGH confidence epoch is a schema violation.
