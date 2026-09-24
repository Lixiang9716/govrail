# Agent Note: task close takes several cards: one gate run, one receipt, every card closed against it

Status: implemented

Related: D55, issues #385, #358, #323

## Problem

A governance adoption staled twelve open cards whose work had all
landed. The honest exit — `gov task close` with its green receipt —
cost one full-DAG run PER CARD (minutes each in the reporting repo;
the DAG included a fresh-clone materialization). The receipt-less exit
(`gov task void`) cost nothing. Observed consequence in the field: ten
landed cards were VOIDED with reasons purely to avoid ten DAG runs —
the close verb's cost pushed a user onto the exit that weakens exactly
the evidence trail receipts exist for.

## Decision

- **`gov task close <id> [<id>…]`** resolves every named card
  (id, prefix, or slug; two handles naming one card close it once),
  and runs the preflight for ALL of them BEFORE the gate DAG starts:
  status, rules pin, ticked contract, live lease, --slug guard. One
  bad card refuses the whole batch, named — a partial close would
  leave the operator guessing which half landed. On an all-green run,
  the SAME receipt (one ts, one mode, one rules hash, the same gate
  records) is written to every card and each is closed; a red run
  changes nothing on any card. Duplicate handles are folded, so the
  receipt is written once per file.
- The per-card preflight moved into `_close_preflight`, returning
  (exit code, reason); the single-card path is the one-card batch, so
  every refusal message and code is byte-for-byte what it was.
- `close --help` names the multiple-id form (the discovery surface;
  no new flags, so the flag registry is unchanged).

## Alternatives considered

- **Receipt reuse: close against an unexpired receipt whose tree sha
  matches HEAD** (the issue's option 2) — declined: it makes "close"
  read a verdict produced for a DIFFERENT selection (a pre-push hook's
  scoped run judged the push range, not the card's DAG state), and the
  #323 contract — close writes and the checker reads the same rule —
  is what keeps receipts trustworthy. Batch close removes the cost
  that made reuse tempting without touching that contract.
- **`--receipt <path>` to attach an explicit verdict file** (option 3)
  — declined for the same reason plus one: an attachable verdict file
  is a tamper surface (a verdict minted outside the runner, pasted in)
  that the receipt's own tamper-evidence exists to prevent.
- **A `gov task close --batch` flag over a file of ids** — rejected:
  positional ids are what every other task command takes, and the
  shell already composes lists (`gov task close $(gov task list
  --json | jq ...)`) without a second syntax.
