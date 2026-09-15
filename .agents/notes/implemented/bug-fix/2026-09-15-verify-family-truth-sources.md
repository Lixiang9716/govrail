# Agent Note: verify family — the index is the truth, unreadable is exit 2

Status: implemented

## Problem

The verify gates treated working-tree content, third-party data, and
hand-edited manifests with a double standard the plane's own rule 5
forbids. `--staged` judged worktree bytes, so bad content staged and
then reverted read green. `archive-notes` re-sealed only entries that
existed on both sides, so `rm archived/foo.md` plus a re-seal washed a
frozen note off the books with exit 0. A non-UTF-8 source file or BOM'd
rubric crashed gates with bare tracebacks — indistinguishable from real
violations and against the 0/1/2 contracts. note.py kept a private
decision-table parser hardcoded to docs/decisions.md that disagreed
with the configured loader, and read "table parses to zero entries" as
"every D-ref is dangling". Loose notes at the notes root were invisible
to both the placement and format checks. A hand-mangled archive seal
crashed `entry.get` instead of reporting tampering. doc-sync hardcoded
govrail's own HIGHLIGHTS layout (adopters ate a permanent red they
could never turn green), the table alternatives check searched the
whole file so one stray word exempted every row, table titles always
read "D14 — D14", and doctor checked a hardcoded path with a NameError
trap in the parse check.

## Decision

`--staged` reads the index everywhere (pairing compares `ls-files
--stage` oids, markers scan `git show :<path>` bytes). archive-notes
treats sealed-but-gone files as drift and refuses without
`--rebaseline`. Every verify main funnels `(OSError, UnicodeDecodeError,
JSONDecodeError)` to a clean exit 2, and content reads are `utf-8-sig`
across the board (BOM tolerated, strict decode preserved). note.py
delegates to `decisions.load()` — one parser, configured path — and
names a zero-entry table instead of dangling every reference.
verify-notes flags and format-checks loose root notes; verify-archive
reports malformed seal entries as violations; doc-sync takes
`.gov/decisions`-style configuration (`.gov/docsync.json`) and runs
named-green when not configured. The alternatives column counts only
when the table's HEADER row declares it; table titles come from the
second cell; doctor checks the configured decisions path and imports
parse outside the try so a failure names itself.

## Alternatives considered

Per-file skip-with-warning for unreadable inputs — rejected: a gate
that silently scans less than it claims is rule 5's exact failure;
exit 2 names the broken prerequisite and blocks the signal. Glob-based
exclude for docs/postmortem — rejected for now: pairing excludes are
exact strings today; changing their semantics belongs to its own
decision, so the seeded README path is excluded literally. Auto-detect
the decisions format — rejected: guessing formats is how the three
glob grammars happened; the seed ships the declaration instead.
