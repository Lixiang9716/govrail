# Agent Note: gov parse names its uncovered files and declares its grammars

Status: implemented

## Problem

Two follow-ups to the parse primitive, both from the first real
consumer (dsh-mobile's code-size gate batched `gov parse --json`):

- #270: a directory walk silently omitted files whose language has no
  shipped grammar — the JSON reported `files` with no trace of the
  `.swift`/`.kt`/`.txt` files the walk SAW and did not parse. A
  consuming gate could not distinguish "parsed clean" from "never
  parsed at all", and silently degrades to not-covering exactly the
  files the project is about to add (dsh-mobile's Swift/Kotlin hosts
  are planned).
- #269: nothing in the CLI surface named the shipped grammars — a
  custom-gate author discovered the inventory by listing
  site-packages directories.

## Decision

Directory walks now compute the honest complement: one os.walk under
the target with the union of pack excludes pruned and symlinks
skipped (the same traversal contract as parse._walk), minus the
claimed set — each uncovered file becomes a `skipped` entry
(`{path, reason: "no grammar for <ext>"}`). The `--json` output is now
an object: `{"files": [...], "skipped": [...]}` — a shape change, taken
now while the command is one release old and its only consumer asked
for the field. The human report gains a coverage line ("N file(s) not
parsed — no shipped grammar matches their type") plus per-file names.
`--help` and `--lang` carry the runtime inventory (`shipped grammars:
c, cpp, go, ...` derived from the installed packs), and the README
declaration lists it too. Shape note: `parse_report` now returns
`(reports, skipped)`.

## Alternatives considered

Only aggregate skipped counts (no per-file list) — rejected: a gate
that wants to fail loud on an uncovered source file needs the paths;
counts re-create the silence one level up. Restrict skipped to
"code-looking" extensions — rejected: the plane does not guess which
uncovered file matters; the consumer filters. Register the passthrough
children's flags under the hub's registry entry by hand — n/a here but
the same principle: declared where listed, forwarded where consumed.
