#!/bin/sh
# gate: check
# Proves the check gate rejects (D55): a #172-class violation in the
# change scope goes red naming file and rule, pre-existing legacy code
# does NOT break the advisory-first first run (the scope judges what
# changed, never history), and --all is the sweep that judges legacy.
set -u
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

# Resolve the govrail package from this repository (self-test runs us
# with the repository root as cwd; `gov` may not be on PATH here).
repo_root=$(pwd)
export GOV_BIN="python3 -m gov"
export PYTHONPATH="$repo_root"

cd "$scratch" || exit 1
git init -q .
git config user.email t@t
git config user.name t

# Legacy product code, committed BEFORE the plane lands: a text-mode
# spawn without encoding= (#172's class).
mkdir -p src
printf 'import subprocess\nsubprocess.run(["ls"], capture_output=True, text=True)\n' > src/legacy.py
printf 'seed\n' > seed.txt
git add -A
git -c commit.gpgsign=false commit -qm legacy

python3 -m gov init > out.txt 2>&1 || {
  echo "case-check: init failed" >&2
  cat out.txt >&2
  exit 1
}

# Advisory-first: the first run after adoption judges the CHANGE SCOPE.
# The plane files are untracked (dirty worktree -> HEAD), legacy.py is
# not in it, and the gate must stay green on code adoption never touched.
if python3 -m gov check > out.txt 2>&1; then
  : green
else
  echo "case-check: the first run went red on pre-existing legacy code" >&2
  cat out.txt >&2
  exit 1
fi

# A violation in the change scope: red, naming file and rule.
printf 'import subprocess\nsubprocess.run(["git", "status"], capture_output=True, text=True)\n' > src/newcode.py
if python3 -m gov check > out.txt 2>&1; then
  echo "case-check: a violation in the change scope passed the gate" >&2
  exit 1
fi
grep -q 'src/newcode.py' out.txt || {
  echo "case-check: the finding does not name the file" >&2
  cat out.txt >&2
  exit 1
}
grep -q 'subprocess-text-encoding' out.txt || {
  echo "case-check: the finding does not name the rule" >&2
  cat out.txt >&2
  exit 1
}

# The whole-tree sweep (--all) is where legacy code is judged.
if python3 -m gov check --all > out.txt 2>&1; then
  echo "case-check: --all did not judge pre-existing legacy code" >&2
  exit 1
fi
grep -q 'src/legacy.py' out.txt || {
  echo "case-check: --all does not name legacy" >&2
  cat out.txt >&2
  exit 1
}

# A clean change scope passes.
rm src/newcode.py
if python3 -m gov check > out.txt 2>&1; then
  echo "case-check: rejection proof holds"
  exit 0
fi
echo "case-check: a clean change scope went red" >&2
cat out.txt >&2
exit 1
