# Agent Note: mutating task commands echo which card moved; --slug turns a remembered id into an assertion

Status: implemented

Related: D55, issues #378, #334, #352, #332

## Problem

Two coding agents share one checkout; a `git stash -u` removed one
agent's untracked card for three minutes, and inside that window the
other agent's `gov task new` minted a NEW card with the SAME id
(per-worktree counters, #332). The first agent's `gov task tick T-0037
1..5` — aimed at the stashed card — resolved to the ONE T-0037 visible
on disk: the wrong card, ticked five times. The #352 disambiguation is
working as designed whenever both cards are present; the mutation
happened in the window where one was transiently absent, which turned
the remembered id into a unique — and wrong — handle. Nothing at the
terminal caught it: the tick success line printed the item text and the
id, but the id names several cards over a session, so a batch loop
scrolling by named no card at all. No damage landed only because the
wrong-card ticks were never committed.

## Decision

- **Every mutating command's success line names the resolved card's
  file identity**: `task: ticked T-0037 (T-0037-overnight) item 1 — …`.
  The slug is what `gov task new` prints, it is unique even when the id
  is not, and it is the handle `--slug` guards with — tick, close
  (success and the refusing line), void, claim, and repin all carry it.
- **`--slug <stem>` is the scripted-use guard** on tick / close /
  claim / void / repin: fail unless the resolved card's file stem is
  exactly the one named (`.json` tolerated, like `_resolve`), BEFORE
  any mutation or gate run. "I read this id earlier in the session"
  becomes an assertion instead of hope — exactly what an agent in a
  shifting shared tree needs. The flag is registered
  (audit_notes.FLAGS) and its help surface is probed like every task
  flag.
- The router skill's stage line is unchanged: the skill carries
  judgment (when to use a card), the budget ceiling is at 11097/11100,
  and --slug's discovery surface is --help + the flag registry — the
  homes rule 10 names for flags.

## Alternatives considered

- **Refuse a bare id that matches a card whose file appeared after the
  process started** (the issue's option 3) — rejected: it needs a
  process-start timestamp threaded through every command, it misfires
  on a card restored by the `git stash pop` that caused the window, and
  the slug guard already covers the TOCTOU: the caller who knows which
  card they mean asserts it, and everything else stays one
  human-readable line.
- **Echo the card TITLE instead of the slug** — rejected: titles are
  prose two workers may genuinely share ("fix the flaky gate"), while
  the slug is the unique file name the resolver itself keys on;
  echoing what resolution keyed on is the auditable form.
- **Make ambiguous-at-write-time a hard error even when one card is
  open** (#352's narrowing) — rejected: it would re-brick the parallel-
  merge shape #352 shipped for, where exactly-one-open is the COMMON
  case; the guard adds certainty without taking that away.
