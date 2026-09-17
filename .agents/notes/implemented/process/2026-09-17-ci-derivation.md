# Agent Note: derived truths regenerate in CI — one command, one fixed point

Status: implemented

## Problem

The truth-source register named every derived copy and its pin, but
enforcement was red-then-human: a pin goes red, a person remembers
which script to run. The register's own audit exposed the pattern's
cost the same week — the i18n pairing example had drifted silently
because NO script owned it; the fix was hand-written prose. Three
regenerators existed (README block, demo specimen) but each was a
separate entry point a contributor had to know about, and master could
carry stale derived content until someone noticed a red test.

## Decision

One entry point: `scripts/derive_all.py` regenerates every mechanical
derivation — README's command block from `gov --help`, the demo
specimen from the live templates, and (new) the i18n pairing examples
from `DEFAULT_CONFIG`, which had been the unpinned hand-written copy.
Idempotent, deterministic, with `--check` as the drift probe. CI grows
a `derive` job wired into the required `gates` summary: on PRs it runs
`--check` (drift goes red naming the one command); on master merge
pushes it regenerates and COMMITS the result itself, pushing under the
RELEASE_PAT identity so the push re-triggers CI — which re-runs derive,
finds the fixed point, and stops. A loop guard makes a derivation
commit that still drifts fail loudly instead of push-cycling.
Deliberately NOT derived: pairing baselines (semantic), seal
re-baselines and the ritual ledger (governed acts, not derivations).

## Alternatives considered

Verification-only (keep red-then-human) — rejected: it caps drift at
"caught at review", but master still hosts stale copies whenever a
regression lands via merge races or bypasses, and it spends a human on
a mechanical act every time. Auto-commit on PR branches — rejected:
bot pushes to contributor branches are unwelcome (forks, WIP), and the
PR-side --check red already names the command; master is where
staleness actually hurts adopters. Fold the regenerators into gov
itself (`gov derive`) — deferred: the derivations are
repository-specific (the demo specimen is this repo's asset), not
product surface; a script is the right weight until adopters ask.
