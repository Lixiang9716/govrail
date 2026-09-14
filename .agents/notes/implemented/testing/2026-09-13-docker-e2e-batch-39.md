# Agent Note: docker e2e batch 39 — note new scaffolds memory that passes its own gate

Status: implemented

Related: the docker matrix + batches 1-38 notes (same series), D34
(the govrail:Dn external reference namespace), D32 (one loader for
note checks)

## Problem

`gov note new` — the WRITE entry to the plane's own memory — had no
e2e journey: every scenario builds note files by hand. The scaffold's
promises are exactly the kind that rot quietly: the skeleton must
pass verify-notes AS WRITTEN (a template drift would make every new
note born red), a --ref must be validated against the decisions table
BEFORE any file lands, a govrail:Dn reference must be recorded
without local validation, and an unknown class must name the closed
set — each refused without leaving a file behind.

## Decision

- **note_new_scaffold**: `note new --class testing --ref D1` writes
  the skeleton and the very next `verify-notes` and `note check` pass
  over it; `--ref D99` exits 2 ("not in docs/decisions.md") and the
  class directory is byte-identical after the refusal; `--ref
  govrail:D54` prints "recorded, not validated" and the resulting
  note still passes verify-notes (the external namespace is stripped
  before local D-ref checking); `--class nonsense` exits 2 naming the
  closed set of six classes.

## Alternatives considered

- **Pin `note check` against a stale D-ref in an EXISTING note** —
  audit-notes' D-ref signal (batch 34) and note check's refusal here
  cover the two ends (write-time, audit-time); a third variant of the
  same check pins nothing new.
- **Also pin the date in the scaffolded filename** — the filename is
  date.today(); pinning it buys a midnight flake, nothing else (the
  glob matches the slug).

## Verification

Host: note_new_scaffold PASS; pytest 480 passed / 2 skipped,
`gov run --mode all` 10 gates pass. Docker: all eight inner-suite
cells at 75/75, cross×3 PASS, pypi-adopter PASS — the 3.12-slim build
process died silently mid-matrix (no output, FAILED latched, which
also swallowed the gbk cell's run); both cells passed on rerun, the
series' second environment-suspect incident, recorded rather than
explained away.
