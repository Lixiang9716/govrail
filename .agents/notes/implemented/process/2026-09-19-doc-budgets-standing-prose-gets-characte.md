# Agent Note: doc-budgets: standing prose gets character ceilings

Status: implemented

## Problem

Standing prose in this repo is read on a cadence — the README on every
adoption, the constitution before every change, the router skill at
every session start — and it grows one "while we're here" paragraph at
a time. Nothing judged that growth: the size-limits gate (#265's
shape) covers code only, so a README or a SKILL.md could double
unnoticed while every consumer kept paying the reading cost forever.
The DSH comparison (the same sweep that motivated the postmortem
practice and the surprise ledger) found the exact gap filled upstream
by a doc-budgets mechanism: declared ceilings, enforced as a gate,
raised only as a reviewed diff.

## Decision

The `doc-budgets` gate (blocking, dogfood-only) reads per-file
character ceilings from `scripts/doc-budgets.json` and judges 20
standing docs — README pair, AGENTS.md, CONTRIBUTING pair,
architecture pair, truth-sources pair, tiers pair, postmortem README
pair, the constitution, the notes README, and the five shipped skills
(their bodies load into agent context every session, so bloat there
is paid per-token). Properties:

- **Characters, not words**: the docs are bilingual pairs and a
  Chinese word is not a space-separated token; a character count is
  the language-neutral measure both sides share. Ceilings sit at
  roughly +25% over the counts on adoption day; the culture is that
  they ratchet down.
- **Generated regions are stripped before measuring**: the README's
  gov:commands block is derived truth — it grows with the product's
  command count and has its own pinning test, so charging it to the
  README's ceiling would make every new command a docs violation. The
  gate caught this on its first DAG run (the `surprise` command had
  grown the block past the freshly set ceiling): the budget judges the
  prose a human owns.
- **Ledgers are deliberately absent**: `docs/decisions.md` and
  `CHANGELOG.md` grow forever by design (append-only logs); a ceiling
  there would be wrong, not generous.
- **A declared doc that vanishes is a stale row: red** (rule 5). A
  file outside the config is unjudged; adding a standing doc means
  editing the config, which is the point.
- Rejection case `.gov/rejections/case-doc-budgets.sh` proves all four
  legs (over-ceiling red naming counts, raised ceiling green, missing
  declared doc red, unknown config key exit 2); the case joins
  `REPO_ONLY_CASES` in both homes.
- Same change, the generated-truth header completed its triple: the
  README command block's BEGIN marker already named the generator and
  the regenerate command; it now names the verifying test
  (`tests/test_docs_cli_consistency.py`) — the DSH contract of
  generator + regenerate command + verifying gate, in one line.

## Alternatives considered

- **Word counts (`wc -w`)** — rejected: the repo's docs are bilingual
  and Chinese text has no space-separated words; a word ceiling either
  undercounts the zh side or needs a second mechanism. Characters are
  monotonic and language-neutral.
- **Budgeting the ledgers too** — rejected: `docs/decisions.md` and
  `CHANGELOG.md` are append-only by design; a ceiling on a ledger is a
  contradiction, and the pressure it creates would push decisions
  somewhere unrecorded.
- **Skipping the skills** — rejected: skill bodies load into agent
  context on every session; their bloat is paid per-token, which makes
  them the highest-leverage docs to cap, not the lowest.
- **A default ceiling instead of an explicit file list** — rejected:
  the config's explicitness IS the mechanism; a default would silently
  judge files nobody decided to cap and exempt the ones somebody
  decided to keep tight.
