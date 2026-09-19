# Agent Note: re-baselining the seal gains friction and visibility (D65)

Status: implemented
Related: D65

## Problem

`gov verify-plane --write --confirm-unattended` let a governed agent
re-seal the constitution with zero human participation: no reason owed,
no per-file consent, and no runner ever announced that a reset had
happened. The ritual ledger recorded the act, but a record nobody reads
is not visibility — "the one move this plane cannot forgive" was
mechanically free (#311).

## Decision

Unattended re-baseline now REQUIRES `--reason` naming the authority
(decision/note/issue) that reviewed the change; the reason rides inside
the seal payload and the ritual ledger. Interactive `--write` confirms
each changed file (`accept the new state of <rel>? [y/N]`) and any
decline aborts with nothing written — the transition is computed before
the first write, so a declined run leaves the old seal byte-identical.
`gov run`'s out-of-band precheck and `gov doctor` announce re-baselines
from the last seven days (caller, mode, reason; advisory). `gov update
--apply` names its own migration as the reason.

## Alternatives considered

Secrets or external anchoring for the seal (HMAC key, remote store) —
the real fix long-term, but a distribution change, not a hardening step;
the issue's own suggestion list stops at reason + announcement for this
round. Blocking `gov run` on a recent re-baseline — rejected: legitimate
migrations need to run their gates right after accepting; the banner
informs, the seal itself still enforces. Refusing unattended re-baselines
entirely — rejected: CI/self-hosted flows legitimately accept reviewed
template moves (`gov update`); the reason requirement is what makes the
machine consent accountable.
