# govrail

English | [中文](README.zh.md)

[![CI](https://github.com/Lixiang9716/govrail/actions/workflows/ci.yml/badge.svg)](https://github.com/Lixiang9716/govrail/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/govrail.svg)](https://pypi.org/project/govrail/)
[![Python](https://img.shields.io/pypi/pyversions/govrail.svg)](https://pypi.org/project/govrail/)
[![GitHub Repo stars](https://img.shields.io/github/stars/Lixiang9716/govrail)](https://github.com/Lixiang9716/govrail/stargazers)

A language-agnostic governance plane for agent-driven development: coding
agents work fast in parallel while machines — not vigilance — hold the quality
line. The runtime is Python 3 (>= 3.10) plus the tree-sitter parsers that
power the code-stat layer — all installed by `pip install govrail`, no
other tooling required.

The plane ships two mechanisms: **gates** (any promise a command can check
becomes a mechanical check) and **notes** (every non-trivial change records the
decision, what it beat, and the consequences). Bilingual pairing keeps the
external-presentation docs in sync.

## What it changes

| Without govrail | With govrail |
|---|---|
| Agents follow rules "on their honor"; nothing is enforced | Every checkable promise is a gate that fails loud |
| "Why did we do this?" is lost or re-litigated | Each decision is a note with the alternatives it beat |
| Adopting tooling means a restructure or a new runtime | One command, zero restructure: `gov init` |

See a governed project in [examples/demo-project](examples/demo-project) — a living specimen exercising every feature (rubric, rejection cases,
surfaces, decisions). Task-oriented recipes: [docs/cookbook.md](docs/cookbook.md).

## Install

```sh
pip install govrail        # or: uv tool install govrail / pipx install govrail
```

On a lagging pip mirror the wheel can be missing while `pip index versions`
already lists it (the JSON API updates before the simple index). Install
from the official index then: `pip install govrail --index-url https://pypi.org/simple`.

This puts the `gov` CLI on your PATH (Python + tree-sitter, nothing
else). It has one subcommand per action:

```sh
gov init --project <path>     # inject the plane into an existing project
gov init --project <path> --upgrade  # show template drift (diffs, never writes)
gov init --project <path> --adopt all  # land missing template files (never overwrites)
gov init --project <path> --adopt-new gates.json  # merge new shipped gates into a customized gates.json
gov preset list                # shipped presets (D53): agent-heavy, python-lib,
                               #  docs-bilingual — typed adoption bundles
gov preset show python-lib     # read-only: exactly what a preset lands
gov preset apply docs-bilingual --project <path>  # land its gates + skills + hints,
                               #  additive and idempotent (never overwrites)
gov init --project <path> --preset agent-heavy  # init, then apply the preset in one command
gov doctor                     # environment self-check (PATH, python, parse layer, hooks, schema, unadopted gates)
gov doctor --json             # machine-readable: {status, checks, problems}
gov note new --class process --ref D6 "Title"  # scaffold a note, pre-validated
gov init --project <path> --hooks --ci  # also install a pre-push hook and CI
gov uninstall --project <path>  # reverse it exactly
gov run                        # run the default mode's gate DAG (defaultMode)
gov run --base HEAD~1          # only the gates whose paths match the diff
gov run --merge a b --base origin/master  # preflight the union of parallel branches:
                               #  merge each into a scratch worktree, gates run on every
                               #  step's tree; conflict or red step keeps the scene (D51)
gov run --gate pairing         # rerun a single gate
gov self-test                  # rejection cases: the tools' + yours (.gov/rejections/)
gov run --json                 # machine-readable: [{gate, outcome, duration_ms, detail,
                               #  selected_by, scoped_out, ...}] — the whole gate set, incl. scoped-out
gov verify-pairing --write    # re-confirm a bilingual pair after editing one side
                              #   (names the field values it wrote; the record's
                              #    comments state the field semantics — #150)
gov verify-pairing --write en:docs/a.md zh:docs/a_CN.md  # register any naming
gov verify-pairing --explain  # the record schema + conventions, read-only
gov verify-note-presence      # warn when a non-trivial diff carries no Agent Note
                              #   (task receipts exempt; manifest note_presence_exempt names more)
gov verify-rubric             # check the review rubric's structure
gov verify-decisions          # guard the decisions table (ids, alternatives)
gov verify-decisions --base <ref>  # + parallel-branch number collisions
gov verify-decisions --json    # machine-readable: {violations, orphans, overdue, ...}
gov decision next --base <ref>     # next free D-number (branch-aware; warns on a stale base)
gov decision add --from FILE       # append a decision, validated + atomic (--against = --base)
gov verify-conflict-markers   # fail when changed files carry git conflict markers
gov review --base <ref> --grade  # dossier + interactive rubric grading
gov trend                     # gate duration trends from --record history
gov receipt verify <commit>   # was a full green run recorded on this tree? (#124)
gov recall <terms>            # retrieve notes, decisions, postmortems (--any relaxes the AND)
gov audit-notes               # staleness signals in implemented notes
gov audit-notes --json         # machine-readable: {findings: [{file, signal}], ...}
gov change-scope --base <ref> # smallest sufficient set (.gov/surfaces.json maps paths)
gov task new "Title" --check "criterion"  # task card: one-line rules@<hash> pin for a subagent brief
gov task check                 # after a rules adoption: name the stale cards
gov task claim T-0001 --agent w1 --ttl 20m  # lease an open card for one worker
                                            # (two workers cannot take one; busy → exit 3)
gov task release T-0001 --agent w1          # release the card lease you hold
gov task close T-0001          # run the gates; the green run becomes the completion receipt
gov task list --json           # cards as [{id, title, status, rules, claim}] — claim read
                               #  from the lease file; expired reads as unclaimed
gov acquire reports/summary.md --agent w1  # lease a shared resource (busy → exit 3;
                                           #  --wait S polls, --ttl S bounds the lease;
                                           #  both outcomes announce the lock root)
gov release reports/summary.md --agent w1  # release a lease you hold (never on another
                                           #  holder's behalf)
gov locks                      # list current leases (diagnostic only)
```

`init` is non-invasive and idempotent: it creates `.gov/rules.md`, adds
`gates.json`, the notes README, and the agent skills (recall-first,
pre-push-checks, code-review, archive-agent-notes) only when missing,
appends one reference line to AGENTS.md, and never overwrites the
project's own files — including its own skills. `--hooks`/`--ci` can be
retrofitted later (`gov init --hooks` on an initialized project installs
just the add-on; customizations stay untouched); `--hooks --pre-commit`
additionally installs the optional pre-commit hook — the cheap content
gates (pairing sidecar freshness, conflict markers) on the staged files,
so pair drift surfaces at `git commit` with the scoped fix command
inline instead of one stage later at push (#110). `uninstall` reverses
everything exactly; when a file drifted from its template it names the
file and requires `--force` to proceed (a genuine two-step). A fresh
install never goes red on its first run: the pairing gate ships advisory,
`gov verify-pairing --write` baselines the existing pairs, and removing
`allowFailure` turns it enforcing. `enabled: false` parks a gate without
deleting its definition.

## What is inside

- `gov/` — the Python package: `gates` (the DAG runner over `gates.json`),
  `verify_notes` (three required sections), `verify_translation_pairing`
  (git blob hashes), `verify_note_presence`, `verify_rubric`, `recall`
  (memory retrieval), `audit_notes` (staleness signals), `change_scope`,
  `self_test`, `archive_notes`.
- `gov/templates/` — the rules, default `gates.json`, notes format, and
  agent skills that `gov init` injects into a project.
- `.gov/rules.md` — the single source of truth for the rules.
- `.agents/notes/` — the decision-record format and lifecycle.
- `.agents/skills/` — the triggers that send agents to the tools first:
  `recall-first` (memory before proposals), `pre-push-checks` (smallest
  sufficient set), `code-review` (rubric), `archive-agent-notes`.
- `docs/review-rubric.md` — how PRs are judged: the criteria gates cannot
  check, graded item by item.

## Origin

The mechanisms are distilled from the DeepSeek Harness repository, whose
gates-over-prose axiom shaped this template. Kept: the governance plane. Left to
you: the product plane. The locked design decisions live in
[docs/decisions.md](docs/decisions.md).

## Star History

![Star History Chart](https://api.star-history.com/svg?repos=Lixiang9716/govrail&type=Date)
