#!/bin/sh
# gate: plane
# Proves the governance-plane seal rejects (rule 6, for the plane itself):
# a tampered or deleted plane config fails verify-plane naming the file,
# and an explicit --write re-baseline is the only way back to green.
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
printf 'seed\n' > seed.txt
git add -A
git -c commit.gpgsign=false commit -qm init
export GOV_BIN="python3 -m gov"
export PYTHONPATH="$repo_root"

python3 -m gov init > out.txt 2>&1 || {
  echo "case-plane: init failed" >&2
  cat out.txt >&2
  exit 1
}
# commit the plane: the restore step checks rules.md out of git, and an
# untracked file has no base to restore to
git add -A
git -c commit.gpgsign=false commit -qm plane
python3 -m gov verify-plane > out.txt 2>&1 || {
  echo "case-plane: a freshly sealed plane must verify green" >&2
  cat out.txt >&2
  exit 1
}

# TAMPER: a gate is deleted from the constitution behind the seal.
python3 - <<'PYEOF' || exit 1
import json
cfg = json.load(open("gates.json"))
cfg["gates"] = [g for g in cfg["gates"] if g["id"] != "plane"]
json.dump(cfg, open("gates.json", "w"), indent=2)
PYEOF
if python3 -m gov verify-plane > out.txt 2>&1; then
  echo "case-plane: a gutted gate set passed the plane seal" >&2
  exit 1
fi
grep -q 'gates.json' out.txt || {
  echo "case-plane: the drift is not named" >&2
  cat out.txt >&2
  exit 1
}

# DELETION drifts too: removing a sealed config cannot read as green.
rm .gov/rules.md
if python3 -m gov verify-plane > out.txt 2>&1; then
  echo "case-plane: a deleted rules.md passed the plane seal" >&2
  exit 1
fi
grep -q 'rules.md' out.txt || {
  echo "case-plane: the deletion is not named" >&2
  cat out.txt >&2
  exit 1
}

git checkout -- .gov/rules.md 2>/dev/null || git checkout -q -- .gov/rules.md

# The explicit re-baseline is the only way back: it accepts the CURRENT
# state loudly, after which the plane is green again.
python3 -m gov verify-plane --write --confirm-unattended > out.txt 2>&1 || {
  echo "case-plane: --write refused a restorable state" >&2
  cat out.txt >&2
  exit 1
}
python3 -m gov verify-plane > out.txt 2>&1 || {
  echo "case-plane: still red after explicit re-baseline" >&2
  cat out.txt >&2
  exit 1
}

echo "case-plane: rejection proof holds"
exit 0
