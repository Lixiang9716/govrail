# Agent Note: docker e2e batch 2 — GBK locale cell and cross-container drills

Status: implemented

Related: the docker matrix note (same file series), #172 (the GBK
incident the locale cell rebuilds), D40 (the decision collision net),
D52 (the lease sharing domain), rule 5/6 (anti-vacuous probe; every
scenario's red is earned)

## Problem

Batch 1 proved the wheel on clean environments but left two claims
untested where they are most likely to break. The locale wall (#168/
#172) had one CI job asserting it on ONE Python version with a
user-space locale — never the full E2E journey under a host that
actively decodes GBK. And "parallel agents" was tested within one
process boundary: the lease/claim race used sequential stand-ins, and
the decision-collision net (D40) had never been walked by two real
isolated agents pushing from two real working copies.

## Decision

- **The gbk cell**: a second image (FROM the standard e2e image) bakes
  `zh_CN.GBK` via localedef into a user-space LOCPATH with
  `LC_ALL`/`PYTHONUTF8=0` set — the CI job's hostile host, but now the
  ENTIRE in-container suite (nine scenarios) runs under it, not a
  probe. A new first-class scenario, `locale_bites`, is the
  anti-vacuous gate for every cell: under a GBK LC_ALL it asserts the
  preferred encoding IS GBK-family AND an unpinned decode of a UTF-8
  child fails — a locale that does not bite fails the cell as vacuous;
  on UTF-8 cells the same scenario walks Chinese through
  notes/decisions/stats/check from the other side of the wall.
- **The cross cell**: `cross_container_drill.sh` — two REAL containers
  (separate PID/mount namespaces) sharing ONE clone via bind mount,
  which is D52's sharing domain drawn with a container boundary. Drill
  1: both agents allocate D2 from the same base and push to their own
  refs; agent A fetches agent B's branch and `verify-decisions --base`
  goes red naming D2 (the union view reports "duplicate decision
  entry" where the base is new to the series it reports "number
  collision" — the drill accepts the contract, both are the collision
  caught loudly). Drill 2: A's 4-second lease blocks B (exit 3), then
  expires and B takes over — coordination state crossing the container
  boundary through the shared git common dir.
- The per-cell stamp became load-bearing here: the gbk image derives
  FROM 3.12-slim, and the original global stamp let a stale base hide
  behind gbk's fresh build — an image must carry its own stamp, and
  the gbk cell now rebuilds its base first. The stamp content also
  covers inner_e2e.py itself: a scenario-only change must rebuild, or
  the matrix silently runs last week's scenarios.

## Alternatives considered

- **Run the whole matrix under GBK instead of a dedicated cell** — the
  hostile locale makes every pip/git byte-decode land on the wall; a
  dedicated cell states the premise (this host is hostile) and keeps
  the base cells' signal clean.
- **Two clones instead of a shared one for the cross drill** — tried
  first, and it is precisely the bug D52 refuses to encode: separate
  clones have separate lock domains, so agent B was acquiring in its
  own private world and the drill "passed" stages meaninglessly. The
  drill now builds D52's actual sharing domain.
- **docker compose for the cross drill** — two long-lived containers
  plus execs; plain `docker run -d` + exec is the same thing without a
  compose file to maintain.

## Consequences

The matrix is now 8 deterministic cells × 9 scenarios + 1 optional
network cell, and every wheel claim that survived is one that has been
WALKED: hostile locale, real cross-container contention, musl, non-root,
the whole interpreter floor. Known flake, said out loud: the PyPI cell
depends on index reachability and reports SKIP on outage — it has never
failed red, and it is not allowed to.
