# Agent Note: docker e2e batch 14 — the format matrix and the base-aware allocation arc

Status: implemented

Related: the docker matrix + batches 1-13 notes (same series), D17 (the
three decisions formats), D40 (base-aware allocation across branches),
rule 5 (the format loader's new refusal)

## Problem

The decisions source's format matrix ran E2E only in fragments: dir
format had batch 11's scenario and batch 4's cross drill, but TABLE
format — rows, options-cell mandatory, D0-legal numbering — had no CLI
journey, and the format loader silently reinterpreted an unknown
`format` value as sections (a typo'd "yaml-blocks" would read a dir
source as a sections FILE, or vice versa — rule 5 violation found by
the batch-14 scenario on its first run). The allocation story had the
collision arc (batches 2/4) but not its complement: `decision next
--base` ACROSS containers, where base-aware allocation prevents the
collision from ever being created (D40's happy path).

## Decision

- **decisions_formats** (29th scenario): the table round trip through
  the CLI — a title+body draft is REFUSED with the row shape taught
  inline (#132's contract); a proper row lands as D0 (tables number
  from D0); a second add allocates D1; verify green; a row whose
  options cell records nothing goes RED naming the rule-3 rule; the
  sections-format options-less draft refuses BEFORE any write; and a
  malformed format value in .gov/decisions.json exits 2 naming the
  value (the loader's new refusal).
- **The loader fix the scenario forced**: `configured_path_fmt` now
  refuses an unknown `format` value (exit 2, value and the legal set
  named) instead of silently falling back to sections. All consumers
  (decision next/add, verify-decisions, recall's corpus statement)
  refuse loudly together. 37 host tests around decisions/recall pass
  unchanged.
- **cross_allocation_drill.sh** — two containers, two SEPARATE clones
  (the layout `next --base` exists for): A allocates D2 and pushes; B,
  stale, still sees D2 (its own view); after fetching agent-a, B's
  `next --base` answers D3 — the number the merged history will show;
  B adds D3 (merging agent-a first, per the refusal's own prescription
  from batch 11's drill), pushes; A's verify-decisions --base turns
  GREEN — both appends absorbed with no collision ever created. The
  complement to batch 2/4's collision arcs: those prove the net catches
  a collision, this one proves the tool's advice avoids needing it.
- One shell lesson repeated: `docker exec ... git fetch` without
  `cd /work` runs in /workspace, fails silently, and the base-aware
  next reads a ref that was never fetched — surfaced only by capturing
  the in-container stderr into the report.

## Alternatives considered

- **Assert `decision next --base`'s stderr note verbatim** ("your base
  is 1 row behind...") — the note's wording is presentation; the NUMBER
  (D3) is the contract. Pinned the number.
- **Fold the allocation drill into cross_container_drill.sh** — that
  script's topology is the SHARED clone (leases need the common dir);
  the allocation arc needs SEPARATE clones (the collision's habitat).
  Separate scripts, stated complements — same call as batch 4 made.
