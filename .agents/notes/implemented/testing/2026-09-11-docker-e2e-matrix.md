# Agent Note: docker e2e matrix — the adopter's environment, in containers

Status: implemented

Related: D54 (the features this exercises through the installed wheel),
#168/#172 (the locale wall, attacked here on a real C-locale host), D32
(worktree ledger anchoring), D52 (lease contention across real
processes), rule 6 (every scenario's red is earned on demand)

## Problem

The host suites test the checkout with the checkout's interpreter
(3.12, glibc, UTF-8 locale, root-adjacent user). Everything the wheel
CLAIMS beyond that — Python 3.10 through 3.13, musl via Alpine, a
C-locale host with Chinese content, a non-root adopter, a pre-push hook
actually executing (the host suite is POSIX-coupled here and skips it) —
was verified nowhere, or only in fragments. And the host E2E drove one
process at a time: the lease/claim race was sequential stand-ins, never
eight real processes colliding. The release wheel shipped on claims no
clean environment had ever exercised end to end.

## Decision

`tests/docker_e2e/` — a Docker matrix that builds the adopter's
environment per cell: base image (python:3.10/3.11/3.12/3.13-slim,
3.12-alpine for musl) + git + the wheel built from the CURRENT checkout
(the release artifact, not the source tree). Dependency wheels resolve
at BUILD time and are baked, so runs are offline-fast; pip retries are
baked too because the PyPI CDN flaps on large wheels and a build must
ride out a read blip. A wheel-sha stamp forces per-cell rebuilds when
the checkout's wheel changes — a stale image can never test an old
wheel, the metrics-suite lesson (a plausible number meaning nothing)
applied to environments.

`inner_e2e.py` runs eight scenarios in every deterministic cell:
wheel-version identity, the full lifecycle (init → gates → conflict
red → task close with receipt → verify → uninstall), the C-locale
round (LANG=C, Chinese notes/decisions — every tool alive, UTF-8
reports), eight-process lease contention (exactly one winner, seven
exit 3), TTL crash recovery, a REAL pre-push hook blocking a red push
and landing a green one (POSIX-legal in containers; the host suite
skips exactly this), worktree ledger anchoring (D32), and a 120-file
stats performance smoke. Cells: the five bases, a non-root variant
(user 1000), and an optional from-PyPI adopter install (network cell —
a mirror outage reports SKIP, never a red run; the deterministic cells
are what gate).

`tests/test_docker_e2e.py` wires the matrix into the regression suite,
opt-in via GOV_DOCKER_E2E=1: a matrix run builds images and takes
minutes — a deliberate act, not a default; without the variable the
test SKIPS naming why, never silently passes. run.sh's verdict is the
contract: deterministic cells must ALL PASS; FAIL anywhere is red.

Engineering findings baked into the harness (each cost a real
iteration): `[ ... ] @cap` alternations with top-level predicates
compile DEGENERATE in py-tree-sitter 0.26 — thousands of empty matches;
the working shape is capture + predicates on the inner pattern (learned
here, pinned by the shipped rules). Ancient wheels in `dist/` ride
along `pip wheel` output and install the wrong version inside the
image — the build removes them first. And task receipts live in the
card JSON, so a close dirties the tree — the lifecycle commits after
close before any receipt verify (the receipt contract working, the
hard way).

## Alternatives considered

- **Run the matrix in GitHub CI unconditionally** — ubuntu runners have
  Docker and can reach Docker Hub directly, so the wrapper is one env
  var away; but the matrix costs ~6 minutes and image pulls, and the
  CN-mirror default is host-specific. Landed as opt-in; CI wiring is a
  one-line workflow step left to the maintainer.
- **Vagrant/VMs instead of containers** — heavier, slower, and the
  platform axes that matter (libc flavor, locales, users) are all
  expressible as images.
- **Extend the host E2E suite to spawn docker itself** — same thing
  with worse ergonomics; the wrapper already is that, one skipif deep.
