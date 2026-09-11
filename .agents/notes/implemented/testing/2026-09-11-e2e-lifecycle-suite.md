# Agent Note: end-to-end lifecycle suite — the plane driven as an adopter drives it

Status: implemented

Related: D54 (the parse-layer features exercised here through the CLI),
D43/D52 (task lifecycle and the claim race), D44 (run receipts), D51
(run --merge), D53 (presets), D28 (what the template ships), rule 6

## Problem

The suite had strong unit/feature coverage (470+ tests, mostly
subprocess-level per mechanism) but nothing that walked the JOURNEY an
adopter walks: init a fresh project, govern real work, delegate to a
second agent, adopt a preset, upgrade. Whole-journey failures were
catchable only by hand — and indeed this suite's first run caught a real
one immediately: `gov init --upgrade --json` crashed with
UnboundLocalError whenever any file DIFFERED (a variable assigned only on
the human-report path), on a documented machine surface no test drove
end-to-end.

## Decision

`tests/test_e2e_lifecycle.py` — three acts, each a fresh git project,
every interaction through the CLI (exit codes + printed output), portable
by construction (git + the interpreter only; hook EXECUTION stays with
the dedicated hook tests):

- **Act 1, adopt and govern**: init (and its idempotent second run),
  doctor (including the D54 parse-layer report), pairing baseline →
  drift red → scoped fix, note scaffold + format gate, note-presence's
  advisory warn/ok cycle, the full template gate DAG green, conflict
  markers red with file:line then resolved, decisions numbering + table
  guard, the archive seal (including tamper-red and honest re-seal), the
  task lifecycle (claim → busy-for-the-second-worker → release → close
  whose gate run writes the receipt), run receipts verified on HEAD,
  trend, stats, check, whatsnew, and the uninstall roundtrip (the
  project's own files stay).
- **Act 2, parallel agents**: lease locks end-to-end (busy exit 3,
  wrong-holder release exit 2, lazy takeover after TTL expiry), the task
  claim race, and run --merge preflighting a clean union (exit 0) and
  catching a conflicting one (exit 1, scene kept and inspected).
- **Act 3, presets and upgrades**: preset discovery, refusal outside an
  initialized project, additive apply (gate in governance mode, skill
  bytes, manifest hint), idempotent re-apply, a governance-mode run, and
  `init --upgrade` human + `--json` surfaces.

Two journey facts the acts now pin: `task close` REFUSES while any gate
is red (the test experiences the refusal by forgetting a pair baseline —
the design working), and `whatsnew`'s default `since` is the manifest's
init version (a governed project asks for older versions explicitly).

The first run also taught the fixture a real lesson: a project README
without a zh counterpart makes `verify-pairing --write` exit 1 (wrote 1,
left 1 unpairable) — the fixture project is bilingual from birth now.

## Alternatives considered

- **One test per feature step** — clearer isolation, but the value here
  is precisely the STATE CARRYING FORWARD (a note committed early
  changes what note-presence sees later; a baseline must survive later
  work). Acts keep the journey coherent; a failure names its step.
- **Drive the installed wheel instead of `-m gov`** — the wheel story is
  exercised by the CI install steps and the backport-shadow job; pinning
  the suite to the checkout keeps it runnable pre-install.
- **Add hook execution** — already covered portably by the dedicated
  hook tests; duplicating it here buys nothing and costs POSIX coupling.
