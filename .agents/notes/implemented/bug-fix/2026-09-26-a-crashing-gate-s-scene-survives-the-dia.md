# Agent Note: a crashing gate's scene survives the diagnostic rerun: last-run rotates, the hook names the evidence

Status: implemented

Related: D21, issues #394, #396, #375

## Problem

Two surfaces, one diagnosis loop, both seen in the field on the same
transient crash (a `code-size` gate printing a bare
`Traceback (most recent call last):` header, passing standalone seconds
later, ~1 in 6-8 full runs). On the hook surface, a red push showed one
summary line; on the run surface, the crash body was erased by the very
rerun taken to diagnose it — `.gov/last-run/<gate>.log` was CLEARED per
run (#375's design), and the passing rerun's output overwrote what
remained. A transient crash was undiagnosable without luck: the
evidence window closed the moment you opened it.

On the capture side the runner is clean — `communicate()` drains both
pipes to EOF and the full captured output flows to the report, the
ledger, and the evidence file. What the runner captured here was
genuinely one line: the loss happens inside the gate's own process tree
(concurrent parse workers writing one capture pipe, a child killed
mid-traceback), which is adopter tooling, not the runner.

## Decision

- **`.gov/last-run/` rotates instead of deleting.** Every log this run
  would disturb — a stale gate's file, or a failing gate's scene about
  to be overwritten by a passing rerun — moves to `<gate>.log.prev`.
  One generation back, bounded by the gate count. A red run's report
  says where the evidence lives (`evidence: .gov/last-run/<gate>.log …
  previous generation *.log.prev`), so the crash scene and the clean
  rerun sit side by side.
- **The pre-push hook names the evidence on red.** `gov_cmd` no longer
  `exec`s (a hook that cannot react to the run's own code cannot point
  anywhere), and every DAG invocation funnels through `run_dag`: on a
  red run it prints the evidence paths once and exits with the run's
  own code — the push is refused exactly as before, with somewhere to
  look. The env-declared scope is unchanged on every branch
  (`GOV_CHANGE_BASE` + `GOV_CHANGE_ROOT`, per #371).

## Alternatives considered

- **Serialize or buffer the gate's subprocess output on the runner
  side** (the issue's suggestion) — nothing to serialize: the runner
  already drains to EOF; the interleaving happens inside the gate's
  own process tree. The adopter-side fix (per-worker buffers dumped
  verbatim on crash) is real, and it is the adopter's file; the
  runner-side job is to keep whatever arrived.
- **Keep N generations** (`.log.1`, `.log.2`, …) — rejected: the
  diagnosis loop needs exactly two points (crashed then passed); an
  unbounded history re-creates the `.gov/history/` ledger's job with
  worse tooling, and the ledger already records every run verbatim up
  to its cap.
- **Have the hook tail the failing gates' logs itself** — rejected:
  the hook would re-parse the run's output to learn which gates failed,
  a fragile sh contract; `gov run` already prints the full failing
  output inline (#109/#317) and now names the evidence directory, and
  the hook's one line points there.
