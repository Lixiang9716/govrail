# Agent Note: docker e2e batch 48 — a gate's timeout is a deadline, and the numbering hole has a legal end

Status: implemented

Related: the docker matrix + batches 1-47 notes (same series),
decisions_dir (the middle-hole red this complements), the gates.json
schema (timeoutMs), #109 (the rerun hint on timeouts too)

## Problem

Two gate-semantics edges were unpinned. `timeoutMs` — the schema key
that bounds a gate's runtime — had no e2e proof the deadline is
ENFORCED (a hung command killed at the budget, the failure naming the
exceeded milliseconds with the rerun hint, the whole run red) rather
than merely decorative. And the decisions numbering hole had only its
red half pinned: decisions_dir notes that removing the HIGHEST number
is legitimate ("not created yet") but never pins that green — the
check could legally demand contiguous-from-D0 and nobody would have
caught the overreach.

## Decision

- **gate_timeout_enforced**: a 5s sleep under timeoutMs 1000 dies at
  the MEASURED deadline (< 4s wall), the summary reads "slow:
  exceeded 1000ms" with "1 timeout"; the same gate with a fast
  command passes under the same budget — the deadline, not the
  command, is what the scenario owns.
- **decision_end_gap_legal**: three dir-format decisions — removing
  D2 is the MIDDLE hole (red), restoring is green, removing D3 (the
  highest) is the legal END gap (green). The first draft failed
  exactly the way worth recording: with only two decisions, removing
  D2 IS the end gap — the middle hole needs a middle.

## Alternatives considered

- **Pin timeoutMs defaults (a gate with no timeoutMs)** — the default
  budget's value is a product constant that should stay free to move;
  the ENFORCEMENT is the contract.
- **Also pin a timeout on a PASSING gate** — the fast-command half
  covers it: the budget does not add latency when nothing hangs.

## Verification

Host: both scenarios PASS; pytest 480 passed / 2 skipped, `gov run
--mode all` 10 gates pass. Docker: all eight inner-suite cells at
92/92, cross×3 PASS.
