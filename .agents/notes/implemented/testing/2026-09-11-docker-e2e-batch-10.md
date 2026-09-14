# Agent Note: docker e2e batch 10 — the --base time split and the version-drift chain

Status: implemented

Related: the docker matrix + batches 1-9 notes (same series), #119 (the
--base split's naming), D44 (metrics-not-evidence — the crafted ledger),
D28 (trend reads the local ledger), the doctor/whatsnew/upgrade trio

## Problem

Two read-side paths ran only through unit tests with synthetic windows.
`gov trend --base` cuts the window at a ref's COMMIT date — a split
that needs runs on BOTH sides of that date, which real commands cannot
produce deterministically (history timestamps are always "now"). And
the version-drift chain — a stale `.gov/manifest.json` version flowing
into doctor's note, whatsnew's default `since`, and upgrade --json's
`initialized_with` — was walked fragment-wise (one assert per tool) but
never as the CHAIN an adopter with an old manifest experiences.

## Decision

- **trend_base_split**: the ledger is a metrics file (D44: it is
  evidence for nothing), so the drill HAND-CRAFTS it — two runs
  timestamped 3 days old at 100ms, two now at 300ms — and BACKDATES the
  base commit 2 days (committer + author dates; %cI is the line the
  split cuts at). The assertions: `--base` reports the 100ms → 300ms
  ×3.0 mover, and the no-flag window (halves of the same four runs)
  agrees. Crafting the ledger is legitimate precisely because D44
  classes it as metrics; the same craft would be fraud in a receipt,
  which is exactly the line between the two ledgers.
- **manifest_drift**: hand-roll the manifest version backward, then
  walk the chain: doctor NOTEs the drift (exit stays 0), whatsnew's
  default `since` follows the manifest (an old manifest shows the
  operator everything since), `init --upgrade --json` reports
  `initialized_with` vs `package`, and aligning the manifest silences
  the note. Three tools, one source of truth, one fixture.

A dead patch line (`... if False else None`) shipped in the first
draft of trend_base_split — caught on re-read and removed; left in, it
would have been a landmine for the next editor of the fixture.

AND the scenario caught a real product bug on its first 3.10-cell run:
`gov trend --base` crashed with ValueError on Python 3.10 because git's
%cI emits UTC as a trailing Z and fromisoformat accepts Z only from
3.11 — on every UTC-hosted commit, on a SUPPORTED interpreter. Fixed by
normalizing the trailing Z before parsing; the 3.10 docker cell is the
rejection case's home (the crash cannot reproduce on a 3.12 host, which
is precisely why a version matrix belongs in E2E).

## Alternatives considered

- **Real timestamps across a real base** — impossible deterministically:
  run timestamps are always "now", so every run lands after any
  backdated base and the early half stays empty (the split then skips,
  silently, by design). Crafting the ledger is the only honest fixture.
- **manifest drift as a doctor-only assert** — the chain is the value:
  three tools reading one key is where a rename would break all three
  at once, and the drill names each consumer.
