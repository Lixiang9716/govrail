#!/bin/sh
# gate: staged-lint
# Proves the staged-lint gate rejects (rule 6): a fixable finding is
# autofixed and restaged (green), an unfixable finding goes red, a
# partially-staged file with findings is skipped by name and still red,
# and no staged python files is a named no-op.
set -u
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

script="$PWD/scripts/staged_lint.py"
# The gate's checker is ruff; in environments without it (wheel-only
# installs, minimal containers) the gate itself would report MISSING —
# this proof skips NAMED, never silently passed (case-lint precedent).
if ! command -v ruff >/dev/null 2>&1; then
  echo "case-staged-lint: SKIP — ruff not installed here; the staged-lint gate would report MISSING"
  exit 0
fi
git init -q "$scratch" && cd "$scratch" || exit 2
git config user.email t@t && git config user.name t

# A clean non-python staged file: named no-op.
echo hi > README.md && git add README.md
if python3 "$script" --staged > out.txt 2>&1; then
  grep -q "no staged python files" out.txt || {
    echo "case-staged-lint: the no-op is not named" >&2; cat out.txt >&2; exit 1; }
else
  echo "case-staged-lint: a non-python commit went red" >&2; cat out.txt >&2; exit 1
fi

# A fixable finding (unused import) is autofixed and restaged.
printf 'import os\nprint("hi")\n' > fixme.py
git add fixme.py
if python3 "$script" --staged > out.txt 2>&1; then
  grep -q "autofixed and restaged 1 file(s)" out.txt || {
    echo "case-staged-lint: the autofix is not reported" >&2; cat out.txt >&2; exit 1; }
  git diff --cached --name-only | grep -q fixme.py || {
    echo "case-staged-lint: the fixed file was not restaged" >&2; exit 1; }
else
  echo "case-staged-lint: a fixable finding went red" >&2; cat out.txt >&2; exit 1
fi

# An unfixable finding (undefined name) goes red.
printf 'print(undefined_name)\n' > broken.py
git add broken.py
if python3 "$script" --staged > out.txt 2>&1; then
  echo "case-staged-lint: an unfixable finding passed the gate" >&2; exit 1
fi
grep -q "findings remain after autofix" out.txt || {
  echo "case-staged-lint: the red is not about findings" >&2; cat out.txt >&2; exit 1; }
git reset -q broken.py && rm broken.py

# A partially-staged file is skipped by name, and still red on findings.
printf 'import os\nprint("worktree")\n' > partial.py
git add partial.py
printf 'import sys\nprint("worktree + unstaged")\n' >> partial.py
if python3 "$script" --staged > out.txt 2>&1; then
  echo "case-staged-lint: a partially-staged dirty file passed" >&2; exit 1
fi
grep -q "skipped (partially staged" out.txt || {
  echo "case-staged-lint: the partial-staging skip is not named" >&2; cat out.txt >&2; exit 1; }
git diff --cached -- partial.py | grep -q "worktree + unstaged" && {
  echo "case-staged-lint: unstaged work was swallowed into the index" >&2; exit 1; }

echo "case-staged-lint: rejection proof holds"
exit 0
