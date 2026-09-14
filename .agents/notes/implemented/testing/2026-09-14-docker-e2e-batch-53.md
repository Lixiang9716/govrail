# Agent Note: docker e2e batch 53 — round 2 opens with BOM drafts, exemption teeth, and non-run p50s

Status: implemented

Related: the docker matrix + batches 1-52 notes (same series), #184
(merged — this batch opens round 2 on a fresh branch), the BOM
tolerance decision (batch 50), #119 (non-run outcomes), D43 (the
exempt-glob vocabulary the agent-heavy preset writes)

## Problem

Three follow-throughs from earlier batches were unpinned. Batch 50
made the memory plane BOM-tolerant, but the DECISION draft path
(`decision add --from`, the write entry) had no BOM case — a Windows
author's first decision would have been the test. The
note_presence_exempt hint that agent-heavy writes had no proof its
exclusion is SELECTIVE (exempt paths out, everything else still
flagged). And trend's non-run handling (#119) — SCOPED_OUT records
must not drag a gate's p50 — lived only in unit fixtures.

## Decision

- **decision_bom_draft**: a BOM'd draft lands as "## D0 — 锚定决策"
  (title clean, no BOM byte) and verify-decisions passes it.
- **note_presence_exempt_globs**: one commit touching both an exempt
  path (scratch/junk.md) and a code file (m.py) — the output reads
  "1 non-trivial file(s) (m.py)", names the loaded hint, and never
  mentions junk.md. Exemption is per-path, not per-run.
- **trend_ignores_non_runs**: late = [SCOPED_OUT@0ms, PASS@300ms]
  reads "p50 100ms → 300ms (×3.0 ↑)" — a naive average would have
  said 150ms and hidden the mover right at the 1.5× boundary.

## Alternatives considered

- **Pin the exempt OUTPUT with multiple globs** — one glob proves the
  mechanism and its selectivity; the glob list is the manifest's
  own format, already covered by the unit side.
- **Also pin NOT_SELECTED/DISABLED outcomes** — the NON_RUN set is
  one predicate in trend; SCOPED_OUT (the most common in practice)
  carries the case.

## Verification

Host: all three scenarios PASS; pytest 481 passed / 2 skipped,
`gov run --mode all` 10 gates pass. Docker: all eight inner-suite
cells at 101/101, cross×3 PASS.
