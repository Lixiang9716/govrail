# Agent Note: check gate path exclusions: .gov/checks/exclude.json, counted SKIP, never invisible

Status: implemented

Related: D54, D15

## Problem

A project that legitimately tracks vendored upstream code had no honest
escape from the check gate. The parse layer's grammars lag real-world
module syntax (`export { _instanceof as instanceof };` — valid ES2015+
that node parses, that tree-sitter-javascript rejects) and type-level
`.d.ts` flourishes the lite grammars never cover, so a verbatim vendored
tree reads as unparseable. Every existing escape fails for vendored
bytes: `gov:ignore-check` markers live INSIDE the offending file and
editing vendored bytes is forbidden by pin discipline; `.gov/checks/<lang>.json`
is additive-only by design and cannot exclude paths or downgrade a
shipped rule. Adopters resorted to untracking the trees or pruning
copies — workarounds that only work when the file SET is free to
diverge. Worse, the gap was path-sensitive: byte-identical content sat
green at a path that predated the diff scope and blocked the moment it
was copied to a path inside it (#347), because a change-scoped gate
judges history's paths, not contents.

## Decision

`.gov/checks/exclude.json` declares path exclusions:
`{"exclude": [{"path": "<glob>", "reason": "<why>"}]}`. The glob grammar
is the plane's one grammar (pathmatch, D15): `**` spans directories, a
slash-less pattern matches a basename, exactly like the parse packs. A
matching file is never parsed and never judged, in the change-scoped
default and the `--all` sweep alike. Every declared pattern surfaces in
every report — text gets `SKIP(excluded: <pattern> — N file(s) —
<reason>)`, JSON gets an `excluded` ledger — including patterns matching
zero files, so a stale exclusion nags instead of silently narrowing the
gate (counted, never invisible, the checks contract). Excluded paths
also drop out of the nolang count: one file, one line naming it.
Malformed config aborts named (rule 5): wrong shape, empty path or
reason, duplicate pattern. `.ets` joins `NOLANG_BY_EXT` as `arkts`
(#343's plane-side half): the shipped TypeScript grammar ERRORs on
ArkTS's `struct` declarations, so claiming ArkTS would manufacture reds
on every UI file — the honest face is the declared skip, like
Kotlin/Swift. The logging/code-size tools adopters wire themselves fix
their own extension lists; dsh-mobile's do (#343 tool side).

## Alternatives considered

- **`gov:ignore-check` in the vendored file** — rejected: it edits
  vendored bytes, which pin discipline forbids; the marker is for code
  the project owns.
- **Letting project rules override shipped ones (downgrade/exclude per
  rule)** — rejected, again: project checks are additive with distinct
  ids by contract; an override that flips a shipped rule's meaning must
  stay loud, and path exclusions are not a rule property anyway (they
  cut across every rule and the parse itself).
- **Shipping an ArkTS grammar and adding `*.ets` to the TypeScript
  pack** — rejected after the probe: tree-sitter-typescript produces
  three ERROR nodes on a canonical `struct Index { ... }` file, so the
  parse-errors rule would block every ArkTS UI file the moment the glob
  landed. A skip that says itself beats a coverage claim that lies.
- **Excluding silently (config only, no report line)** — rejected: an
  exclusion that shrinks the gate without a trace is the vacuous-green
  shape rule 6 exists to kill.
- **Re-scoping the check gate to content hashes to fix #347's
  path-sensitivity directly** — rejected: a change-scoped gate judging
  the diff is the adoption-critical design (a fresh install must not go
  red on code it never changed); the exclusion gives verbatim trees a
  first-class declaration instead of bending the scope model.
