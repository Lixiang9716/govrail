# Agent Note: task new mints past the upstream's card ids: parallel branches stop colliding on T-numbers

Status: implemented

Related: D55, issues #393, #327, #352, #378

## Problem

Two branches created from nearby mains each ran `gov task new`; both
minted T-0049 (each branch's high-water — current cards plus git
history under `.gov/tasks/` — was blind to the sibling branch), and
after both merged, `gov task list` showed two open cards displaying the
same id. The #352 disambiguation refuses an ambiguous prefix naming
both files whenever both are visible, and #378's identity echo says
which card a mutation moved — but the mint-side hole stayed: id
allocation could not see across branches, so the collision was minted
into existence and every later invocation paid for it.

## Decision

- **`task new` scans the upstream's tracked card set before minting.**
  `git ls-tree --name-only @{upstream} .gov/tasks/` (then
  `origin/HEAD` — the same ref chain the pre-push hook uses for fork
  points) contributes every T-number the remote carries to the
  high-water; the local sequence is never reused upstream. A repository
  with neither ref scans nothing and keeps today's behavior. When the
  scan bumps the mint past the local sequence, `task new` says so
  ("minted T-0050 instead of T-0049 — sibling branches share the
  sequence").
- **The post-merge ambiguity abort is pinned as a regression**: two
  OPEN cards sharing an id prefix must exit 2 naming both FILES —
  #352's one-open-wins narrowing applies only when every other match is
  terminal, never while the collision is live. The issue's step 4 read
  as acceptance; the test pins the refusal.

## Alternatives considered

- **Refuse to mint on collision instead of bumping** — rejected: the
  number carries no meaning beyond being an address (#327), so refusing
  would only add a round trip; the bump IS the refusal, said out loud.
- **Date+slug ids** (`T-2026-09-25-web-client`, the issue's option 3) —
  declined for now: it changes the id contract every existing card,
  doc, and citation carries, and the scan closes the live collision
  without a format migration. Same verdict #352 reached for the
  matcher: fix the live behavior, leave the format alone.
- **Scanning every remote** (not just the upstream/origin/HEAD chain) —
  rejected: forks and stale second remotes would reserve numbers for
  trees this repository never merges, ratcheting the sequence without
  reason; the upstream is where sibling work actually lands.
