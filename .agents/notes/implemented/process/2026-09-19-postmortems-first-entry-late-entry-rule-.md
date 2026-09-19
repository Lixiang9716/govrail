# Agent Note: postmortems: first entry, late-entry rule, and a structure gate

Status: implemented

## Problem

The postmortem practice existed from the plane's first day —
`docs/postmortem/README.md` defined structure and bar, `docs/tiers.md`
assigned it a tier, `gov recall` indexed the corpus — and sat empty for
three months while two qualifying incidents (#290: a red lint and eight
red e2e cells landed on master via auto-merge; #294: the same class
reaching master a second time) were captured only as Agent Notes and
decision rows. Two structural reasons kept it empty: the README's rule
("same PR as the guardrails, or not at all") made any late entry
illegitimate, so the note — the plane's native genre — always won; and
nothing in the process triggered the genre at fix time. Writing the
first entry also surfaced a factual drift in the incident record: the
ci.yml comment said the gates summary "stayed green" during #290, but
the head commit's check-run record shows it reported `skipped` — the
summary abstained (its needs included the failed lint job, no
`if: always()` yet), and branch protection counts abstention as
satisfaction. The deeper mechanism was never stated anywhere.

## Decision

- **Postmortem 0001 written** (`docs/postmortem/0001-the-required-check-abstained-and-abstention-merged.md`
  + zh pair): #290/#294/#296 as one event, with the corrected mechanism
  — abstention, not green — as the root-cause class: an enforcement
  surface whose behavior under failure was never specified.
- **The late-entry rule amended** (README pair): "same PR as the fix's
  guardrails, or in the first PR that lands after they do — or not at
  all." The anti-story intent (a linked, landed guardrail) is kept; the
  letter no longer forbids the retrospective the practice exists for.
- **The structure contract gate-enforced**: the `postmortems` gate
  (blocking, dogfood-only, the `lint`-gate precedent) runs
  `scripts/check_postmortems.py` — every entry carries the four README
  sections in one consistent heading vocabulary (English or Chinese,
  never mixed), each non-empty, and a Guardrails section that names at
  least one pointer with every path pointer resolving to a file. A
  zero-pointer guardrails section — the story the README forbids — goes
  red. Rejection case `.gov/rejections/case-postmortems.sh` proves all
  five legs (missing section, story, dangling path, mixed vocabulary,
  and the green path). What stays human: numbering, narrative quality,
  and whether an incident meets the bar — detecting "an incident
  happened" is not mechanizable, so the gate polices structure only.
  Incident-review discipline ("does this fix owe a postmortem?") stays
  with the review rubric and human judgment.

## Alternatives considered

- **A trigger gate that detects unwritten postmortems** — rejected:
  recognizing "a failure happened" from a diff is not mechanizable; any
  approximation (e.g., keying on gate failures) would false-positive on
  ordinary red runs and train everyone to ignore it.
- **Rubric item only, no gate** — rejected as insufficient by rule 1:
  the four sections and pointer resolvability are exactly the promises a
  command can check; leaving them to review repeats the prose-discipline
  pattern this plane exists to end (the skill-coverage lesson, same
  day).
- **Requiring the en heading vocabulary in both languages** — rejected:
  the zh side is written for zh readers (one language per file); the
  gate requires consistency within a file, the pairing gate covers the
  pair, and the README's bolded English terms are terminology anchors,
  not a heading mandate.
- **Recording the corrected #290 mechanism by editing the ci.yml
  comment** — rejected: postmortems are the append-only home for
  corrected history; the comment cites #290's lesson accurately enough
  (#296 fixed the class), and frozen/recorded artifacts stay untouched.
