#!/bin/sh
# gate: pairing
# Proves the pre-commit hook honors the CONFIGURED contract (#110, and
# the advisory/blocking flip): pairing ships advisory, so a stale
# sidecar is NAMED at commit time without blocking; after the documented
# enforce step (remove allowFailure) the same drift blocks the commit
# naming the scoped fix, and the fixed pair lands.
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

# Deterministic hook resolution: GOV_BIN wins over PATH/module fallback.
export GOV_BIN="python3 -m gov"
export PYTHONPATH="$repo_root"

if python3 -m gov init --hooks --pre-commit > out.txt 2>&1; then
  :
else
  echo "case-pre-commit-hook: init --hooks --pre-commit failed" >&2
  cat out.txt >&2
  exit 1
fi
test -x .git/hooks/pre-commit || {
  echo "case-pre-commit-hook: the hook was not wired into .git/hooks" >&2
  exit 1
}

# A confirmed pair, committed through the hook (must pass).
mkdir -p docs
printf 'hello\n' > docs/a.md
printf 'nihao\n' > docs/a.zh.md
python3 -m gov verify-pairing --write docs/a.md > out.txt 2>&1 || {
  echo "case-pre-commit-hook: baselining the pair failed" >&2
  cat out.txt >&2
  exit 1
}
git add -A
git -c commit.gpgsign=false commit -qm baseline || {
  echo "case-pre-commit-hook: a confirmed pair failed the hook" >&2
  exit 1
}

# The hook honors gates.json (the H5 contract): pairing ships advisory,
# so the drift is NAMED at commit time but does not block yet.
printf 'hello v2\n' > docs/a.md
git add docs/a.md
git -c commit.gpgsign=false commit -qm drift > out.txt 2>&1 || {
  echo "case-pre-commit-hook: advisory pairing blocked a commit" >&2
  cat out.txt >&2
  exit 1
}
grep -q "verify_translation_pairing: 1 violation(s)" out.txt || {
  echo "case-pre-commit-hook: the advisory did not name the drift" >&2
  cat out.txt >&2
  exit 1
}
# The documented enforce step (init's next steps): remove allowFailure.
python3 - <<'PYEOF' || exit 1
import json
cfg = json.load(open("gates.json"))
for g in cfg["gates"]:
    if g["id"] == "pairing":
        g.pop("allowFailure", None)
json.dump(cfg, open("gates.json", "w"), indent=2)
PYEOF
python3 -m gov verify-plane --write > /dev/null 2>&1 || {
  echo "case-pre-commit-hook: the enforce flip could not be recorded" >&2
  exit 1
}
printf 'hello v3\n' > docs/a.md
git add docs/a.md
if git -c commit.gpgsign=false commit -qm drift > out.txt 2>&1; then
  echo "case-pre-commit-hook: a stale sidecar committed without complaint" >&2
  exit 1
fi
grep -q 'gov verify-pairing --write docs/a.md' out.txt || {
  echo "case-pre-commit-hook: the block does not name the scoped fix command" >&2
  cat out.txt >&2
  exit 1
}

# The scoped fix closes the loop: re-stage, commit lands.
python3 -m gov verify-pairing --write docs/a.md > out.txt 2>&1 || {
  echo "case-pre-commit-hook: the scoped fix failed" >&2
  cat out.txt >&2
  exit 1
}
git add -A
if git -c commit.gpgsign=false commit -qm drift > out.txt 2>&1; then
  echo "case-pre-commit-hook: rejection proof holds"
  exit 0
fi
echo "case-pre-commit-hook: the fixed pair still could not commit" >&2
cat out.txt >&2
exit 1
