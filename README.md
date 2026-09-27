# ⏳ Codebase Time Machine

> **Understand not only what a codebase is today — but how it got there.**

Codebase Time Machine is a developer workflow tool that reconstructs the evolution of a Git repository and turns its history into an evidence-grounded, developer-friendly report.

Instead of asking a new developer to read thousands of lines of code and hundreds of commits, the tool answers:

- What changed?
- When did it change?
- Which files were affected?
- How did the architecture evolve?
- Why does the current codebase look this way?
- What should a new developer understand first?

---

## 🎯 The Problem

When developers join an existing codebase, the current source code tells only **what exists now**.

Git contains the missing historical context, but raw Git history is difficult to understand quickly.

A developer may need to manually inspect:

```text
hundreds of commits
       ↓
changed files
       ↓
individual diffs
       ↓
architectural changes
       ↓
bug fixes
       ↓
current architecture
