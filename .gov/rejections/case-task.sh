#!/bin/sh
# gate: task
# Proves the task gate rejects (D43): after a governance adoption, a card
# pinning the OLD rule-set hash goes STALE and fails check, naming the
# card — pasted-rule drift is detectable instead of silent.
set -u
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

# Resolve the govrail package from this repository (self-test runs us
# with the repository root as cwd; `gov` may not be on PATH here).
repo_root=$(pwd)

cd "$scratch" || exit 1
mkdir -p .gov/tasks
printf '# Rules\n' > .gov/rules.md
printf '{"gates": []}\n' > gates.json

PYTHONPATH="$repo_root" python3 -m gov task new "Brief me" > out.txt 2>&1 || {
  echo "case-task: opening a card failed" >&2
  cat out.txt >&2
  exit 1
}
PYTHONPATH="$repo_root" python3 -m gov task check > out.txt 2>&1 || {
  echo "case-task: a fresh card did not pass check" >&2
  cat out.txt >&2
  exit 1
}

# The adoption: the rule set moves under the open card.
printf '\n## 8. New rule adopted mid-flight\n' >> .gov/rules.md
if PYTHONPATH="$repo_root" python3 -m gov task check > out.txt 2>&1; then
  echo "case-task: a card pinning a pre-adoption hash passed check" >&2
  cat out.txt >&2
  exit 1
fi
grep -q 'STALE' out.txt || {
  echo "case-task: the stale card is not named STALE" >&2
  cat out.txt >&2
  exit 1
}
grep -q 'T-0001' out.txt || {
  echo "case-task: the failure does not name the card id" >&2
  cat out.txt >&2
  exit 1
}

echo "case-task: rejection proof holds"
exit 0
