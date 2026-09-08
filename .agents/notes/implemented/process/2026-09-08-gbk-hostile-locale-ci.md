# Agent Note: GBK hostile-locale CI job — the decode wall meets a non-UTF-8 host

Status: implemented

Related: #172 (whose follow-up list this lands), #168 (the decode wall's
print/decode halves), #173 (the pinned self-test spawns the wall now
guards), #171 (the pytest-on-Windows port whose suite this job also runs
under GBK), rule 6 (a gate that never fails is vacuous)

## Problem

The #172 reporter asked for a CI job reproducing their crash class:
a zh-CN Windows host whose ANSI code page (GBK) decodes every
`text=True` subprocess output that forgets `encoding=`. Forcing cp936 on
`windows-latest` needs a system-locale change plus a reboot, so the
suggestion was deferred as expensive — leaving the decode wall
(#168/#173) guarded only by unit tests that run on UTF-8 hosts, where
an unpinned decode is invisible.

## Decision

CI gains a `gbk-locale` job that rebuilds the hostile host on Linux:

- A **user-space GBK locale** — `localedef -i zh_CN -f GBK
  "$LOCPATH/zh_CN.GBK"` with `LOCPATH` set, no sudo and no image
  dependency beyond glibc's locale tooling (an apt fallback names
  itself if localedef is somehow absent). `LC_ALL=zh_CN.GBK` then makes
  `locale.getpreferredencoding(False)` return GBK for the whole job.
- An **anti-vacuous assertion step** before any suite runs (rule 6):
  the preferred encoding must be GBK-family, AND an unpinned text
  decode of a UTF-8-speaking child must produce mojibake — if the
  locale failed to build or the host silently coerces to UTF-8, the job
  fails loud instead of passing green while proving nothing.
- The full battery then runs under the hostile locale: `pytest -q`,
  `gov self-test`, `gov run --mode all`.

Empirically the locale bites: under it, the pre-#168/#173 tooling
(0.29.0 install) failed `doc-sync` (UnicodeEncodeError on the report's
`↔`) and `test_verify_decisions_rejects_base_collision` (the exact
decode crash #168 fixed) — the same two defect classes those PRs
repaired. Master runs all three suites green under GBK.

## Consequences

- Any future `text=True` spawn without `encoding=` — in the runner, the
  harness, or a test fixture — crashes this job on the first non-ASCII
  byte, on every push. The wall now has a host that punishes its
  removal, not just unit tests asserting its presence.
- Test-side encodes are covered too: fixtures writing non-ASCII via
  unpinned `write_text`/`open` would raise under GBK; the current suite
  (as of #171's port) survives, which is that port's encoding
  discipline verified from the hostile side.
- The job costs one more ubuntu runner (~2 min); it does not touch the
  Windows job, whose cp1252-ish default remains a weaker but distinct
  signal.

## Alternatives considered

- **`chcp 936` on the Windows job** — rejected: chcp changes the
  console code page, not the ANSI code page `GetACP` reports, so
  Python's `locale.getpreferredencoding` stays untouched and the
  simulation is decorative.
- **`sudo locale-gen zh_CN.GBK`** (the common ubuntu-runner recipe) —
  works, but needs root and the `locales` package's locale.gen list;
  the LOCPATH build is self-contained, works without sudo, and fails
  with localedef's own diagnostics on any image.
- **`LC_ALL=C` + `PYTHONCOERCECLOCALE=0`** — even more hostile (ASCII),
  but PEP 538 coercion subtleties make it fragile, and GBK is the
  reporter's actual locale: its ASCII subset decodes cleanly and only
  non-ASCII bytes crash, which is precisely the partial failure #172
  reported ("概率性").
- **Monkeypatch `locale.getpreferredencoding` in a wrapper process** —
  rejected: CPython's TextIOWrapper default-encoding lookup has moved
  between internal implementations (`_bootlocale` and friends); pinning
  the real locale exercises the real lookup on every version.
