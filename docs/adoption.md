# Adopting the plane into a project

English | [中文](adoption.zh.md)

The plane is adopted with one command per action. The rules live in
[.gov/rules.md](../.gov/rules.md); the locked decisions are in
[decisions.md](decisions.md).

## Install and remove

```sh
gov init --project <path>       # inject gates, notes, rules, reference
gov init --project <path> --hooks --ci  # also install the runners
gov uninstall --project <path>  # reverse exactly; removes only what init created
```

`init` is idempotent (re-running is a no-op) and non-invasive: it creates
`.gov/rules.md`, adds `gates.json` and the notes README only when they are
missing, appends one reference line to AGENTS.md, and never overwrites the
project's own files.

`--hooks` writes a `pre-push` hook (`.gov/hooks/pre-push`, wired into
`.git/hooks/pre-push`) that runs `gov run` before a push leaves your machine;
a foreign pre-push is never overwritten — the add-on fails loud before
anything is mutated. `--ci` generates `.github/workflows/gov.yml` (runs
`gov run`), only when that file does not exist. Both are recorded in the
manifest and removed by `uninstall`.

## First-day loop

```sh
gov run                  # the default mode's gate DAG; pairing reports advisory
gov self-test            # prove every governance gate can reject
gov run --base HEAD~1    # only the gates whose paths match the diff
gov change-scope --base HEAD~1   # what changed, which gates cover it
```

On a fresh install the pairing gate is advisory (`allowFailure: true`): it
reports which existing documents have no baseline yet, but never blocks. When
you are ready to enforce pairing, record the existing pairs and remove
`allowFailure` from the pairing gate in `gates.json`:

```sh
gov verify pairing --write       # baseline every pair (writes .i18n.yaml records)
```

Projects that name translations differently (e.g. `foo_CN.md`) configure the
convention in `.gov/pairing.json`, or register pairs one by one with
`gov verify pairing --write en:<path> zh:<path>`.

A change that touches behavior-bearing surfaces with no Agent Note draws a
warning from `gov note presence` (naming the rule); add the note, or
pass `--strict` once your team wants that warning to block. Routine
bookkeeping never warns — task-card receipts (`.gov/tasks/**`) are exempt
by default — and a repo can exempt more surfaces by declaring
`"note_presence_exempt": ["docs/**", ...]` in `.gov/manifest.json`, so the
advisory fires only where a note is genuinely expected.

Then make a real change, record it as an Agent Note, and re-run the gates.
