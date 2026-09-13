# Agent Note: docker e2e batch 29 — the four corpus classes in one recall, and the cost×base boundary

Status: implemented

Related: the docker matrix + batches 1-28 notes (same series), F4
(current authority over frozen evidence), #126/D45 (the cost ledger),
#119 (the --base split's naming)

## Problem

Two cross-surface composites had no journey. Recall's sort contract
was pinned per class (batch 21's postmortem, earlier batches'
implemented/archived) but never across ALL FOUR corpus classes with
one term — the question "where does a decisions.md heading hit land
against archived title evidence" had no answer in the suite. And
`trend --cost --base` (cost roll-up × commit-date split) had no
scenario: its boundary equality (a run whose ts exactly equals the
base commit's date) was exercised only on the duration dimension.

## Decision

- **recall_rank_classes**: one term ("hedge") seeded into all four
  classes — implemented title, archived title, a decisions D-row
  heading, a postmortem body. The scenario PINS the discovery the
  first run made: a decisions D-row's heading IS its title (recall
  loads decisions entries with title=<heading text>, headings=[]), so
  "## D1 — the hedge decision" is a CURRENT title(3) hit, and the
  sort key (-rank, archived-demotion, path) yields implemented >
  decisions#D1 > archived > postmortem. The first-draft expectation
  (decisions as a body(1) hit, ranked last) was WRONG and the run
  said so — the corrected order is the contract, not the draft.
- **cost_base_boundary**: three runs BEFORE/AT/AFTER a base commit
  backdated to `at` (committer date amended); `trend --cost --base
  HEAD` must put the AT run in EARLY (`_ts(r) <= split_at`) — the
  parenthetical reads "150 early → 400 late". The run(s) count and
  token total span the WHOLE window (3 runs, 550 tokens); the split
  shows only in the parenthetical. Also regression-covers the 3.10 Z
  normalization (git %cI emits Z; fromisoformat on 3.10 rejects it —
  batch 28's fix is load-bearing here too).

## Alternatives considered

- **Assert the first-draft order (decisions last)** — that would pin
  a wish, not the product; the loader's title=<heading> design is
  deliberate (same loader as verify-decisions, D32), so the scenario
  documents it instead.
- **Assert the full cost line including the "trend --cost:" header** —
  the header's window count duplicates what cost_ordering and
  cost_caller_ranking already pin; the boundary scenario pins only
  the split semantics it exists for.

## Verification

Host: recall_rank_classes + cost_base_boundary PASS; full inner suite
60 scenarios across the docker matrix; host pytest 475 passed /
2 skipped, self-test 62 all pass, `gov run --mode all` 10 gates pass.
