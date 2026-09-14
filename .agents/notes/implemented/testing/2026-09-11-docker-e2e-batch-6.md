# Agent Note: docker e2e batch 6 — memory_trend read-side drill and budget ceilings with teeth

Status: implemented

Related: the docker matrix + batches 1-5 notes (same series), D28 (the
history ledger trend reads), D42 (caller tags), D45 (the cost ledger's
shape), D18 (recall's read-side), #148 (the miss diagnostics), rule 6

## Problem

Batch 5 made the perf budgets honest about WHAT they measured but left
them dishonest about what they'd CATCH: 600s ceilings over 2-6s actuals
meant a 100x walker regression still passed. And the ledgers' read-side
— trend's three views (window, by-tag, cost) and recall's diagnostics
(AND misses with per-term counts, --any relaxation) — had unit coverage
but no journey that wrote real tagged/cost-bearing runs and then read
them back the way an adopter's operator does.

## Decision

- **memory_trend** (15th scenario, every cell): three tagged runs with
  caller-reported cost flow into the ledger; `trend` reads the window,
  `--by-tag` groups alpha/beta, `--cost` rolls up the token totals;
  then the recall half: an exact hit, an AND miss whose per-term
  diagnostics name which term the corpus HAS and which it LACKS, and
  `--any` relaxing the AND back to a hit. One argv lesson is pinned in
  the code: recall's terms are ARGV ITEMS — quoting two terms as one
  argument makes the per-term line read `汇率风暴 不存在的词: 0`, a
  single lump that passes a substring assert while testing nothing.
- **Budget ceilings with teeth**: kilo 120s/120s → 30s/60s; night
  600s/600s → 60s/120s. Measured firsts (0.3/0.7 kilo, 2.3/5.6 night)
  are in the docstrings with the headroom rationale: loose enough not
  to flake on slow runners, tight enough that a gross walker
  regression cannot hide inside "it passed".

zh_TW/Big5 evaluated and DEFERRED in the README: same force_utf8_stdio
codepath as the GBK cell with a different legacy codec — one more image
against zero marginal signal. The GBK cell keeps the codec whose
incident actually happened.

## Alternatives considered

- **Trend mover assertions (×1.5 thresholds)** — durations in CI are
  jittery; asserting a specific mover flakes while asserting nothing.
  The scenario pins the grouping and roll-up structure instead; mover
  thresholds stay the operator's reading.
- **A Big5 cell** — documented in the README's evaluation note rather
  than built; revisit only on a Big5-specific incident.
- **Nightly budget left at 600s** — a ceiling 260x the measurement is
  not a budget, it is a formality; tightened with stated headroom math.
