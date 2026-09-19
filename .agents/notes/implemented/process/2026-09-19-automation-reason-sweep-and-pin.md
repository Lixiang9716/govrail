# Agent Note: every automated unattended re-baseline names its authority (D66 follow-through)

Status: implemented
Related: D65, D66

## Problem

#311's `--reason` requirement made bare
`verify-plane --write --confirm-unattended` invocations exit 2, and the
automation surfaces still carried three generations of them: the docker
e2e suite's fourteen call sites, the backport-shadow CI job, and (fixed
same-day, different leg) the Windows isatty quirk. Each bare call reds
an entire CI job — first discovered when the accumulating release PR
re-ran the docker cells under the new contract. The miss pattern
repeated: rejection cases fixed in one round, docker e2e and workflow
call sites found only by CI.

## Decision

All fourteen `inner_e2e.py` call sites and the backport-shadow job's
re-baseline now carry `--reason` naming the scenario as the authority.
A meta-test pins the sweep: every `--confirm-unattended` occurrence in
`tests/docker_e2e/inner_e2e.py` and `.github/workflows/*.yml` must be
accompanied by `--reason` within the invocation window — the
refusal-proof rejection cases stay deliberately bare and out of scan
scope. Future automation surfaces get the same tripwire by file
convention (workflows dir is scanned wholesale).

## Alternatives considered

Widening the scan to the whole repository (docs, demo, prose) —
rejected: prose mentions and the intentional bare rejection cases would
need a growing allowlist, teaching readers to ignore the tripwire.
Removing the --reason requirement for automation identities — rejected:
the CI bot identity is exactly the "governed agent" the requirement
exists to make accountable; the scenario name is its authority.
