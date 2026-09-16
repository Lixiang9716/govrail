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
gov run                   # the full gate DAG (notes + pairing + note-presence + self-test)
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

### The release PR may need one click

The `chore(master): release x.y.z` PR is authored by the release-please bot.
GitHub holds its CI run in "action_required" (workflow runs from bot PRs
need a maintainer's approval; that setting exists only in the repository UI).
When it happens, either:

- open the PR's checks and click **Approve and run** on the run created
  AFTER the drafting job's amend (the pre-draft creation-time run is
  cancelled automatically; if you ever see two pending, the older one is
  stale) — CI runs, the `gates` check reports, and the PR merges
  normally; or
- merge with the owner bypass (`gh pr merge <n> --squash --admin`) — admins
  are not subject to the required checks on this repository, which is scoped
  deliberately: every non-admin PR (human or agent) still requires `gates`.

Prefer the first: it keeps the release PR's CI evidence real.
