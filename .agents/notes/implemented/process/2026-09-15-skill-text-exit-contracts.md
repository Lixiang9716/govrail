# Agent Note: skill text tells the truth about exits and anchors

Status: implemented

## Problem

Two shipped skills taught inferences the tools do not make.
recall-first claimed "nothing matches → the change is non-trivial by
definition" — an empty result set proves nothing, and treating it as a
note requirement invites exactly the pipeline notes the format gate
cannot judge. It also never explained `gov recall`'s exit 2 (empty
memory plane), which a fresh adopter meets on day one. pre-push-checks
linked `../../docs/review-rubric.md` from `.agents/skills/pre-push-checks/`,
which resolves to `.agents/docs/` — a link that 404s in every freshly
initialized repo (and in this one).

## Decision

recall-first now grounds the note obligation in rule 2's own test
(would a maintainer ask why?) rather than in the emptiness of a search
result, and documents the exit contract: 2 = no memory plane yet,
1 = searched and found nothing. The rubric link points three levels up
to the repo root. Fixed in both the live skills and the shipped
templates so new inits inherit the corrected text.

## Alternatives considered

Make `gov recall` exit 0 on an empty corpus instead — rejected: the
exit code is honest and callers may branch on it; the skill was the
component that lied. Drop the rubric link — rejected: the rubric is
the grading contract; a reachable link is the cheapest fix.
