# Agent Note: hook wiring keeps its promise: update --apply re-wires from the template; init --hooks stops implying claude

Status: implemented

Related: D60, D34, issues #373

## Problem

Two behaviours of the hook-wiring path, both hit while migrating a
repository 0.47.1 → 0.48.0. First, the drift note says "`--apply`
re-wires it (or run `gov init --hooks`)" — but `--apply` finished with
"done" while `.gov/hooks/pre-push` was byte-identical to the OLD
version's content. The #331 re-wire copies the TRACKED copy over the
EXECUTED one; the tracked copy itself was never refreshed from the
shipped template, so the migration re-wired the executed hook to the
very bytes the note promised to replace. Nothing in the output said the
promise went unkept — an afternoon spent believing a migration had done
something it had not. Second, on a plane initialized WITHOUT any agent
platform, `gov init --hooks` printed "created .claude/settings.json":
the retrofit path kept the pre-D60 default (claude riding along with
any add-on), so re-wiring a git hook adopted a repo-visible platform
config the caller never asked for. A fresh init has been explicit
opt-in since D60; the retrofit path silently disagreed with it.

## Decision

- **`gov update --apply` now keeps the drift note's promise.** The
  migration refreshes each tracked gov hook copy
  (`.gov/hooks/pre-push`, `.gov/hooks/pre-commit`) from THIS version's
  shipped template before #331's executed-copy re-wire runs, so both
  copies end on the same bytes. The contract is `gov init --hooks`'s
  own: a copy without the `# govrail:` marker is someone else's hook —
  named skip, never overwritten. The dry-run/apply report still names
  the drift; the apply now also says how many tracked copies it
  refreshed.
- **The platform retrofit is explicit opt-in only.** `_add_ons`
  installs platform configs for exactly the `--platforms` list and for
  nothing else: `platforms=None` now means "no platforms", matching the
  fresh-init contract D60 already set. The git-hook verb no longer
  implies the platform verb; an adopter who wants agent hooks names
  them.

## Alternatives considered

- **Only fix the message** ("say `re-wire with gov init --hooks`
  instead of naming `--apply`") — rejected: the capability and the
  migration step both exist; a migration that reports drift and then
  tells the adopter to run a second command for a step it could perform
  is the promise-shaped hole the issue cost an afternoon in. The note
  text stays as written because it is now true.
- **Refresh the tracked hook only when a manifest hash proves it
  un-customized** (the D34 `templates` record) — rejected as the gate
  for THIS step: hooks predate the manifest's template-hash record in
  live repos (govrail's own manifest carries no hook entry), so the
  hash test would refuse exactly the migration the bug report came
  from. The marker test is the customization line the plane already
  draws for `gov init --hooks`; a project that customized a gov-marked
  hook in place has always been one `gov init --hooks` away from the
  same overwrite.
- **Default the retrofit to the last-used platforms** (read them from
  the manifest) — rejected: a repo initialized pre-D60 has `claude` in
  its manifest without ever opting in at the current vocabulary; replaying
  that stale list re-creates the file this fix removes, and a fresh
  repo with no platforms would stay platformless anyway — two repos,
  two invisible rules.
