# Postmortem 0001: the required check abstained, and abstention merged

## Executive summary

PR #290 landed on master with red CI on the record. The required check — the
`gates` summary job — never voted: it depended on the failed `lint` job,
GitHub's default semantics skip a job whose dependency failed, and branch
protection counts a skipped required check as satisfied. Auto-merge therefore
landed the PR two minutes after it opened, with `lint: failure` and eight
failing `e2e-docker` matrix cells visible on the head commit but consulted by
nothing. Three independent defects had to co-operate: a summary whose failure
behavior was "abstain", a merger whose semantics count abstention as passage,
and a verdict scope maintained as a hand-written needs list that left part of
the workflow outside it. #294 fixed the instance (the 69 ruff findings; lint
gate-ized into the local DAG), #296 fixed the mechanism (`if: always()` plus a
verdict over every job). The durable lesson: **a required check that can skip
is not a gate — to the merger, abstention is passage.**

## Timeline

Evidence is the check-run record on the PR head (`04ce396`) and the workflow
file as it stood at `f80c2b9` (pre-fix master).

- 2026-09-18 20:13 UTC — PR #290 opened (squash, auto-merge enabled).
- Same run — `lint: failure` (69 ruff findings from the refactor); `gates:
  skipped`, because its `needs: [lint, gates-cell, governance, derive]`
  (`.github/workflows/ci.yml` at `f80c2b9`) included the failed job and no
  `if: always()` existed to override the default skip; `e2e-docker`: 8 of 10
  matrix cells `failure` — outside the needs list, invisible to any verdict.
- 20:15 UTC — auto-merge lands `6fb6fba` on master. The required check's
  record reads `skipped`, which satisfies protection; the red jobs are never
  consulted. 69 ruff findings are now on master.
- 20:36 UTC — PR #294 opens: the findings fixed, and the ruff CI job adopted
  into the plane as the blocking `lint` gate with a rejection case — the
  local pre-push DAG now sees what CI sees (lands as `8a85f1d`, recorded
  under D61).
- 2026-09-19 03:20 UTC — PR #296 opens against the mechanism instead of the
  instance: `gates` needs all 11 jobs, `if: always()` makes the summary
  render its verdict even when a dependency failed, and the verdict goes red
  on any `failure`/`cancelled` across `needs.*.result` (lands as `5266655`).
- 03:29 UTC — #296 merged; task card T-0003 closed on an all-green receipt
  (`106ede8`).

## Root cause

One class, three instances of "an enforcement surface whose behavior under
failure was never specified":

1. **The summary abstained.** The `gates` job declared no failure behavior,
   so it inherited GitHub's default: skip when a dependency fails. A summary
   built to aggregate a failure went silent under exactly the condition it
   existed for.
2. **Abstention satisfied the merger.** Branch protection requires named
   checks; a check reporting `skipped` is not a failure, so protection
   passed. The gate had two exits from a red world and only the loud one was
   guarded.
3. **The verdict scope was hand-maintained.** `needs` listed four jobs of
   ten; `e2e-docker`'s eight red cells never reached any verdict. An
   aggregate whose membership is curated by hand lies silently at the moment
   a new job is added — the moment attention is elsewhere.

The general form, recognizable next time: every aggregate verdict must
specify its behavior under failure (always render, fail loud — rule 5
applied to CI), must be computed over the closed set of the thing it judges
rather than a curated subset, and every CI-only check needs a home in the
local plane, or the pre-push gate and CI judge different worlds.

## Guardrails added

- **The summary cannot abstain:** the `.github/workflows/ci.yml` gates job
  carries `if: always()`, needs all 11 jobs, and verdicts red on any
  `failure`/`cancelled` over `needs.*.result`, tolerating only conditional
  skips (PR #296; note
  `.agents/notes/implemented/process/2026-09-19-ci-auto-merge-gates-job.md`;
  task card T-0003 closed on an all-green receipt).
- **CI-only checks got a local home:** the `lint` gate — blocking,
  dogfood-only, wired into `modes.all`, with its rejection case
  `.gov/rejections/case-lint.sh` (PR #294; D61; note
  `.agents/notes/implemented/architecture/2026-09-19-code-design-contracts.md`).
- **Residual, documented:** the needs array is still hand-written (GitHub
  has no all-jobs wildcard); the mitigation is that omitting a job is a
  visible one-line diff, and the gates job's comment in
  `.github/workflows/ci.yml` states the standing rule — a new CI job's
  discovery surface includes the gates needs list.
