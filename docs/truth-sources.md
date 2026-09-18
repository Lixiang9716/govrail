# Truth sources

English | [中文](truth-sources.zh.md)

Each fact in this repository has exactly ONE authoritative home —
everything else is a copy (kept in sync mechanically) or a link. This
register names every truth source, its copies, and the test that pins
the relation: a row without a pin is a row that can lie. For which
documentation tier owns which kind of prose, see
[tiers.md](tiers.md) — this register does not repeat that table, it
extends it to code constants, ledgers, and seals.

## Code constants

| # | Truth source | Governs | Copies | Pinned by |
|---|---|---|---|---|
| 1 | `gov/version.py` `__version__` | the package version | pyproject reads it dynamically; the release tag is checked against it | release workflow's tag check |
| 2 | `gov/cli.py` `_COMMANDS` | the command surface and its one-line descriptions | README's generated command block (`gov:commands` markers) | `tests/test_docs_cli_consistency.py` |
| 3 | `gov/audit_notes.py` `FLAGS` | every command's flag surface | `gov <cmd> --help` outputs | `tests/test_flag_registry.py` |
| 4 | `gov/verify_translation_pairing.py` `DEFAULT_CONFIG` | pairing defaults (include, counterparts, exclude) | the example JSON in `docs/i18n/README.md` | `tests/test_truth_sources.py` |
| 5 | `gov/note.py` `CLASSES` + `gov/verify_notes.py` `LIFECYCLES` | the note taxonomy (closed sets) | the enumerations in the notes README | `tests/test_truth_sources.py` |
| 6 | `gov/doctor.py` `HAND_SHIPPED_GATES` ∪ `gov/templates/gates.json` | the full shipped-gate set | doctor's gate-adoption check reads both | `tests/test_truth_sources.py` |

## Authoritative files

| # | Truth source | Governs | Copies | Pinned by |
|---|---|---|---|---|
| 7 | `.gov/rules.md` | the constitution (8 rules) | `gov/templates/rules.md`, the demo specimen's copy | `tests/test_template_sync.py` |
| 8 | `gov/templates/gates.json` | the adopter gate DAG base | the demo's gates (base + its typed extras); the repo root's `gates.json` is a **dogfood instance**, not the base | `tests/test_template_sync.py` |
| 9 | `gov/templates/gov.yml` | the adopter CI shape | `gov init --ci` renders it (version pinned) | `tests/test_template_sync.py` |
| 10 | `.gov/pairing.json` + each `*.i18n.yaml` | bilingual pair truth (git blob hashes per side) | — | `gov verify pairing` (the pairing gate) |
| 11 | `.gov/plane-seal.json` | sha256 seal over the plane's own config | — | `gov verify-plane` (in-DAG and out-of-band) |
| 12 | `.gov/rituals.jsonl` | the append-only ritual ledger (tracked) | — | created by the first ritual; `tests/test_rituals.py` |
| 13 | `docs/decisions.md` | the decision log and D-number allocation | `.gov/decisions.json` may override path/format (absent here = default) | `gov decision verify`, `gov decision next` |
| 14 | `CHANGELOG.md` ↔ `gov/HIGHLIGHTS.md` | released-version pairing | HIGHLIGHTS sections are drafted from CHANGELOG | `gov verify doc-sync` (the doc-sync gate) |
| 15 | `.agents/skills/*/SKILL.md` | the shipped skills | `gov/templates/skills/`, the demo's copies, the agent-heavy preset's `parallel-workers` copy | `tests/test_template_sync.py` |
| 16 | `.gov/rejections/case-*.sh` | the rejection cases (rule 6) | the demo's copies (plus demo-own cases for demo-own gates) | `tests/test_template_sync.py` |

## The anchor that is not a file

| # | Truth source | Governs | Pinned by |
|---|---|---|---|
| 17 | git history | the adoption record: a seal present in history can never silently become "never adopted" (N7); past ritual-ledger and pairing states survive in it | structural — history rewrite is outside any worktree tool's threat model |

## Explicitly NOT truth sources

- `.gov/history/` — runtime ledgers, gitignored by design; the ritual
  ledger exists precisely because this storage is deletable (N9).
- `.release-please-manifest.json` — synchronized by release-please
  itself; humans do not edit it.
- README's quick-start comments — curated judgment, not generated; the
  commands they cite are still resolved against the CLI surface by
  `tests/test_docs_cli_consistency.py`.
- The repo root's `gates.json` — a dogfood instance (it carries
  `self-test`, retired from adopter DAGs by D4); the adopter-facing
  truth is the template, row 8.

Adding a new truth source? The register's own rule: **a row must name
its pin** — write the test in the same change, or the row documents an
intent, not a fact.
