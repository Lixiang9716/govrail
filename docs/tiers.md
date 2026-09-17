# Documentation tiers: one home per fact

English | [中文](tiers.zh.md)

Each fact has exactly one home — the tier whose job it is. Everywhere else links
there. When two places need the same fact, one of them is wrong on the day they
drift.

| Fact | Home |
|---|---|
| Standing orders for agents and humans | [AGENTS.md](../AGENTS.md) → [.gov/rules.md](../.gov/rules.md) |
| How the governance plane works | [architecture.md](architecture.md) |
| Locked design decisions | [decisions.md](decisions.md) |
| Why a decision was made, what it beat | `.agents/notes/` (Agent Notes) |
| Why a failure happened, why guardrails missed it | `docs/postmortem/` |
| Bilingual pairing contract | [i18n/README.md](i18n/README.md) |
| How PRs are judged (the judgment gates cannot check) | [review-rubric.md](review-rubric.md) |
| Gate definitions and modes | `gates.json` |
| Product code knowledge | the product plane's own docs, owned by you |

The register of authoritative sources — code constants,
ledgers, seals — lives in [truth-sources.md](truth-sources.md); this
table owns prose-tier ownership, that one owns fact ownership.
