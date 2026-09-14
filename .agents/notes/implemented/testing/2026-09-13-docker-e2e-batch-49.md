# Agent Note: docker e2e batch 49 — recall terms are literal, and a done card refuses its claimants

Status: implemented

Related: the docker matrix + batches 1-48 notes (same series), #148
(the recall miss diagnostics), the card state machine (open → claimed
→ done)

## Problem

Two agent-facing edges were unpinned. Agents query recall with
whatever text the codebase handed them — including regex
metacharacters — and the engine advertises "no semantics, literal
terms": nothing e2e proved a metachar query is matched LITERALLY
(no regex interpretation, no crash) and that an unmatched metachar
term produces the ordinary per-term miss line. And the card state
machine's guard — `claim` on a DONE card — had no journey (the
concurrency scenario pins the OPEN-card contention exit 3; the
terminal state's refusal was unwatched).

## Decision

- **recall_literal_specials**: a note body containing "(paren)" is
  found by the query "(paren)" ("matched in body"); the query "zz)"
  exits 1 with "zz): 0" — the same miss diagnostics as any other
  term, metacharacters or not.
- **task_claim_status_guards**: after a card closes (the real arc:
  baseline pairing, commit, close), `claim` exits 2 with "is 'done',
  not open — only an open card can be claimed", and `task list`
  shows the "done  T-0001" verdict.

## Alternatives considered

- **Pin claim-on-claimed (exit 3) too** — that is concurrency
  scenario territory (batch 2) and already e2e-covered; this scenario
  owns the TERMINAL state's guard.
- **Also pin `task list` filtering** — the list has no filters; the
  done-verdict line is the whole surface.

## Verification

Host: both scenarios PASS; pytest 480 passed / 2 skipped, `gov run
--mode all` 10 gates pass. Docker: all eight inner-suite cells at
94/94, cross×3 PASS.
