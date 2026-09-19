---
name: govrail
description: Use when working in any govrail-governed repository — before running gates, writing notes, sealing the plane, leasing resources, or pushing; routes every gov command to the right moment, names the moves that are never OK, and is the starting point for the other govrail skills (recall-first, pre-push-checks, code-review, archive-agent-notes).
---

# govrail — the router

This repository is governed by the govrail plane. The gates are not
bureaucracy: they are the project's memory and its seatbelt. This skill
routes you — what to run when, and which moves are never OK. Syntax for
any command is always `gov <command> --help`; this skill carries the
JUDGMENT (when, and when not).

## First session in this repository?

1. `gov doctor` — environment self-check (PATH, Python, parse layer).
2. Read `.gov/rules.md` — the project's standing orders; this skill
   routes commands, the rules decide what matters here.
3. `gov run` — the gate DAG. First contact is advisory by design
   (pairing starts `allowFailure`); a red gate is information, not an
   obstacle.

## The everyday loop

change code → `gov run` → if a gate demands a note:
`gov note new --class <class> --ref <D-id> "title"` (fill every
section — placeholders fail the gate) → `gov note check` → commit →
push (the pre-push hook re-runs the scoped DAG automatically).

## Stage → command → judgment

**Adopting or upgrading**
- `gov init` — inject the plane. Re-runs are no-ops; `--adopt` lands
  MISSING templates (never overwrites); `--upgrade` reports drift and
  changes nothing. Use `--adopt` when a report says UPSTREAM MOVED and
  you want the new template; do NOT use it to paper over a real
  customization. `--platforms <list>` adds agent platforms (claude,
  codex, copilot, gemini; `all`) — fresh or retrofitted, each config
  create-if-missing; a platform you never named gets no files.
- `gov update --apply` — one deliberate migration step (adopt missing/
  moved templates + merge newly shipped gates + refresh the CI pin +
  re-seal). Dry run by default; use it when `gov init --upgrade`
  reports MISSING/UPSTREAM MOVED files or the workflow pin is stale.
  Not on a dirty worktree, and the seal step needs consent (TTY or
  `--confirm-unattended`).
- `gov init --preset <name>` — typed starters. Only when the project
  matches the preset's type; presets never load themselves.
- `gov preset list/show/apply` — the bundles behind `--preset`, inspected
  and applied directly. `list` is the discovery surface; `apply` is
  additive and never overwrites. First adoption goes through
  `init --preset`; `preset apply` is for re-typing an
  already-initialized plane.
- `gov agent-hooks <event> [--dialect <platform>]` — the plane's
  presence at the agent's lifecycle events across platforms: claude
  (default), codex, copilot, gemini — same five events, each platform's
  own deny/context contract. Framework-invoked, not a human verb; the
  `--dialect` in a hook command must match the config file it is wired
  from (`gov init --platforms` writes the matching spelling). If init
  reports a platform's config already exists, merge the five events in
  by hand — and on codex, trust the project hooks via `/hooks`
  (untrusted hooks are silently skipped). The pre-tool-use deny is a
  presence, not a fence — `gov run` and the pre-push gate remain the
  enforcement.
- `gov uninstall --force` — reverse init. `--force` is for customized
  trees AFTER copying out what you keep; without it, uninstall refuses
  to delete anything customized.
- `gov doctor` — environment self-check. Run it first whenever anything
  feels wrong (PATH, Python, parse layer, hooks).

**Running gates**
- `gov run` — the scoped DAG (auto base: dirty worktree → working
  tree; clean → unpushed commits; else last commit). The default is
  almost always right.
- `gov run --every-gate` — the full matrix. CI owns this; use it when
  several push ranges make one base ref insufficient (the hook does
  this automatically).
- `gov run --gate <id>` — one gate. Use for re-running a single red
  gate AFTER reading its failure output (the summary inlines it).
- `gov run --receipt` — evidence run: records a tamper-evident receipt
  bound to the tree. Use when a claim needs to be verifiable later.
- `gov change-scope --base <ref>` — the surfaces the outgoing diff
  touches, i.e. which gates the scoped DAG will trip. Run it when unsure
  what a change will cost; rule 1's smallest-sufficient-set starts here.
- `gov check` — the syntax-class static checkers, by hand. The `check`
  gate runs them scoped; invoke directly to re-judge one tree on demand
  (`--strict` makes warnings block).
- `gov self-test` — every governance gate proves it can reject (rule
  6). Run it whenever touching gates.json, a checker, or a rejection
  case; a gate whose rejection proof is red is vacuous, not green.
- `gov receipt verify/show` — cited receipts: verify one against its
  commit before trusting a claim that cites it; show renders one.
- NEVER `git push --no-verify` to skip a red gate, and NEVER park a
  gate (`enabled: false`) to get green once. Fix the code, fix the
  gate, or take the explicit ritual (below).

**Notes (rule 2's teeth)**
- `gov note new` — every behavior-bearing change carries one. Fill all
  three sections; placeholders fail `verify-notes` by design.
- `gov note check` — pre-commit-sized format + D-reference audit.
- Not for: typo fixes, format-only renames, pure bookkeeping (task
  receipts are exempt by design).

**Pairing (bilingual docs)**
- `gov verify pairing --write` — confirm a pair after BOTH sides moved;
  re-run after the first commit if a side was stamped `untracked`.
- `--staged` — the commit-stage check. A PR never lands one language
  of a pair alone (rule 7).

**The seal (constitution tamper-evidence)**
- `gov verify-plane` — green means the constitution is intact.
- `gov verify-plane --write` — RE-BASELINE = accepting a new
  constitution. Legitimate only after a reviewed, intentional change
  to sealed files. It is a recorded ritual (tracked ledger); making red
  green with it is the one move this plane cannot forgive.
- `--confirm-unattended` — for agents and non-interactive shells; the
  record says so out loud.

**Leases and tasks (parallel agents)**
- `gov lease acquire` / `release` / `locks` — only when ≥2 workers may touch
  one resource; busy is exit 3, `--wait S` polls. Single worker: skip.
- `gov task new/check/close` — briefs for subagents; a `done` card
  without a green receipt is named by `task check`.

**Memory and history**
- `gov recall` — before proposing anything (see the recall-first skill).
- `gov surprise record "<expectation>" --reality "<what happened>"` —
  rule 11's teeth: record expectation-vs-reality the session you notice
  it; the ledger counts recurrences per signature and the `surprises`
  gate escalates the third into a process note. Not for ordinary bugs —
  for the moment reality disagrees with your model of it.
- `gov surprise list` — counts per signature; the "have I seen this
  before?" lookup before recording.
- `gov decision next/add/verify` — the D-number registry behind
  docs/decisions.md: `next` finds the free number, `add` lands a row
  atomically and validated, `verify` guards the table structure. A
  decision row lands through `add`, never hand-edited into the table.
- `gov parse` — per-file structure facts (function spans, line counts,
  nesting depth); the primitive `stats` reports and a size gate reads.
  Facts, not verdicts.
- `gov trend` / `gov stats` — facts, not verdicts; never gate on them.
- `gov whatsnew --since <manifest version>` — what arrived since this
  checkout's init.
- `gov note archive` + the archive-agent-notes skill — the audit →
  archive handoff.

**Review**
- `gov review --base <ref>` — the dossier (scope, notes, recall, rubric
  items); `--grade` makes the human's verdict machine-typed. See the
  code-review skill.

## Never (each has burned someone)

- `git push --no-verify` to land past a red gate.
- `gov verify-plane --write` to make red green — that is constitution
  acceptance, recorded under your name.
- Hand-editing anything under `.gov/` (ledgers, seals, rituals) — the
  plane's state is append-only and tracked on purpose.
- Parking a gate (`enabled: false`) for convenience — parking is a
  visible declaration, not a silencer.
- Running with inherited `GIT_DIR`-style variables — the plane refuses
  them; do not work around the refusal.
