## Summary

The problem this solves and the decision it ships — not a restatement
of the diff. One or two paragraphs; the *why* an Agent Note cannot
carry alone.

## Governance

- [ ] **Agent Note** (rule 2): this PR adds or updates one at
      `.agents/notes/implemented/<class>/<date>-<topic>.md` — or the
      change is mechanical/local and exempt (say which).
- [ ] **Derived truths**: if a truth source moved (`gov/cli.py`
      surface, live templates, `DEFAULT_CONFIG`, skills), I ran
      `python scripts/derive_all.py` and committed the result — never
      edited a derived copy by hand (CI's `derive` job checks this).
- [ ] **Rituals**: if `gates.json`, `.gov/rules.md`, or other sealed
      config changed, the re-baseline was recorded
      (`gov verify-plane --write`; see `.gov/rituals.jsonl`).
- [ ] **Bilingual pairs**: docs pairs I touched are re-confirmed
      (`gov verify pairing --write <doc>`); no pair lands one side alone.
- [ ] **New gate?** It ships a rejection case that proves it can reject
      (rule 6; `gov self-test` runs it).

## AI assistance

Per CONTRIBUTING: which parts were agent-written? A human owns this
merge — able to explain every hunk and roll it back.

## Verification

```sh
# what ran, and what it said (pytest / gov self-test / gov run /
# docker cells — the smallest sufficient set for this diff)
```
