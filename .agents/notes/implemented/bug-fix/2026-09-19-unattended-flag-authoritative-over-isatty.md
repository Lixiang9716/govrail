# Agent Note: --confirm-unauthenticated flag is authoritative over isatty (Windows runners)

Status: implemented
Related: D65, D66

## Problem

`gov verify-plane --write --confirm-unattended --reason ...` exited 1 on
Windows CI runners: `sys.stdin.isatty()` reports TRUE under the runner's
pwsh pseudo-console, so the #311 interactive per-file prompt fired,
`input()` hit EOF immediately, and the EOF-as-decline abort refused an
otherwise valid unattended re-baseline. Linux CI (stdin = /dev/null,
isatty false) never saw it — the release-branch CI caught what master
missed only because the release branch re-runs the same suite.

## Decision

The unattended flag is authoritative over the TTY probe:
`interactive = not args.confirm_unattended and sys.stdin.isatty()`. With
the flag, the per-file prompt never fires anywhere; without it, a real
terminal still prompts and a non-terminal still refuses (2) with the
remedy. The D66 CI follow-through surfaced this the same day the
strategy changed — the accumulating release PR re-runs the suite per
push, and its first run was red on Windows. Test-side: the #322
new-diff-warning test now configures git user identity before
committing (runner-hostile default).

## Alternatives considered

Probing stdin usability (try reading /dev/null emulation) or keying off
CI=true env — rejected: platform-quirk whack-a-mole; the flag already
carries the caller's intent, and honoring it is both simpler and the
documented contract ("UNATTENDED machine consent"). Making EOF on the
prompt a silent accept — rejected: an unreadable consent prompt must
never auto-accept a constitution change; abort-with-nothing-written is
the only safe default there.
