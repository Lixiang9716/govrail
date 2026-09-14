# Agent Note: docker e2e batch 3 — CI wiring, the kilo-file scale step, and the drift-chaos drill

Status: implemented

Related: the docker matrix + batch 2 notes (same series), D34 (the drift
machine this walks), D15/D28 (paths and what the template ships), rule 6
(the chaos drill's reds are earned by real customization and real loss)

## Problem

Batch 2 proved the wheel on hostile locales and real cross-container
contention, but three surfaces stayed dark. The matrix ran only when an
operator remembered to set GOV_DOCKER_E2E=1 — nothing in CI forced the
adopter experience to stay green, so a regression in, say, musl installs
would surface from a user report instead of a red run. The scale story
ended at 120 files, one order of magnitude below where a walker's
corner cases live (path depth, pack fan-out, accumulator drift). And
the drift machine — D34's customize/lose/adopt/uninstall-with-warning
transitions — had unit coverage per function but no journey that
walked a project through all of them.

## Decision

- **CI wiring**: a `docker-e2e` job in ci.yml (ubuntu-latest, which has
  Docker) sets GOV_DOCKER_E2E=1 and GOV_DOCKER_MIRROR=docker.io (hub is
  directly reachable from hosted runners; the mirror default stays for
  CN hosts) and runs the pytest wrapper — the same single command a
  developer runs locally. The matrix now goes red in CI when the
  adopter experience regresses, per interpreter and per libc.
- **perf_kilo**: 1,200 files across a 12-pack nested tree — stats AND
  check must finish inside a stated budget AND the counts must be
  exact (files, functions, lines). Exactness is the point: a perf test
  that only asserts "it finished" would happily time a walker that
  silently skipped half the tree. The line arithmetic caught its own
  author twice (the join inserts a blank line between blocks — 29
  lines per file, not 25); the assertion carries the arithmetic and
  its reason in the code.
- **drift_chaos**: the D34 journey through the CLI — customize a file
  → upgrade names DIFFERS; lose a file → upgrade reports MISSING as
  adoptable → --adopt restores it (and upgrade stops saying MISSING);
  --json stays exactly one value mid-chaos; and uninstall over a
  customized tree is refused (exit 1, files named) until --force.

## Alternatives considered

- **Wire the matrix into the existing gates job** — gates is the
  fast-feedback signal (~4 min); the matrix costs ~8-15. A separate
  job keeps both properties and fails independently.
- **A 10k-file scale step** — at ~6 MB/s the parse alone passes 100k
  lines in seconds; the honest next threshold is minutes-wide, which
  is a nightly shape, not a per-PR one. 1,200 files keeps the budget
  assert meaningful (sub-2-minute) in every CI cell.
- **Assert only "exit 0" in the drift drill** — D34's whole value is
  the NAMING (DIFFERS / MISSING / the customized-file warning); the
  drill asserts the words, because a drift machine that stayed silent
  would still exit 0 on three of these steps.
