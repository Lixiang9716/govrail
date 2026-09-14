# Agent Note: docker e2e batch 7 — the review grade journey and the archive closure

Status: implemented

Related: the docker matrix + batches 1-6 notes (same series), D30 (the
review workbench: human decides, machine transcribes), rule 4 (the
frozen archive), the archive-agent-notes skill (the loop this closes)

## Problem

Two judgment-facing surfaces had no journey. `gov review --grade` —
dossier, the interactive p/f/s/q loop, the verdict block with blockers —
was pinned only by unit tests driving the function, never by stdin
through the CLI where a typo in the prompt contract or an exit-code
drift would surface to a real reviewer mid-review. And the archive loop
was covered only to its seal: the memory CONTINUITY half (a sealed note
must stay readable, with the corpus statement counting the archived
side) and the no-laundering half (re-sealing a drift refused, restoring
the sealed bytes turning verify green without any re-seal) were
asserted in fragments.

## Decision

- **review_grade** (single container): a project with a two-item rubric
  and a diff; stdin IS the human. Approve journey: two p answers →
  `verdict: approve`, exit 0, each item transcribed. Request-changes
  journey: f demands an evidence line (the typed text appears verbatim
  in the R1 fail line), s skips without blocking, the verdict names the
  blocker and exits 1.
- **archive_closure**: two implemented notes; one moves to the frozen
  archive and `archive-notes` seals it; recall still reads the sealed
  note with the corpus statement counting `archived 1` (memory persists
  past archiving); tampering turns verify red; re-sealing a drift is
  refused; restoring the sealed bytes turns verify green WITHOUT any
  re-seal — the no-laundering half walked to its actual resolution.

Harness archaeology, worth recording because it shaped the stamping
design: the scenario table in inner_e2e.py carried a duplicated entry
and two missing ones after five patch generations — the runs stayed
green because the stale entries were all passing scenarios, the exact
"plausible zero" failure class the metrics suite exists to catch. The
dict is now rebuilt wholesale, and the per-cell content stamp (batch 2)
is what would force any future rebuild to be honest.

## Alternatives considered

- **Drive --grade with a pty** — the loop is line-oriented stdin; a
  piped string is the honest minimal harness, and a pty would test the
  terminal, not the contract.
- **Assert the dossier's evidence candidates** — they are leads to
  verify, not verdicts (the tool says so); pinning their exact layout
  would over-constrain presentation.
- **Grow the archive in the drift state** — refusal-over-drift and
  growth-over-drift are different behaviors; the drill pins the refusal,
  and growth is asserted only over the honest restored state.
