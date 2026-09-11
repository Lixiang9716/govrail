# Agent Note: project rejection cases cover every shipped gate

Status: implemented

Related: rule 6, D30 (the coverage ledger), #18/D32 (undeclared cases),
#168 (the deferred Windows semantics for this family), the two cases that
predated this round (`case-conflict-markers.sh`, `case-pre-commit-hook.sh`)

## Problem

This repository's own coverage ledger read `NONE — rule 6` for eight of its
ten gates: only `pairing` (via `case-pre-commit-hook.sh`) and
`conflict-markers` had a project case. The tools family ships 49 cases, so
rule 6 held for the product — but the repository that *ships* the rule was
20% covered by its own last mile, and the gap was invisible by design: the
ledger is advisory (D30), so CI stayed green while an adopter reading the
ledger saw the plane's own repository doing what the plane tells them not
to do. The one open issue (#167) was filed *from* that ledger.

## Decision

Eight cases under `.gov/rejections/`, one per uncovered gate (`self-test`,
`notes`, `note-presence`, `rubric`, `archive`, `decisions`, `task`,
`doc-sync`), each declaring its gate in the first five lines. Every case
runs the gate as the CLI (`python3 -m gov <cmd>`) against a scratch project
under `mktemp -d`, introduces the violation, asserts the red by exit code
*and* by the finding naming its offender (the missing section, the drifted
file, the stale card id, the unpaired version), and — where the gate can be
green on a fixture — runs the well-formed fixture first so the red is
proven earned rather than vacuous. The ledger now reads `gate(1)` across
all ten gates.

Conventions the family already had: POSIX `sh`, shebang on line 1, the 10s
budget, the package resolved through `PYTHONPATH=$repo_root` (the ambient
`gov` may be older), and `repo_root=$(pwd)` because self-test runs cases
with the repository root as cwd.

One trap is worth its own line, since the case documents it: the
note-presence case captures every command's output in a shell variable,
never in a file inside the scratch. A written `out.txt` is an untracked
file, which makes the worktree dirty, which moves the gate's auto base to
`HEAD` and puts `out.txt` itself into the reviewed diff — the first draft
asserted on `app.py` while the gate was naming `out.txt`.

The deferred rule-6 decision stands unchanged: these are `.sh` by the
project-family convention, so the Windows CI job still runs
`gov self-test --scope tools`, and teaching self-test a named SKIP for
OS-unrunnable cases (or shipping a `.bat` shim) remains the designed-once
decision #168's CI comment describes.

## Alternatives considered

**Python cases (`case-*.py`) throughout.** The harness accepts any
executable file, but nothing in these proofs needs Python beyond the `gov`
CLI itself, and the two existing project cases set the shell convention —
following it keeps the directory readable as one family.

**Porting the project family to Windows in this round.** That is the
deferred semantics decision (#168): it wants one designed mechanism (a
named SKIP vocabulary in self-test, or a Windows shim), not eight
per-case workarounds. Taking it here would have replaced an open question
with eight local answers.

**Making the ledger block on uncovered gates.** Rejected in D30 — during
ramp-up that pressure deletes gates instead of adding cases — and it is the
wrong instrument besides: the ledger's job is to name the gap, not to be
the gate on its own coverage.

**Driving the cases through pytest instead.** The tools family already
does that. The project family exists to prove the gates *without* the test
harness — that is rule 6's last mile, and a project that cannot run
pytest must still be able to prove its own gates.
