# Agent Note: the pairing config init always writes: rules.md's reference is true now, and the next-steps signal is evidence, not configuration

Status: implemented

Related: D37, issue #367

## Problem

Three generated facts did not fit together. The shipped `rules.md` says
the naming conventions are "declared in `.gov/pairing.json`"; the shipped
`gates.json` lists that file in the `paths` of two gates; and `gov init`
never created it while `verify-plane` requires the file to be inside the
seal if it exists. So an adopter who made the sentence true by writing the
file — with content identical to the defaults it overrides — triggered
`plane config is not sealed` and had to perform a recorded constitution
re-baseline to add a no-op config. The alternative was leaving a
reference that can only mislead, which is what the reporter did while
auditing doc-vs-code drift.

## Decision

- **`gov init` writes `.gov/pairing.json`** with exactly the tool's
  `DEFAULT_CONFIG`, so the file rules.md points at exists from init
  onward, the gates' `paths` entries describe a file that is really
  there, and editing it is how a repo changes the conventions. It is a
  normal template: `gov init --adopt` lands it where it is missing
  (`gov update --apply` adopts and re-seals in its own ritual), uninstall
  removes it, and drift is reported like any other shipped file — a
  defaults change upstream surfaces as a decision point rather than
  silently re-typing every adopter's behavior.
- **The init next-steps signal changed from configuration to evidence.**
  `has_pairs` used to include "a `.gov/pairing.json` exists" as a proxy
  for "this project cares about pairing"; with the file always present
  that proxy turns every monolingual project into a paired one and hands
  it baselining advice that fails on day one (#315's branch exists to
  prevent exactly that). The branch now keys on real counterparts
  (`*.zh.md`) or records (`*.i18n.yaml`).
- Two tests pin the pair: init writes the defaults (and the written
  content EQUALS `DEFAULT_CONFIG`, so the explicit file cannot silently
  re-type behavior), and `--adopt` lands it where it is missing.

## Alternatives considered

- **Soften the wording instead** (the issue's option 2) — rejected as the
  whole fix: it leaves the gates' `paths` entries pointing at a file that
  is expected to be absent, and it removes the obvious place a repo
  changes the conventions. The wording was not the defect; the missing
  file was.
- **Treat a defaults-identical config as not requiring a seal** (option
  3) — rejected: the seal's rule is "an existing plane config is sealed",
  and a content-dependent exemption would make the seal's verdict depend
  on a diff nobody records. Sealing at init (before any seal exists) is
  the honest ordering.
- **Have init write an empty `{}`** — rejected: a config that changes
  nothing when empty teaches nothing; the defaults written out are the
  documentation of what the conventions ARE, which is what rules.md
  promises a reader will find there.
- **Leave it absent and let the first `gov verify pairing --write` create
  it** — rejected: that command's job is confirming a pair, not seeding a
  config, and it would leave the file's content decided by whichever
  command happened to run first.
