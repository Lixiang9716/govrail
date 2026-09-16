# Agent Note: test execution runs in parallel — and the move exposed a leaking guard

Status: implemented

## Problem

Wall clock was paid serially everywhere. The host suite (546 tests, all
subprocess-heavy: in-process gov invocations, scratch git repos, a 10s
timeout case) ran in single file order for ~53s on every version cell
and platform job; the docker e2e suite ran its 105 scenarios one at a
time inside every one of ten cells (~100s each on the critical path).
Parallelism was also the only way this class of waste becomes visible:
under `-n 4`, one test that serial ordering had silently broken ran
the way it was designed to — `test_every_released_tag_has_a_highlights
_section`, the version-alignment guard, was skipping in serial mode
because four `-C` flag tests chdir the PROCESS (the flag's whole point)
and never restored it, leaving every later test in a deleted tmp dir
where `git tag` returns nothing. The guard had been vacuously skipping
since it landed — rules 5 and 6's exact anti-pattern.

## Decision

Host suite: pytest-xdist in the dev extras; every CI pytest step runs
`-n auto` (4 workers on hosted runners; 53s -> 20s at -n 4 locally, and
every gates-cell/platform job pays it). The docker e2e suite: scenarios
run in a process pool (`GOV_E2E_JOBS`, default min(cpu, 8)), with two
ordering rules — `fresh_project` uses `mkdtemp` instead of a global
counter (a fork inherits the counter and two workers collide on
`proj-N`), and TIMING_SENSITIVE scenarios (`perf_*`,
`gate_timeout_enforced` — assertions that measure wall time) run
serially, alone, BEFORE the pool starts so pool load cannot distort
their budgets. Inner suite: ~100s -> 20s. Two invariants pin it: a CI
pytest step without `-n` goes red, and the `-C` tests now restore cwd
by fixture. The new invariant immediately caught its author: a step
name containing a colon-space broke the YAML again, exactly the
incident the CI-health suite was written for.

## Alternatives considered

Split the pytest suite across more CI jobs — rejected: setup (install,
checkout) is paid per job, and xdist gets the same overlap inside one
job for free; the matrix already parallelizes versions and platforms.
Threads for the docker scenarios — rejected: the scenarios fork git/gov
subprocesses and set process-global state; a process pool isolates
cwd, env, and the module-level caches, and a crashed scenario cannot
poison its siblings. Parallelize the timing-sensitive scenarios too —
rejected: their budgets measure wall time, and pool contention turns
them into coin flips; five scenarios stay serial at negligible cost.
