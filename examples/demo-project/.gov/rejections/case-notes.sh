#!/bin/sh
# gate: notes
# Proves the notes gate rejects (rule 3): a note missing its
# `## Alternatives considered` section goes red naming the section, and a
# Status field that contradicts the lifecycle directory goes red naming
# the value. A well-formed note in the same tree passes — the reds above
# were earned, not vacuous.
set -u
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

# Resolve the govrail package from this repository (self-test runs us
# with the repository root as cwd; `gov` may not be on PATH here).
repo_root=$(pwd)

cd "$scratch" || exit 1
notes=.agents/notes/implemented/bug-fix
mkdir -p "$notes"

# A decision recorded without what it beat is the exact failure notes exist
# to prevent (rule 3).
printf '# Agent Note: no alternatives\n\nStatus: implemented\n\n## Problem\np\n\n## Decision\nd\n' > "$notes/2026-01-01-sections.md"
if PYTHONPATH="$repo_root" python3 -m gov verify-notes > out.txt 2>&1; then
  echo "case-notes: a note without Alternatives considered passed" >&2
  cat out.txt >&2
  exit 1
fi
grep -qi 'alternatives' out.txt || {
  echo "case-notes: the finding does not name the missing section" >&2
  cat out.txt >&2
  exit 1
}

# The lifecycle directory is the truth; Status must not improvise.
rm "$notes/2026-01-01-sections.md"
printf '# Agent Note: lying status\n\nStatus: banana\n\n## Problem\np\n\n## Decision\nd\n\n## Alternatives considered\na\n' > "$notes/2026-01-01-status.md"
if PYTHONPATH="$repo_root" python3 -m gov verify-notes > out.txt 2>&1; then
  echo "case-notes: Status: banana passed" >&2
  cat out.txt >&2
  exit 1
fi
grep -q 'banana' out.txt || {
  echo "case-notes: the offending Status value is not named" >&2
  cat out.txt >&2
  exit 1
}

rm "$notes/2026-01-01-status.md"
printf '# Agent Note: well formed\n\nStatus: implemented\n\n## Problem\np\n\n## Decision\nd\n\n## Alternatives considered\na\n' > "$notes/2026-01-01-good.md"
PYTHONPATH="$repo_root" python3 -m gov verify-notes > out.txt 2>&1 || {
  echo "case-notes: a well-formed note was rejected" >&2
  cat out.txt >&2
  exit 1
}

echo "case-notes: rejection proof holds"
exit 0
