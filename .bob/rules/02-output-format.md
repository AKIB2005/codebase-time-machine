# 02-output-format.md — Codebase Time Machine: Output Format Rules

These rules define the required JSON schema for every output file
produced by the Codebase Time Machine analysis pipeline. All analysis
scripts must produce output that conforms to this schema.

---

## Schema Version

All output files must include a `schema_version` field at the top level.
The current version is `"1.0"`. Increment the minor version for
backwards-compatible additions; increment the major version for breaking
changes.

---

## F1 — epoch_analysis.json Schema

File location: `output/epoch_analysis.json`

### Top-level structure

```json
{
  "schema_version": "1.0",
  "generated_at":   "<ISO-8601 UTC timestamp>",
  "analyzer":       "<identifier string for the producing script>",
  "source_file":    "<path to repo_history.json used as input>",
  "repository_summary": { ... },
  "epochs": [ ... ]
}
```

### repository_summary object

```json
{
  "total_commits":        <int>,
  "total_epochs_found":   <int>,
  "date_range": {
    "first": "<ISO-8601>",
    "last":  "<ISO-8601>"
  },
  "all_contributors":     ["<name>", ...],
  "total_files_touched":  <int>
}
```

### epoch object (each element of `epochs[]`)

```json
{
  "epoch_id":     "<string — unique, stable identifier e.g. 'epoch_1'>",
  "name":         "<concise descriptive name for this period>",
  "summary":      "<1-3 sentence human-readable summary of the epoch>",
  "commit_hashes": ["<full hash>", ...],
  "start_commit": "<full hash of first commit in this epoch>",
  "end_commit":   "<full hash of last commit in this epoch>",
  "key_files":    ["<file path>", ...],
  "observed_changes": [
    {
      "description":       "<factual statement about what changed>",
      "evidence_commits":  ["<hash>", ...],
      "evidence_type":     "<commit_message | diff | file_addition | file_modification | file_deletion>"
    },
    ...
  ],
  "inferred_theme": {
    "label":       "<short label for the theme>",
    "explanation": "<1-2 sentence interpretive explanation — clearly marked as inference>",
    "basis":       "<what evidence the inference rests on>"
  },
  "confidence":        "<HIGH | MEDIUM | LOW>",
  "uncertainty_notes": "<required string when confidence is MEDIUM or LOW; null when HIGH>"
}
```

---

## F2 — Field Constraints

| Field | Constraint |
|-------|-----------|
| `epoch_id` | Must be unique across all epochs in the file. Format: `epoch_N` where N is 1-based. |
| `name` | Max 60 characters. Must be a noun phrase, not a sentence. |
| `summary` | Max 300 characters. |
| `commit_hashes` | Must be a non-empty list. All hashes must exist in the source `repo_history.json`. |
| `start_commit` | Must equal `commit_hashes[0]`. |
| `end_commit` | Must equal `commit_hashes[-1]`. |
| `key_files` | Must be files that appear in `files_changed` of at least one commit in `commit_hashes`. |
| `observed_changes` | Minimum 1 entry per epoch. |
| `evidence_commits` | Must be a subset of `commit_hashes` for the epoch. |
| `inferred_theme.label` | Max 40 characters. |
| `confidence` | Exactly one of: `HIGH`, `MEDIUM`, `LOW`. |
| `uncertainty_notes` | Must be a non-null, non-empty string when `confidence != "HIGH"`. Must be `null` when `confidence == "HIGH"`. |

---

## F3 — Separation of Fact and Inference

- Statements inside `observed_changes[].description` must be verifiable
  against the diff or file-change data in `repo_history.json`.
- Statements inside `inferred_theme.explanation` may contain
  interpretation but must state their evidential basis in
  `inferred_theme.basis`.
- Neither field may contain author email addresses (see rule E9).

---

## F4 — Determinism

Given the same `repo_history.json` input, the epoch analysis must
produce structurally identical output (same epochs, same commit
assignments, same confidence levels). Timestamps in `generated_at`
will naturally differ but no other field should vary between runs on
unchanged input.

---

## F5 — Completeness

Every commit in `repo_history.json` must appear in exactly one epoch.
No commit may be omitted. No commit may appear in more than one epoch.

---

## F6 — Auditability

The `source_file` and `generated_at` fields allow any reviewer to
reproduce the analysis against the same input and compare outputs.
The `analyzer` field identifies which script version produced the file.

---

## F7 — why_analysis.json Schema

File location: `output/why_analysis.json`

### Top-level structure

```json
{
  "schema_version": "1.0",
  "generated_at":   "<ISO-8601 UTC timestamp>",
  "analyzer":       "<identifier string for the producing script>",
  "source_file":    "<path to repo_history.json used as input>",
  "repository_summary": { ... },
  "analyses": [ ... ]
}
```

### analysis object (each element of `analyses[]`)

```json
{
  "analysis_id":             "<string — unique, stable e.g. 'why_1'>",
  "change":                  "<short noun phrase naming the change>",
  "commit_hashes":           ["<full hash>", ...],

  "observed_change":         "<factual description of what changed, traceable to diffs/files>",
  "stated_intent":           "<text from commit message / code comment / README that explicitly states intent — or null if no such text exists>",
  "evidence_based_inference":"<what can reasonably be inferred from commit ordering, diffs, surrounding changes — clearly labelled as inference>",
  "unknown":                 "<what cannot be established from available repository evidence>",

  "evidence": [
    {
      "commit_hash": "<full hash>",
      "files":       ["<file path>", ...],
      "reason":      "<why this commit/file constitutes evidence for this analysis>"
    }
  ],

  "confidence":        "<HIGH | MEDIUM | LOW>",
  "uncertainty_notes": "<required when confidence != HIGH; null when HIGH>"
}
```

### Field constraints (why_analysis)

| Field | Constraint |
|-------|-----------|
| `analysis_id` | Must be unique. Format: `why_N` (1-based). |
| `change` | Max 80 characters. Short noun phrase, not a sentence. |
| `observed_change` | Must be verifiable against diffs/files in `repo_history.json`. No invented facts. |
| `stated_intent` | Null if no explicit intent statement exists in the repository. Never fabricated. |
| `evidence_based_inference` | Must explicitly state it is inference. Must name the evidence it rests on. |
| `unknown` | Must be populated. Never empty. Explicitly states what evidence is absent. |
| `evidence[].commit_hash` | Must exist in `repo_history.json`. |
| `confidence` | One of: `HIGH`, `MEDIUM`, `LOW`. |
| `uncertainty_notes` | Required non-null string when `confidence != "HIGH"`. |

### Separation of voice (F7a)

The four narrative fields (`observed_change`, `stated_intent`,
`evidence_based_inference`, `unknown`) serve distinct epistemic roles
and must never be mixed:

- `observed_change` — facts only, grounded in diffs and file changes.
- `stated_intent` — verbatim or direct paraphrase of repository text.
- `evidence_based_inference` — labelled interpretation with stated basis.
- `unknown` — explicit declaration of evidential gaps.

No field may contain author email addresses (rule E9).
