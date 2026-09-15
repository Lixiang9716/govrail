# Agent Note: one git-listing and path-glob grammar for the whole plane

Status: implemented

## Problem

git quotes non-ASCII paths by default, and nothing in the plane opted
out: every one of the eight `git diff --name-only` / `ls-files` / `ls-tree`
call sites split lines, so a Chinese filename arrived as a quoted octal
escape no matcher could match. The damage was silent and systemic —
path-scoped gates scoped themselves out, the conflict-marker scanner
failed to open the "file" and skipped it, D-numbers on a ref went
under-counted so `decision next` could re-allocate a live number.
On top of that, three glob grammars disagreed: the gate engine's `**`
demanded a full directory between slashes (root-level files silently
out of scope), parse's fnmatch let `*` cross separators, and the
`--staged` gates read the working tree instead of the index, so a
worktree restored to clean after staging bad content bought a green
pre-commit.

## Decision

New `gov/gitutil.py` owns every file listing: `-c core.quotepath=off`,
NUL-split, surrogateescape round-trip, GIT_* variables scrubbed. New
`gov/pathmatch.py` owns the one glob grammar (`**` spans zero or more
directories, `*`/`?` never span a separator); gates, parse, and
change-scope all consume it. `--staged` modes now read the index
(`ls-files --stage` blob oids for pairing, `git show :<path>` bytes for
markers), and the empty-tree probe is `git mktree` over empty stdin —
no `/dev/null`, correct under sha256. verify-note-presence anchors to
the git root before resolving anything.

## Alternatives considered

Keep per-module listings and patch each one with `-z` — rejected: eight
copies of the same policy is how the drift started; one module makes
the next call site correct by default. Adopt git's `-z` alone without
`quotepath=off` — rejected: `-z` already implies unquoted paths, but
making the policy explicit survives refactors that drop `-z` for
human-facing output. Leave parse on fnmatch — rejected: a second
grammar inside the same tool guarantees the next `paths` bug.
