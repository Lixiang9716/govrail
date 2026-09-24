# Agent Note: note verify names files: the authoring loop lints exactly the notes it names

Status: implemented

Related: D3, issues #386

## Problem

While authoring a single note, the only passing route to "lint just
this file" was `gov run --gate notes` or a repo-wide `gov note verify`
— 134 notes judged (in the reporting repo) plus the rest of the DAG
tooling, for feedback about section order in the one file being
edited. `gov task show <id>` set the precedent for single-entity
inspection; `gov note verify` was the surface where the same shape was
missing, and the mistyped-flag refusal ("unexpected argument ... this
command takes no flags") was the wall an author hit first.

## Decision

- **`gov note verify [path ...]`**: each named file is judged with the
  same per-note checks the repo-wide gate runs — format, required
  sections and their order, hollow/placeholder bodies, thin-section
  advisories, the superseded pointer. No paths means the repo-wide
  gate, byte-for-byte unchanged. Flags are still refused: a token
  starting with `-` exits 2 naming it (the exit-code contract's
  refusal), so a mistyped flag can never read as a green verdict.
- **Placement stays a repo-wide concern.** The scoped form judges the
  file, not where it sits — a note mid-move is exactly when this form
  is used, and a placement verdict there would judge the workflow
  rather than the note. The count line ("N violation(s) in M
  note(s)") reports M as the named count.
- `gov note verify --help` names the paths (the discovery surface; the
  positional rides the existing suppressed-`rest` forwarding, so the
  flag registry is unchanged).

## Alternatives considered

- **Also run the D-reference audit in the scoped form** — declined:
  `gov note check` already owns the dangling-D audit and runs the
  format gate first; duplicating the decisions-table read inside
  verify would give one file two auditors whose verdicts can drift.
  The scoped form is the fast authoring loop for SHAPE; `note check`
  remains the full pre-commit judgment.
- **`--file` flag instead of positionals** — rejected: the issue asks
  for the `task show <id>` shape (a positional entity), a flag would
  make the common invocation longer, and REMAINDER forwarding already
  carries plain paths with no new flag to register.
- **A `--json` output for the scoped form** — declined for now: the
  ask is human-in-the-loop feedback; nothing consumes a single note's
  verdict mechanically yet, and an output contract nobody reads is
  drift surface (rule 10's spirit, applied to outputs).
