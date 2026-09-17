# Contributing

English | [中文](CONTRIBUTING.zh.md)

govrail is a governance plane for agent-driven development, and it governs its
own development — so contributing means following the same rules it injects
into other projects.

## Setup

```sh
git clone https://github.com/Lixiang9716/govrail.git
cd govrail
pip install -e .        # installs the gov CLI in editable mode
```

## Run the gates

```sh
pytest -q                 # unit tests
gov self-test             # rejection cases: prove every governance gate rejects
gov run                   # the full gate DAG (this repo's own gates.json)
```

## Making a change

1. Make the change.
2. Run `gov run` and fix anything red (`gov run --base <ref>` for the
   smallest sufficient set).
3. If the change is non-trivial, add or update an Agent Note in the same PR
   (`.agents/notes/implemented/<class>/<date>-<topic>.md`). The note needs
   `## Problem`, `## Decision`, and `## Alternatives considered` — see
   `.gov/rules.md` rule 2 and 3 for the exact test.
4. Open a PR. CI runs the gates.

## AI-assisted contributions

AI-assisted work is welcome and expected — this repository's own
development is heavily agent-driven. Three rules keep that honest:

- **Disclose it.** Say in the PR description which parts were
  agent-written. Undisclosed agent output is grounds for rejection —
  review effort depends on knowing what wrote the code.
- **A human owns the merge.** The PR opener is the author of record:
  able to explain every hunk, answer review on it, and roll it back.
- **The gates do not care who typed it.** Agent-authored changes pass
  the same rejection cases, the same Agent Note format, the same seal
  re-baseline discipline. Where the gates cannot judge a change, that
  is review work — not a formality.

## Waiting for CI and async steps

Wait on conditions, never on clocks (rule 8): `gh pr checks --watch`,
`gh run watch <id> --exit-status`, and poll-until-condition-with-deadline
in tests. A bare `sleep N` that hopes a state has arrived is rejected in
review; the only lawful sleeps pace real wall-clock physics (lease TTL
expiry).

## Keeping the README's command reference current

Every DERIVED truth (README's `gov:commands` block from `gov --help`,
the demo specimen from the live templates, the i18n pairing examples
from `DEFAULT_CONFIG`) regenerates through one command:
`python scripts/derive_all.py`. On PRs, the CI `derive` job runs it in
`--check` mode — drift goes red naming that command; on master merge
pushes the job regenerates and commits the result itself (one step to
the fixed point, loop-guarded). Never edit derived content by hand;
edit its truth source and let the derivation own the copy. Unresolvable
`gov ...` citations and help lines that omit a real subcommand stay
red via tests/test_docs_cli_consistency.py.

## Notes and rules

- Standing orders: [.gov/rules.md](.gov/rules.md) (read before starting).
- Locked design decisions: [docs/decisions.md](docs/decisions.md).
- Bilingual docs pair whole: [docs/i18n/README.md](docs/i18n/README.md).
- Select the smallest sufficient check set:
  `gov change-scope --base <verified-ref>`.

## Releasing

1. Releases are cut by release-please from conventional commits; the version
   lives in `gov/version.py` (single source).
2. Publishing to PyPI is automated on the release tag — the workflow checks
   the tag matches the package version. The PyPI index can lag the publish
   by ~a minute; a first `pip install -U` right after may miss the fresh
   wheel — retry before suspecting the release.
3. While the release PR is open, the workflow drafts its missing HIGHLIGHTS
   sections (`gov verify-doc-sync --write`: bullets copied verbatim from
   CHANGELOG, each heading self-declared as a draft, D46) and AMENDS them
   into the release commit itself — the branch head is one complete commit
   (CHANGELOG + version + HIGHLIGHTS together), so no CI run can capture a
   half-drafted SHA. The drafting job also cancels superseded pending runs,
   so the only approvable run is the complete one. The draft satisfies
   pairing, not prose: rewrite the section's bullets for usage (what
   HIGHLIGHTS actually carries) before or after the merge; until then the
   heading says "draft" out loud.

### The release chain is automated end to end

With the `RELEASE_PAT` secret configured (one-time setup below), a
release-worthy merge to master chains unattended: release-please opens
the PR under a user identity (its CI starts immediately — no
action_required hold), the drafting job amends the HIGHLIGHTS draft into
the release commit, cancels superseded runs, arms auto-merge, and when
the required checks pass GitHub squash-merges; the merge push runs the
release job (tag + GitHub Release + PyPI). A red PR never auto-merges —
the chain halts on evidence, not on hope.

**One-time setup** (repository owner): create a fine-grained PAT scoped
to this repository only, with Contents: read/write and Pull requests:
read/write, and store it as the `RELEASE_PAT` secret. Until it exists,
the workflow falls back to the default token: the PR's CI run waits in
action_required, and approving the run created after the drafting
amend (stale pre-draft runs are cancelled automatically) is the one
human act left. The owner bypass (`gh pr merge <n> --squash --admin`)
remains available; prefer real CI evidence.
