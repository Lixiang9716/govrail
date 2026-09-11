#!/bin/sh
# gate: self-test
# Proves the self-test harness rejects: a project case that fails must fail
# the run and be named, while the case beside it is still reported — a
# green `gov self-test` is evidence, not a formality (rule 6). Runs the
# harness against a scratch project, never against this one.
set -u
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

# Resolve the govrail package from this repository (self-test runs us
# with the repository root as cwd; `gov` may not be on PATH here).
repo_root=$(pwd)

cd "$scratch" || exit 1
mkdir -p .gov/rejections
printf '#!/bin/sh\nexit 0\n' > .gov/rejections/case-holds.sh
printf '#!/bin/sh\nexit 1\n' > .gov/rejections/case-broken.sh
chmod +x .gov/rejections/case-holds.sh .gov/rejections/case-broken.sh

if PYTHONPATH="$repo_root" python3 -m gov self-test --scope project > out.txt 2>&1; then
  echo "case-self-test: a failing rejection case passed the harness" >&2
  cat out.txt >&2
  exit 1
fi
grep -q 'FAIL .gov/rejections/case-broken.sh' out.txt || {
  echo "case-self-test: the failing case is not named as the failure" >&2
  cat out.txt >&2
  exit 1
}
grep -q 'PASS .gov/rejections/case-holds.sh' out.txt || {
  echo "case-self-test: the case that held was not reported" >&2
  cat out.txt >&2
  exit 1
}

echo "case-self-test: rejection proof holds"
exit 0
