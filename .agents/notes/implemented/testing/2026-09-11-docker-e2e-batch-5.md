# Agent Note: docker e2e batch 5 — postmortem recall, measured perf, the bullseye cell that wasn't

Status: implemented

Related: the docker matrix + batch 2/3/4 notes (same series), #148 (the
recall diagnostics this exercises), D18 (recall's read-side), rule 5/6

## Problem

Three surfaces remained dark. The memory read-side (recall) had no E2E:
its postmortem corpus, its hit-naming, and its miss diagnostics (the
corpus statement and per-term counts, #148) were pinned only by unit
tests — never by the wheel in a clean container. The perf scenarios
asserted budgets but printed no MEASURED durations, so a cell passing
at 119s and one passing at 2s were indistinguishable in the log. And
the glibc axis ended at bookworm — bullseye (one older) was assumed
supported by the same reasoning the plane exists to eliminate.

## Decision

- **postmortem_recall** (14th scenario, every cell): a postmortem hit
  names its document on stdout; a miss exits 1 with the corpus
  statement and per-term counts; and a Chinese postmortem term
  round-trips the read-side. One contract detail is now pinned BECAUSE
  the test got it wrong first: the corpus statement is deliberately on
  STDERR (stdout stays the ranked hit list), so the assertions run
  against both streams — asserting stdout alone reads as a false
  regression.
- **Measured perf**: perf_kilo and perf_night print their measured
  durations on PASS — a cell passing at 0.3s and one passing at 119s
  were previously indistinguishable, and a creeping regression inside
  the budget was invisible until it crossed the line. Nightly's first
  measured run: 10k files → stats 2.3s, check 5.6s.
- **3.10-bullseye: attempted and DROPPED, with the autopsy in run.sh**.
  Post-EOL bullseye is unbuildable as a per-PR cell three ways in a
  row: the security Release file is EXPIRED on the mirror (apt refuses
  without Check-Valid-Until=false); with that relaxed, the security
  index points at .debs the mirror has already replaced (404s); and
  pointing sources at archive.debian.org breaks the apt closure against
  the base image's baked packages (perl-base version skew). An EOL
  compat cell needs a pre-baked image — nightly territory. bookworm
  keeps the old-glibc axis on a consistent mirror. The Dockerfile kept
  the Check-Valid-Until relaxation (harmless for current suites) and
  the run.sh comment carries the full autopsy.

Also in this batch: the fixture-hygiene pass on the harness itself —
every text decode in inner_e2e.py pins UTF-8 (the GBK cell caught the
unpinned ones; the #172 class reproduces in test code exactly as it
does in product code), and the perf scenarios' counting arithmetic is
stated in the assertions (the join blank cost the author a correction
twice; the code now says 29 lines per file and why).

## Alternatives considered

- **archive.debian.org for bullseye** — tried second; the frozen set is
  internally consistent but SKEWED against the base image's baked
  packages (perl-base version skew breaks apt closure). An EOL cell
  needs a baked nightly image, at which point it is not a cell anymore.
- **Big5/zh_TW locale variant** — same force_utf8_stdio code path as
  GBK with a different codec; near-zero marginal signal.
- **Leave perf durations out** — the log line costs nothing and turns
  "budget not crossed" into "here is where we are"; taken.
