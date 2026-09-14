# Agent Note: docker e2e batch 33 — a self-test FAIL keeps its whole output, and whatsnew's range edges

Status: implemented

Related: the docker matrix + batches 1-32 notes (same series), #139
(the evidence-line convention this extends), the batch-32 flake that
motivated the dump, D31 (whatsnew)

## Problem

Batch 32's matrix hit a flake (test_change_scope_suggests_from_paths
on 3.10, never reproduced since) — and the flake's full evidence was
UNREADABLE BY CONSTRUCTION: the case's assert message embedded the
whole subprocess traceback, the FAIL line quotes only its last line
(#139's convention, right about the killer exception), and the rest
of the message existed for the split second of the print. The
operator — and the agent debugging at 2am — gets "AttributeError: …"
with the frames gone, exactly when reproduction is hardest. On the
same sweep, whatsnew's range edges (explicit --since, the
nothing-newer branch, the no-project newest-section default) had no
e2e journey.

## Decision

- **The product fix**: when a tool case fails with a MULTI-line
  message, `_run_tool_case` writes the whole text to a temp file
  (`gov-selftest-<case>-*.log`) and the FAIL line names it after the
  quoted killer exception — the last line stays the headline (#139
  unchanged), the traceback stays readable. Single-line failures dump
  nothing (the line IS the evidence). Two unit tests pin both shapes.
- **whatsnew_since_edges**: `--since 99.0.0` takes the nothing-newer
  branch; `--since 0.0.1` reveals the history; the default in a
  governed project is the manifest's init version (and prints the
  nothing-newer line when aligned); outside a project the newest
  section prints with the range hint.

## Alternatives considered

- **Print the full message in the FAIL line** — reverses #139's whole
  point: the headline would drown in subprocess output, and `gov run`
  summaries would scroll. Name-a-file keeps the line short and the
  evidence whole.
- **Dump under .gov/history/** — the self-test runs outside projects
  too (and inside read-only CI checkouts); tempdir is neutral and
  self-cleaning.

## Verification

Host: whatsnew_since_edges PASS; pytest 478 passed / 2 skipped (two
new), self-test 62 all pass, `gov run --mode all` 10 gates pass.
Docker: all eight inner-suite cells at 66/66, cross×3 PASS (the
wheel changed, forcing a full rebuild).
