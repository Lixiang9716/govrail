# Docker E2E matrix (D58)

The adopter's environment, in containers: every cell is a clean image
holding only the interpreter, git, and the **installed govrail wheel
built from the current checkout** — the release artifact, not the source
tree. The in-container suite (`inner_e2e.py`) is plain Python with no
dependencies, because an adopter's machine has no pytest either.

## Cells

| cell | what it proves |
|---|---|
| `3.10-slim` … `3.13-slim` | the supported Python floor-to-ceiling matrix (Debian/glibc) |
| `3.12-alpine` | musl: the wheelhouse claim (musllinux wheels for tree-sitter) is real, `apk` git included |
| `3.10-bookworm` | the floor interpreter on the PREVIOUS Debian stable — the old-glibc corner, walked not assumed |
| `3.12-slim-nonroot` | the lifecycle under user 1000 — permissions and ownership edges |
| `pypi-adopter` | `pip install govrail==<version>` from the real index, then `gov --version` (network cell; a mirror outage reports SKIP, never red) |

Fifteen scenarios run in every deterministic cell: wheel version, the full
lifecycle (init → gates → conflict → task close with receipt → verify →
uninstall), the C-locale hostility round (#168/#172's wall on an
ASCII-locale host with Chinese content), eight-process lease contention
(exactly one winner), crash recovery via TTL takeover, a real pre-push
hook blocking a red push and landing a green one (POSIX — the host suite
skips this), linked-worktree ledger anchoring (D32), and a 120-file
stats performance smoke.

## Run it

```sh
tests/docker_e2e/run.sh               # build (if missing/stale) + all cells
tests/docker_e2e/run.sh --quick       # only current, already-built images
tests/docker_e2e/run.sh --cell 3.12-alpine
```

- Base images come from `GOV_DOCKER_MIRROR` (default
  `docker.mdaocloud`-style mirror; point it at `docker.io` where Docker
  Hub is reachable).
- The wheel is rebuilt from the checkout on every invocation; a sha
  stamp (`.wheel-sha`, gitignored… actually committed-state-free)
  forces per-cell rebuilds when it changes, so a stale image can never
  test an old wheel.
- Exit non-zero if any deterministic cell FAILs; the optional PyPI cell
  only ever PASSes or SKIPs.

## The regression wrapper

`tests/test_docker_e2e.py` runs the matrix from pytest. It SKIPS unless
`GOV_DOCKER_E2E=1` is set — a full matrix run takes minutes and builds
images, which is a deliberate act, not a default test. Wiring it into
CI (ubuntu runners have Docker) is a one-line workflow step and a
maintainer decision.

## Runtime-variant evaluation (Kata/gVisor)

Evaluated and DEFERRED: both need a runtime plugin this environment does
not ship (runc only), and the plane is stdlib-Python — no cgroups,
networking, or userns syscalls where an OCI runtime boundary would
change behavior. The stdlib wall (#168/#172's) is the compatibility
surface, and it is covered by the GBK cell. Revisit on a
runtime-specific incident.

## Locale-variant evaluation (zh_TW/Big5)

Evaluated and DEFERRED: a Big5 cell would exercise the same
`force_utf8_stdio` wall as the GBK cell with a different legacy codec —
one code path, near-zero marginal signal, one more image to maintain.
The GBK cell keeps the hostility premise (a host that decodes non-UTF-8)
with the codec whose incident actually happened (#172). Revisit only if
a Big5-specific incident ever exists.

## Engineering notes

- pip retries/timeouts are baked into the image: the dependency wheels
  (tree-sitter, tens of MB) come from PyPI's CDN, which flaps — a build
  must ride out a read blip.
- A `[ ... ] @cap` alternation with top-level predicates compiles
  DEGENERATE in py-tree-sitter 0.26 (thousands of empty matches); the
  working shape is capture + predicates attached to the inner pattern.
  (Pinned by the shipped rules, learned here first.)
- Old wheels in `dist/` are removed before the build: `pip wheel` adds
  the current one, and a 0.11.0 wheel riding along installs the wrong
  version inside the image.
