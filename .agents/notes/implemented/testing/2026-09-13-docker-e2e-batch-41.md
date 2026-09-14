# Agent Note: docker e2e batch 41 — doctor triage returns to sound, and the lock table is a mirror, not a gate

Status: implemented

Related: the docker matrix + batches 1-40 notes (same series),
doctor_parser_versions (batch 31's parser slice of the same report),
D52 (leases decide; listings show)

## Problem

Two read-only surfaces were unpinned end to end. `gov doctor` is the
adopter's FIRST command when something feels wrong, but no scenario
walked the triage arc: sound → a broken gates.json is a PROBLEM
(exit 1, named in problems[]) → the file removed, the built-in
defaults apply and the run returns to sound. And `gov locks` — the
diagnostic mirror of the lease table — had no pin that it shows
holder/expiry while never deciding admission (the D52 boundary
between seeing a lock and honoring it).

## Decision

- **doctor_triage**: --json is exactly one object {version, status,
  checks, problems} with the human report on stderr; a corrupt
  gates.json flips status to "problems" with the file named (twice —
  exit 1 in both stream shapes); deleting the file falls back to
  defaults and the same --json shape reads "sound" again. Triage must
  be RECOVERABLE, not just loud.
- **locks_listing**: acquire then `gov locks` shows the resource and
  holder; release then `gov locks` shows neither. The listing's
  honesty is the pin — the admission decision itself is D52's,
  already pinned by the cross-container lease drill.

## Alternatives considered

- **Force the OTHER doctor problems** (argparse shadow, python too
  old) — the backport-shadow CI job owns the hostile-environment
  half; duplicating it in the matrix buys a second copy of the same
  evidence.
- **Pin the exact checks list** — the check set grows with the tool
  (the parser check arrived in D54); pinning membership would make
  every future check a breaking test. The shape and the triage arc
  are the contract.

## Verification

Host: both scenarios PASS (the scenario's own first run caught its
author's missing expect=1 — the broken state's --json call — before
any matrix time was spent); pytest 480 passed / 2 skipped,
`gov run --mode all` 10 gates pass. Docker: all eight inner-suite
cells at 79/79, cross×3 PASS.
