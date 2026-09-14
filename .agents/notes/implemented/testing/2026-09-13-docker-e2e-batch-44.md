# Agent Note: docker e2e batch 44 — a config refusal runs no gate, and an empty tree's zeros carry their own definition

Status: implemented

Related: the docker matrix + batches 1-43 notes (same series), D1
(argv arrays — the schema refusal enforces the shape at run time),
D54 (the口径 echo stats_empty_tree pins)

## Problem

Two first-contact surfaces were unpinned. A hand-edited gates.json —
the file every adopter eventually touches — met `gov run` with no e2e
proof of the refusal shape: a command written as a STRING (the most
natural wrong guess against D1's argv-array rule) must be named with
its remedy before a single gate executes, not discovered mid-run.
And `gov stats` on a tree with no source files had no journey: the
plan's own phobia is "a plausible zero is the worst kind of lie", so
the empty answer must show its work — every shipped language, files
0, and the口径 (code_line rule, nesting set, grammar identity) that
defines what the zeros mean.

## Decision

- **gates_schema_refusal**: a two-gate config where the second gate's
  command is a string — `gov run --mode all` exits 2 with
  "gate 'str-cmd': command must be a non-empty array of strings" and
  stdout carries NO PASS line: the refusal happens before the first
  gate, even though the first gate was perfectly fine.
- **stats_empty_tree**: init'd project, zero source files — the
  --json answer still carries all eight shipped language rows, python
  at files=0 with the zeroed lines dict, parse_errors 0, and
  rule.grammar == tree_sitter_python alongside code_line and nesting.

## Alternatives considered

- **Also refuse at WRITE time (init --upgrade / preset apply)** — both
  write paths already validate against the same schema (preset's
  refusal was batch 35's discovery); this scenario pins the READ side
  where hand-edits actually arrive.
- **Assert the empty-tree OUTLIERS key too** — the outliers list is
  part of the same zero row; the files/lines/parse_errors trio plus
  the口径 echo already fail any "phantom language" or "dropped
  metadata" regression.

## Verification

Host: both scenarios PASS first run; pytest 480 passed / 2 skipped,
`gov run --mode all` 10 gates pass. Docker: all eight inner-suite
cells at 85/85, cross×3 PASS.
