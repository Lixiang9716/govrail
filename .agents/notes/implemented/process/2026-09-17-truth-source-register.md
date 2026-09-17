# Agent Note: the truth-source register — every row names its pin

Status: implemented

## Problem

The mechanical-sync audit found the same disease in four more places:
relations that LOOKED maintained but had no pin. The i18n README's
pairing example had already drifted from DEFAULT_CONFIG (missing the
postmortem exclusion) — nobody noticed because nothing checked it. The
note taxonomy (CLASSES/LIFECYCLES) and its README enumeration were two
hand-written copies of one closed set. The shipped-gate full set spans
TWO files (template gates.json + doctor's HAND_SHIPPED_GATES) with no
structural invariant — a new verify-* tool landing in neither would be
invisible to every adoption check, the exact #147 failure mode. And the
agent-heavy preset's parallel-workers skill was a fourth unwatched
copy. Each was a row waiting to lie.

## Decision

docs/truth-sources.md (+ .zh.md, a paired bilingual document): the
authoritative register of all seventeen truth sources — six code
constants, ten authoritative files, and git history itself as the
adoption anchor — each row naming its copies AND the test that pins
the relation. The register's own rule, stated in it: a row without a
pin documents an intent, not a fact; write the test in the same
change. Four pins landed with the register
(tests/test_truth_sources.py): the i18n example must equal
DEFAULT_CONFIG (both languages — the pin caught the real drift on its
first run), every taxonomy token must appear in the README, every
verify_* module must ship in the template's DAG or doctor's hand list
(with one explicit, commented command alias), and the preset's skill
copy must be byte-identical to the live skill. Exclusions are
documented, not implied: .gov/history/ is deletable runtime (the
reason the ritual ledger exists, N9), the release manifest is
tool-synced, the root gates.json is a dogfood instance (the adopter
truth is the template), README quick-start comments are curated
judgment whose commands are still resolved against the CLI surface.

## Alternatives considered

Extend docs/tiers.md instead — rejected: tiers owns documentation-tier
prose ownership; the register covers code constants, ledgers, and
seals; the register REFERENCES tiers rather than duplicating it.
Generate the register from a machine map — deferred: the rows are
heterogeneous (constants, unions, bilateral pairs); a generator would
need the map to be richer than the prose it produces. The bilingual
pair constraint (pairing include) plus the per-row pins already make
the register self-checking where it counts. N-way pairing groups for
the copies — not needed: every copy relation here is byte-identical
(mechanical sync), not semantic; the semantic-sync case (bilingual)
is two-sided and already covered.
