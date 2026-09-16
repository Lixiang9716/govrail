# Agent Note: the README command reference is generated from gov --help

Status: implemented

## Problem

The documentation had drifted from the CLI surface it describes: `gov
--help` still described `note` as "(new/check)" two releases after
list/show landed, `verify-plane` still named a two-file seal long after
the surface grew to five, and `receipt` never listed its subcommands.
The README's curated quick-start lacked the newest load-bearing
commands entirely. Every fix so far was hand-synced prose — the same
copy-paste drift pattern the audit's H1 finding described for code,
reproduced in docs: multiple hand-maintained copies of one truth.

## Decision

`gov --help` (the descriptions in `gov/cli.py`) is the single source of
truth. README.md carries a generated command block between `gov:commands`
markers, rendered by `scripts/update_readme_commands.py` with COLUMNS
pinned to 80 so the render is byte-identical on every machine and in
CI. Four consistency tests (tests/test_docs_cli_consistency.py) turn
drift red in the host suite: a stale block, any `gov ...` citation in
the doc set that does not resolve (command, subcommand, or flag), a
help line whose one-line description omits a real subcommand, and the
Chinese README citing commands the generated surface no longer has.
The stale descriptions themselves were fixed at the source (note,
verify-plane, receipt) — the machine caught receipt within minutes of
the test existing. CONTRIBUTING (en + zh) documents the contract: edit
cli.py, run the script, never touch the block.

## Alternatives considered

Hand-fix the drifted docs — rejected: it re-creates the drift cycle
this note exists to end; the third hand-sync would already be wrong
again. Generate the curated quick-start too — rejected: its per-command
usage comments carry narrative value a generator cannot produce; only
the exhaustive reference is mechanical, so only that is generated.
Make it a `gov verify-cli-docs` gate for adopters — deferred: adopters'
docs do not cite gov commands the way this repo does; if the pattern
recurs in the wild, promoting the test into the shipped gate set is a
small step.
