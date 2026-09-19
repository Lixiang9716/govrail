# Postmortems

English | [中文](README.zh.md)

A postmortem is written when a failure was subtle, systemic, and costly to rediscover. The interesting part is why the process let it through, not the one-line fix.

## Structure

- **Executive summary** — one paragraph a busy reader absorbs in thirty seconds: what broke, the root cause in plain terms, why it escaped, the durable lesson.
- **Timeline** — the observed sequence, with evidence locations (files, logs, sequences) a reader can verify.
- **Root cause** — the mechanism, stated so the same class is recognizable next time.
- **Guardrails added** — the gates, tests, or rules this failure motivated, each linked.

## Rules

Write it in the same PR as the fix's guardrails, or in the first PR that
lands after they do — or not at all; a postmortem without a linked
guardrail is a story. Structure is gate-enforced (`postmortems` gate,
`scripts/check_postmortems.py`): the four sections must be present in one
heading vocabulary, and every pointer in Guardrails added must resolve.
Never name individuals; the process failed, not a person.
