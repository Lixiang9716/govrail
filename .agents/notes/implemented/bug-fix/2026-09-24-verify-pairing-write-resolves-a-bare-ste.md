# Agent Note: verify pairing --write resolves a bare stem against the include scope and names the roots it tried

Status: implemented

Related: D28, issues #379

## Problem

`gov verify pairing --write <pair>` tripped an agent mid-landing a
bilingual pair: two exit-2 rounds before the cd-to-root workaround, in
a flow where every other `gov` subcommand already accepts
root-relative paths from any CWD. The command announces the repository
root it anchors to, but a bare stem (`upstream-dsh-anatomy`) resolved
only against two literal guesses — the root itself and a flat
`docs/` — so a pair nested at `docs/research/upstream-dsh-anatomy.md`
was "no such pair source" even though the project's
`.gov/pairing.json` include patterns name exactly one such pair. And
when resolution failed, the diagnostic named the argument as a path
without saying WHERE it had been resolved against — the next
invocation was a guess.

## Decision

- **A bare stem resolves against the include scope.** After the two
  literal roots (repository-root-relative path, then the legacy flat
  `docs/` fallback), `_resolve_source` matches the normalized name
  against the pairs `.gov/pairing.json` actually declares; exactly one
  match wins. More than one match is an ambiguity, not a guess: the
  diagnostic names every candidate and asks for the
  repository-root path.
- **A failed resolution names where it looked.** The no-match
  diagnostic names the repository root (and the CWD too when anchoring
  could not make them the same thing) and the include scope that was
  searched. `--write` exits 2 on an unresolved name — a typo is a
  caller error, not a pair state.

## Alternatives considered

- **Print the resolved path on success** so mismatches surface that
  way — rejected: the success line already renders the record it wrote
  with the source path; a second echo of the same path is noise on
  every green run to debug one red shape the failure message now
  names.
- **Fuzzy/substring matching for stems** — rejected: `--write` mutates
  a record; a matcher that can pick a near-miss name is how the wrong
  pair gets re-confirmed. Exact basename against the declared scope,
  ambiguous → fail loud, is the same contract task-card resolution
  landed after its collision incidents.
- **Also resolve `en:`/`zh:` explicit paths against the include
  scope** — rejected: those arguments are paths the caller states
  outright (often outside the include scope entirely — the explicit
  registration exists precisely for convention-breaking names);
  second-guessing them would break the escape hatch the feature
  ships for.
