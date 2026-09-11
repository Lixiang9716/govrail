#!/bin/sh
# gate: note-presence
# Proves the note-presence gate rejects (rule 2): a committed change to
# behavior-bearing code carrying no note anywhere in the diff fails under
# --strict, while the advisory default warns without blocking (D3) and
# names its rule. The note closes the loop.
#
# The gate diffs the repository, so this case keeps the scratch tree
# clean: every run's output is captured in a variable, never in a file
# (an untracked out.txt would itself become the reviewed change).
set -u
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

# Resolve the govrail package from this repository (self-test runs us
# with the repository root as cwd; `gov` may not be on PATH here).
repo_root=$(pwd)

cd "$scratch" || exit 1
git init -q .
git config user.email t@t
git config user.name t
printf 'x = 1\n' > app.py
git add -A
git -c commit.gpgsign=false commit -qm init
printf 'x = 2\n' > app.py
git add -A
git -c commit.gpgsign=false commit -qm change

# The advisory run is the shipped gate: it warns, it must not block.
out=$(PYTHONPATH="$repo_root" python3 -m gov verify-note-presence 2>&1) || {
  echo "case-note-presence: the advisory run blocked (D3 says it must not)" >&2
  printf '%s\n' "$out" >&2
  exit 1
}
printf '%s\n' "$out" | grep -q 'rule 2' || {
  echo "case-note-presence: the warning does not name its rule" >&2
  printf '%s\n' "$out" >&2
  exit 1
}

if out=$(PYTHONPATH="$repo_root" python3 -m gov verify-note-presence --strict 2>&1); then
  echo "case-note-presence: an un-noted change passed --strict" >&2
  printf '%s\n' "$out" >&2
  exit 1
fi
printf '%s\n' "$out" | grep -q 'app.py' || {
  echo "case-note-presence: the un-noted file is not named" >&2
  printf '%s\n' "$out" >&2
  exit 1
}

mkdir -p .agents/notes/implemented/bug-fix
printf '# Agent Note: the change\n\nStatus: implemented\n\n## Problem\np\n\n## Decision\nd\n\n## Alternatives considered\na\n' > .agents/notes/implemented/bug-fix/2026-01-01-the-change.md
git add -A
git -c commit.gpgsign=false commit -qm note
out=$(PYTHONPATH="$repo_root" python3 -m gov verify-note-presence --strict 2>&1) || {
  echo "case-note-presence: a diff carrying a note failed --strict" >&2
  printf '%s\n' "$out" >&2
  exit 1
}

echo "case-note-presence: rejection proof holds"
exit 0
