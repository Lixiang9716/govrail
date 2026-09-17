# Agent Note: round-10 follow-up — containment over the whole path, not just the last name

Status: implemented

Related: D56

## Problem

The review of the symlink fix (#243) reproduced its own incompleteness
in both directions. First, the directory variant: `.gov/history`
ITSELF symlinked outside the repository routed the full gate record to
an external file — `O_NOFOLLOW` and a final-component lstat are blind
to a linked DIRECTORY, and the round-10 fix had checked only final
components. Second, AGENTS.md: the reference-line injection read
through a user's symlink and wrote the gov line into their managed
dotfile — the exact `.gitignore` attack shape from the original
finding, one file over, missed because the fix enumerated instances
instead of walking the class (N12's structural pattern, again, in the
fix of the finding that named the pattern). The round-10 note's
rationale — containment "adopted only where a READ can leak" — was
refuted by the first probe: the write half leaks too.

## Decision

`atomicio.assert_contained` walks every component of a state path
between the owning work-tree root (resolved from the path itself via
`gitutil.toplevel(start)`, so a caller may sit elsewhere) and the
final component, refusing any link; outside any repository there is no
inside and the check steps aside. It gates all three write entries
(`append_line`, `write_text`, `write_bytes`) and the ledger
prechecks in gates and receipt — the seal, sidecar, and manifest
writes inherit it through the same core. init pre-flights a symlinked
AGENTS.md beside the `.gitignore` one, the AGENTS.md writes go through
the atomic contained writer, and uninstall refuses to edit through the
link (the line lives in a file the plane does not own). Tests pin the
directory variant at helper, ledger, and CLI layers with the external
directory proven empty.

## Alternatives considered

Resolve-and-prefix (realpath the parent, require it to start with the
work-tree root) — rejected for this layer: resolving follows exactly
the links being judged, so the verdict depends on the attacker's own
links, and macOS's symlinked `/tmp` made the naive version refuse
legitimate scratch writes; component lstat-walking between root and
final judges the links themselves. Fix AGENTS.md by writing through
the link deliberately (the line "belongs" in the file the operator
shows the plane) — rejected: writing a user's managed dotfile silently
is the N13 defect regardless of who owns the path's name. Leave the
directory variant documented as accepted risk — rejected: it is the
same exfiltration channel as the file variant the round already
declared a blocker, one `ln -s` away.
