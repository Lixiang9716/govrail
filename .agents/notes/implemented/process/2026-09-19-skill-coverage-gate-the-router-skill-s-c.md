# Agent Note: skill-coverage gate: the router skill's command coverage is gated, not hoped for

Status: implemented
Related: D56, D61

## Problem

Rule 9 names the router skill's stage table as the third discovery-surface
home of a command, and its note pre-agreed the trigger for a structural
gate: "if stragglers appear, the gate becomes the fix." The stragglers
did appear — the `gov update` incident was the first, and a sweep at
this change found seven more shipped commands with zero presence in the
`govrail` skill (`self-test`, `receipt`, `decision`, `check`, `parse`,
`change-scope`, `preset`): 7 of 24 routable commands invisible to the
one surface agents actually enumerate. Nothing in the repo could catch
the next one, because every red-on-drift check watches registries and
hashes, not routing prose — rule 9's discipline was the only guard, on
the surface whose whole point is that agents never read the other
surfaces.

The sweep also caught the truth-source register lying by omission and
by staleness: row 2 still named `gov/cli.py` `_COMMANDS` as the command
vocabulary's truth source two refactors after D61 moved it to
`gov/commands.py`, and the skill stage-table copies appeared in no row
at all — the exact "looks maintained but has no pin" pattern the
register exists to kill.

## Decision

`skill-coverage` joins the dogfood DAG as a blocking, self-hosted gate
(the `lint`-gate precedent: no adopter first-run risk, so no advisory
incubation). `scripts/check_skill_coverage.py` ast-reads the `COMMANDS`
panel from `gov/commands.py` under `--root` — the checkout under
judgment, never the installed package, so the rejection case can prove
the gate red on a scratch tree — and requires every command to appear
as `gov <cmd>` in `.agents/skills/govrail/SKILL.md`, with these
properties:

- **Exclusions are data with reasons** (`scripts/skill-coverage.json`):
  `hooks` is excluded as git-hook plumbing that installed hooks delegate
  to, not a routing verb. A stale exclusion (naming no COMMANDS entry)
  is a config error — exit 2, not a silent no-op (rule 5).
- **An unreadable registry fails loud** (rule 5): if `COMMANDS` grows a
  form `ast.literal_eval` cannot read, the gate says the checker must
  be extended in the same change — a registry this gate cannot parse
  must never pass silently.
- Rule 6 case: `.gov/rejections/case-skill-coverage.sh` proves red on a
  missing command (naming it), green through a reasoned exclusion,
  exit 2 on a stale exclusion and on an unreadable registry.
- The seven stragglers are fixed at the source: stage-table lines with
  routing judgment (when to use, when not), not bare name-drops.
- Truth-source register row 2 now names `gov/commands.py` `COMMANDS`
  (en+zh), lists the skill stage-table lines among its copies, and pins
  the relation to this gate — the register's own rule: a row without a
  pin documents an intent, not a fact.
- Demo-specimen plumbing: the case joins `REPO_ONLY_CASES` in
  `scripts/sync_demo_specimen.py` and `tests/test_template_sync.py`
  (it judges the govrail repo itself — scripts/ + the live skill —
  which the specimen does not carry); the updated SKILL.md is mirrored
  to the template and demo copies it pins.

## Alternatives considered

- **Structural gate over the stage table only (rule 9's deferred
  option)** — this IS that option, arrived at through its own trigger;
  the design that was rejected there (a rigid mechanical parse forcing
  format onto judgment prose) is avoided by matching `gov <cmd>`
  citations anywhere in the skill: the prose stays free, only presence
  is gated.
- **Extending `tests/test_docs_cli_consistency.py` to walk COMMANDS →
  skill** — rejected: it would add a sixth relation to a test file that
  owns doc↔CLI resolution, while the straggler is a governance
  violation (rule 9), and only a gate is visible in the DAG summary
  where `gov run` and CI report it; host-suite tests are invisible to
  the plane's own ledger.
- **Excluding the seven stragglers instead of routing them** — rejected
  for six of seven: they are agent-relevant verbs with real judgment to
  convey (when `gov check` vs the gate, when `change-scope` prices a
  change); only `hooks` earned its exclusion, with the reason recorded
  where the gate can see it.
- **Advisory incubation for the gate** — rejected via the lint
  precedent: the first-run-red concern (P0-3) does not apply to a
  self-hosted gate with no adopter exposure, and the tree is already
  green (23/24 + 1 exclusion), so advisory would add a round-trip with
  no evidence to gather.
