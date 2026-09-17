#!/bin/sh
# gate: rubric
# Proves the rubric gate rejects: an item missing a required field goes red
# naming the field, and a rubric with zero items is caught as the vacuous
# pass it is (rule 6) instead of reading "0 items ok".
#
# The fixtures are written out literally, never derived with grep: an em
# dash is an invalid byte sequence under a non-UTF-8 locale, and grep then
# calls the file binary and stops handing back its lines.
set -u
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

# Resolve the govrail package from this repository (self-test runs us
# with the repository root as cwd; `gov` may not be on PATH here).
repo_root=$(pwd)

cd "$scratch" || exit 1
mkdir docs
cat > docs/review-rubric.md <<'MD'
### R1 — a

- **Checks:** c
- **Evidence:** e
- **Anti-pattern:** a
- **Gate candidate:** no — judgment
MD
cat > docs/review-rubric.zh.md <<'MD'
### R1 — 甲

- **Checks:** c
- **Evidence:** e
- **Anti-pattern:** a
- **Gate candidate:** no — judgment
MD

# The well-formed pair passes first, so the red below is the violation.
PYTHONPATH="$repo_root" python3 -m gov verify-rubric > out.txt 2>&1 || {
  echo "case-rubric: a well-formed pair was rejected" >&2
  cat out.txt >&2
  exit 1
}

# The evidence field is the one a review cannot do without.
cat > docs/review-rubric.md <<'MD'
### R1 — a

- **Checks:** c
- **Anti-pattern:** a
- **Gate candidate:** no — judgment
MD
if PYTHONPATH="$repo_root" python3 -m gov verify-rubric > out.txt 2>&1; then
  echo "case-rubric: an item without Evidence passed" >&2
  cat out.txt >&2
  exit 1
fi
grep -q 'Evidence' out.txt || {
  echo "case-rubric: the finding does not name the missing field" >&2
  cat out.txt >&2
  exit 1
}

# Zero items would otherwise be a green run over nothing.
printf '# Review rubric\n\nno items here, just prose\n' > docs/review-rubric.md
if PYTHONPATH="$repo_root" python3 -m gov verify-rubric > out.txt 2>&1; then
  echo "case-rubric: a rubric with zero items passed (vacuous, rule 6)" >&2
  cat out.txt >&2
  exit 1
fi

echo "case-rubric: rejection proof holds"
exit 0
