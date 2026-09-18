# preset: agent-heavy

Multi-agent parallel development: several oblivious coding agents working
one repository in parallel — the workflow validated in the 5/10/15-worker
concurrency drills. This preset ships the coherent starting set that
workflow needs, landing through the plane's existing adoption machinery
and never overwriting local state.

## What lands

| Item | Content | Adoption contract |
|---|---|---|
| gate `verify-decisions` | `gov decision verify` scoped to `docs/decisions.md` | merged into `gates.json` by id (D39) — a local gate with the same id is kept untouched |
| mode `governance` | `+= verify-decisions` (mode created when absent) | membership converges: an existing mode gains the declared ids it lacks, local order untouched — even when the gate arrived in an earlier round (D39) |
| skill `parallel-workers` | the worker protocol: lease → verify → preflight → blind coordination | copied byte-for-byte when missing (D29); an existing skill is skipped and named |
| manifest hint `note_presence_exempt` | `[".gov/tasks/**"]` | written only when the key is absent (D49); the local value always wins |

## Why these pieces

- **The decisions table guard**: in a multi-worker repository the
  decisions table is the coordination spine (parallel branches allocate
  numbers against it); making it mechanical is what keeps the spine from
  rotting. It rides in the `governance` mode so it stays reachable (D24).
- **The worker protocol skill**: the drill-validated rules — acquire a
  lease before touching a shared file, run the gates before releasing,
  preflight the union with `gov run --merge` before landing — as a
  trigger agents load, not prose they must rediscover.
- **The bookkeeping exemption**: task receipts (`.gov/tasks/**`) are
  machine-written bookkeeping (D43); without the exemption the
  note-presence advisory fires on every closed task and agents learn to
  ignore it (#149).

## Apply

```sh
gov preset show agent-heavy        # read-only: exactly what lands
gov preset apply agent-heavy       # into an initialized project
gov init --preset agent-heavy      # one command for a new project
```

Apply is idempotent: on an already-adopted repository every item reports
"already adopted" and nothing is written. `python-lib` and
`docs-bilingual` presets follow the same matrix (D53).
