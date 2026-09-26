# Agent Note: DX batch: the close refusal names its own run and carries the report tail; the reminder throttles; --any keeps the ranking contract

Status: implemented

Related: D18, D55, issues #395, #385

## Problem

Three small friction points from one landing, each pushing an operator
toward a wrong conclusion. `task close`'s not-green refusal named the
failed gate but not WHICH run it evaluated — an operator who had just
watched `gov run --gate <gate>` pass standalone read the refusal as a
stale verdict, when in fact close runs a FRESH DAG every time and the
standalone pass measured a different run. Ticking a seven-item
checklist printed the uncommitted-card warning seven times — identical
noise that trains the eye to skip it. And `recall --any` ranked purely
by terms matched, burying a title hit under body-only matches with more
terms — while the strict-AND mode's documented contract (and the
recall-first skill's assumption) is title > heading > body, so --any's
top line was usually NOT the answer.

## Decision

- **The close refusal names its own run and carries the report tail.**
  "THIS close's own gate run (mode, just recorded) was not green
  (gates)" — followed by the runner's report tail (last twelve lines),
  whose per-gate pointers are the diagnosis. The standalone-pass
  confusion dies at the message level.
- **The uncommitted-card reminder throttles to once per card per
  REMINDER_WINDOW_S (300s)**, keyed by card slug in a gitignored
  sidecar (`.gov/tasks/.reminders.json` — shipped in init's, update's,
  and the repo's own ignore lines). The push-time task gate still
  judges the real state; the reminder is advisory UX, and six identical
  warnings train the eye to skip it. `_load_cards` skips dotfile
  sidecars — the plane's own bookkeeping must never read as a card.
- **`--any` sorts by WHERE it hits first** (title > heading > body —
  the strict-AND contract's own ranking), then by terms matched, then
  authority, then path; the header says so. A title hit surfaces even
  when a body-only entry matched more terms: the top line is usually
  the answer.

## Alternatives considered

- **Dedupe the reminder across invocations by suppressing on a dirty
  TREE** — rejected: the reminder is per-CARD (a push carries whatever
  is committed at push time), and a second worker's unrelated dirty
  file would silence this card's warning.
- **No throttle; the loop is the caller's** — rejected: the issue's
  field report is the loop being the NORMAL shape (checklists are
  ticked item by item), and a warning that appears seven times in a
  minute is not evidence, it is wallpaper.
- **Count-first ranking for --any** (today's behavior) — rejected: the
  strict-AND mode already teaches title > heading > body; two modes
  with opposite ranking contracts is the drift. More-terms wins only
  within a tier, which keeps partial-recall utility (a 3-term body hit
  still outranks a 1-term body hit).
