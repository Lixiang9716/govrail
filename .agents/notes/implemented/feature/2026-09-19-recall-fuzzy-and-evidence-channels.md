# Agent Note: recall --fuzzy and the human-readable evidence channels (D65)

Status: implemented
Related: D65

## Problem

Recall's literal substring AND is honest (D18) but brittle exactly where
the corpus is thickest: Chinese notes have no word boundaries to anchor
substring matches, and a one-character vocabulary mismatch silences a
relevant note. On the evidence side, receipts existed only as JSON
lines (a PR had to paste them by hand — #313), and lease acquisition
never mentioned that its coordination domain is a single clone, so two
clones of one repository could both "hold" a resource in good faith.

## Decision

`gov recall --fuzzy` (#319) widens term matching opt-in: word-level
edit distance ≤ 2 for Latin terms (words < 4 chars stay literal —
short-word fuzzing is noise), CJK bigram overlap ≥ 70% for Chinese
terms; the AND semantics (and --any ranking) are unchanged, and the
default stays literal. `gov receipt show --markdown` (#313) renders
receipts as a paste-ready PR-comment / `$GITHUB_STEP_SUMMARY` block
that states PASS/DIRTY/NOT GREEN and the verify command. `gov lease
acquire` announces the single-checkout boundary whenever the checkout
has linked worktrees (the likeliest multi-worker shape); remote
coordination (a shared `refs/gov/state` mirror) stays future work —
the boundary is now said out loud where it bites.

## Alternatives considered

Making fuzzy matching the default or adding tokenization/stemming —
rejected: the literal AND is the documented contract (D18) and fuzzy
by default trades determinism for hits nobody asked for in that
invocation. Full semantic recall — rejected: dependencies and a model
boundary; the docstring's "grep with structure is the honest tool"
still holds, --fuzzy is the cheap widening, not an index. A GitHub
Action for receipts — deferred: `show --markdown` + the existing
workflow summary file covers the paste path without shipping a second
distribution artifact; the Action remains a possible follow-up.
