# Agent Note: the plane seals itself, and the hooks obey the config

Status: implemented

## Problem

The plane's tamper-evidence stopped at archived notes: `gates.json` and
`.gov/rules.md` — the files that DEFINE the gates — could be edited or
gutted by any agent with nothing but review to notice. The pre-commit
hook hand-wired `verify-pairing --staged || status=1`, ignoring
`allowFailure`: a pure-English repo's first docs commit was rejected by
a gate its own config called advisory. The shipped gate set made every
adopter run govrail's own 53-case self-test on every push, and the CI
template installed govrail unpinned — one bad release, every adopter's
CI red at once. Hooks were installed blind to `core.hooksPath` (written
where husky users' hooks never run) and linked worktrees were refused
outright while doctor claimed to be worktree-aware. init seeded neither
`docs/decisions.md` nor `docs/postmortem/`, so recall's memory plane
pointed at files that did not exist, and the run ledger rode every diff
as untracked noise because init never managed `.gitignore`.

## Decision

`gov verify-plane` seals `.gov/rules.md`, `gates.json`, and
`.gov/pairing.json` into `.gov/plane-seal.json` (written by init, or
explicitly via `--write`); drift — edits, deletions, unsealed new
configs — is a named red, and preset apply extends an intact seal
chain automatically while refusing to launder accumulated drift.
Enforcement is OUT-OF-BAND by design (the reflexive gap: the in-DAG
`plane` gate lives inside the sealed `gates.json`, so tampering that
disables its own detector would otherwise go silent) — `gov run`
checks the seal BEFORE parsing the config, and the pre-commit runner
checks before reading the staged gate list; neither trusts anything
from gates.json to judge it. Deleting the seal file itself is the same
attack one level up (N2): a plane config whose seal is GONE is
nominated drift by the constitution's presence
(`.gov/rules.md` exists → the seal must too), while bare gates.json
scratch configs stay unsealed by design. The
pre-commit hook delegates to `gov hooks pre-commit`, which runs every
gate declaring `"stages": ["pre-commit"]` under its configured
advisory/blocking contract — flipping pairing to blocking is the
documented remove-`allowFailure` step, not a hook edit. The template
DAG drops the vendor self-test (govrail keeps it in its OWN gates.json)
and the CI template pins `govrail==<init-time version>`. init resolves
the real hooks dir (`core.hooksPath`, else the common dir — worktrees
included), seeds the decisions log (in the loader's
default sections format, with a D0 "adopt the plane" entry — no format
declaration file for a fresh install to trip over) and the postmortem
README so recall has a corpus on day one, appends
`.gov/history/` to `.gitignore`, and prints that the shipped gates
guard the governance plane — wire your own test/lint gates (presets
ship typed starters, now on `python3`).

## Alternatives considered

Seal via the manifest's existing template hashes — rejected: those are
provenance records with no verifier; a seal nobody checks is rule 6's
vacuous script. Keep self-test in the template but path-scoped —
rejected: any scoping still couples adopters' pushes to the vendor's
test suite; the vendor's gates.json is the right home for the vendor's
tests. Refuse worktree installs with a clearer message instead of
supporting them — rejected: parallel-workers explicitly assumes
worktrees, and the common-dir hooks resolution is three lines once
`core.hooksPath` is honored anyway.
