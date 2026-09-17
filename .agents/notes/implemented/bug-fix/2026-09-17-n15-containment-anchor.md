# Agent Note: N15 — the containment anchor never comes from the protected path

Status: implemented

Related: D56

## Problem

The auditor's round-13 probe defeated the containment fix in its own
terms: `.gov/history` linked to a directory OUTSIDE the repository, and
`gov run` happily couried the full gate record out — `ls /tmp/outside-h2/
→ gates.jsonl`. The root cause is anchor pollution: `assert_contained`
resolved its containment boundary FROM THE PROTECTED PATH
(`toplevel(str(path.parent))`), and git's walk-up, followed through the
attacker's link, answers "not a repository" — the check stepped aside
entirely (its own docstring's step-aside clause), and the component walk
never ran. The step-aside existed to spare macOS's symlinked `/tmp`;
it became the escape hatch. Two of my own probes missed this because
their escape targets lived INSIDE the worktree — git's walk-up found
the repo, the walk ran, the link was caught; the test passed for the
wrong reason. N7's lesson (an anchor must never come from a path the
adversary shapes), one layer up.

## Decision

`assert_contained(path, root)` takes the boundary from the PROCESS,
never from the path: the runner passes its anchored repository, the
ledger sites pass their structural root (the common-dir checkout that
owns `<main>/.gov/history/<name>` — `parents[2]`, a fact of the
checkout, not of anything the attacker links), init passes the
project's repository resolved from the PROJECT (the caller's intent).
`root=None` (no repository known) degrades to the final-component
refusal only. Two read-only judgments then apply: `realpath` the path —
a write that would LAND outside the root is refused outright (the
auditor's repro now dies with "resolves to /tmp/outside-h2/gates.jsonl
— outside the repository"); and a per-component lstat walk on the
ORIGINAL lexical components refuses a link even when it points
somewhere inside — the walk on resolved components would find only
clean directories, because realpath resolves the very links being
judged. init threads the project's repository through every injection
write (`_copy`, `_atomic_write`, AGENTS.md, `.gitignore`, hooks,
workflow, manifest); uninstall resolves its own.

## Alternatives considered

Keep the path-derived anchor and only drop the step-aside (refuse when
toplevel is None) — rejected: git's walk-up through the attacker's
links can also find a DIFFERENT repository the attacker owns, and the
check would then "contain" writes inside the wrong boundary with
confidence. Resolve the path and prefix-match against the root
(realpath containment alone, no component walk) — insufficient alone:
it catches the escape but not a link that stays inside, which remains
a silent rewrite of the plane's layout; the walk is what refuses the
LINK, the realpath check is what refuses the DESTINATION, and N10
needed both. Whitelist known-safe symlinks (macOS `/tmp`) — rejected:
the boundary is passed in, so nothing above the root is ever judged
and no whitelist is needed.
