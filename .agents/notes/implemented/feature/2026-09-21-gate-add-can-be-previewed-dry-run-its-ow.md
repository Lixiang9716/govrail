# Agent Note: gate add can be previewed: --dry-run, its own grammar in --help, and --command

Status: implemented

Related: D29, issue #366

## Problem

`gov gate add` had no preview and no self-documenting help. Its grammar —
the gate's argv goes after a standalone `--`, with `id` before the options
— lived in a source comment and the subparser's prose, so `--help` showed
`... id` with no command and no separator. The only way to exercise the
command was to run it for real: it writes `gates.json`, then runs
`gov run --gate <id>` as its verification step. In a governed repository
`gates.json` is sealed, so **confirming a proposed wiring** — the exact
invocation quoted in a PR body, a review, or a scripted proposal — cost a
recorded re-baseline ritual. The reporter had to state the command as
"untested by construction" precisely because testing it would have
drifted the constitution.

## Decision

- **`--dry-run`**: validates everything the real run validates (id shape
  and uniqueness, the command's presence, glob compilation, mode
  membership) and prints the entry that WOULD be appended, the mode
  memberships it would join, and the exact verification argv — then
  writes nothing and runs nothing. A preview that skipped validation
  would confirm nothing, so the same guards run first.
- **The grammar documents itself**: the subparser's `usage=` is
  `gov gate add <id> [options] -- <command...>` and its epilog carries
  two worked examples. Agents and CI wrappers enumerate help output, not
  source — the flag registry, the router skill and this note follow from
  the same rule as any new surface.
- **`--command` is the same separator, spelled**: a caller building argv
  programmatically cannot always emit a bare `--` positionally (the split
  happens before argparse, so an argument that happens to look like a
  flag cannot be misread as one).

## Alternatives considered

- **A separate `gov gate preview` subcommand** — rejected: `--dry-run` is
  the contract every other mutating command in the plane already speaks
  (`gov update`'s dry run, `gov init --upgrade`'s report), and a second
  entry point would duplicate the validation it must not diverge from.
- **Print `--help` and let the caller parse the source** — rejected: the
  point of the issue is that the sanctioned invocation must be obtainable
  from the tool, not from site-packages.
- **Make the verification run optional (`--no-verify`)** — rejected: the
  prove-it-can-run step is what makes the wiring trustworthy; the dry run
  answers "what would you do", not "is it live".
- **Auto-baseline the seal after a write** — rejected outright: the
  re-baseline is a recorded ritual under `gov verify-plane --write` and
  never a side effect of a feature command; the dry run exists so the
  ritual is not needed for a PROPOSAL.
