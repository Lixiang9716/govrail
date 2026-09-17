---
name: pre-push-checks
description: Use before pushing, force-pushing, or marking a PR ready for review, to select the smallest gate set that covers the outgoing diff without reflexively running the full repository aggregate.
---

# Pre-push checks

CI owns exhaustiveness; this skill owns coverage of the outgoing diff at the lowest cost.

1. Establish the verified base. Use the ref you actually based on (`main`, or the parent PR's head in a stack). Never guess or fetch a base.
2. Report the scope:

   ```sh
   gov change-scope --base <verified-ref>
   ```

3. Select the gates:
   - Prefer the mechanical selector — `gov run --base <verified-ref>` runs exactly the gates whose `paths` cover the diff, plus the unpathed ones, and names what it left out.
   - Without `paths` configured, pick from the reported surfaces: governance tooling or tests → `self-test` (in the `governance` mode where shipped); `.agents/notes/` → `notes`; `.md`/`.zh.md`/`.i18n.yaml` → `pairing`; `docs/review-rubric*.md` → `rubric` where that gate exists; product-plane code → the slots you declared for that surface.
4. Run the chosen mode, the `--base` selection, or individual commands. If there are unstaged or untracked files, either include them or exclude them from your reasoning — never assume they are part of the diff.
5. Self-grade the judgment half: if the project maintains a review rubric ([docs/review-rubric.md](../../../docs/review-rubric.md)), grade the items the diff touches — the mechanical ones are already covered by the gates you ran. Without a rubric, check the reviewer-only axes: honest alternatives, loud failures, a chosen-not-reflexive check set, one fact one home.
6. Report exactly which commands ran and their outcomes. Do not repeat a passing check to feel safe.
