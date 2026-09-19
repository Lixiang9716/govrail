#!/bin/sh
# gate: staged-derive
# Proves the staged-derive gate rejects (rule 6): staged inputs trigger
# the derivation and its outputs are restaged (green), non-input staged
# files are a named no-op, a failing derivation is red, and a repo
# without a derivation surface is a named skip.
set -u
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

script="$PWD/scripts/staged_derive.py"
git init -q "$scratch" && cd "$scratch" || exit 2
git config user.email t@t && git config user.name t
mkdir -p scripts

# Stub derivation: touches its output, exits 0.
cat > scripts/derive_all.py <<'EOF'
import pathlib, sys
pathlib.Path("README.md").write_text("derived " + pathlib.Path("in.txt").read_text())
EOF
echo hi > in.txt && git add in.txt scripts/derive_all.py
if python3 "$script" --staged > out.txt 2>&1; then
  grep -q "regenerated and restaged" out.txt || {
    echo "case-staged-derive: the regeneration is not reported" >&2; cat out.txt >&2; exit 1; }
  git diff --cached --name-only | grep -q README.md || {
    echo "case-staged-derive: the derived output was not restaged" >&2; exit 1; }
else
  echo "case-staged-derive: a triggered derivation went red" >&2; cat out.txt >&2; exit 1
fi

# Non-input staged files: named no-op (no run of the deriver). Unstage
# the stub itself too — the derivation tooling IS an input by design.
git reset -q in.txt scripts/derive_all.py
echo hi > docs.md && git add docs.md
if python3 "$script" --staged > out.txt 2>&1; then
  grep -q "nothing to regenerate" out.txt || {
    echo "case-staged-derive: the no-op is not named" >&2; cat out.txt >&2; exit 1; }
  [ ! -f SENTINEL ] || {
    echo "case-staged-derive: the deriver ran on non-inputs" >&2; exit 1; }
else
  echo "case-staged-derive: non-inputs went red" >&2; cat out.txt >&2; exit 1
fi

# A failing derivation is red (the stub restaged: it is an input).
git add in.txt scripts/derive_all.py
cat > scripts/derive_all.py <<'EOF'
import sys
sys.exit(1)
EOF
if python3 "$script" --staged > out.txt 2>&1; then
  echo "case-staged-derive: a failing derivation passed" >&2; exit 1
fi
grep -q "derivation failed" out.txt || {
  echo "case-staged-derive: the failure is not named" >&2; cat out.txt >&2; exit 1; }

# A repo without the derivation surface: named skip, exit 0 (an input
# IS staged, so the intersection fires and the missing surface shows).
mkdir -p "$scratch/plain/gov" && cd "$scratch/plain" || exit 2
git init -q . && echo x > gov/mod.py && git add gov/mod.py
if python3 "$script" --staged > out.txt 2>&1; then
  grep -q "derivation surface absent" out.txt || {
    echo "case-staged-derive: the surface skip is not named" >&2; cat out.txt >&2; exit 1; }
else
  echo "case-staged-derive: a repo without the surface went red" >&2; cat out.txt >&2; exit 1
fi

echo "case-staged-derive: rejection proof holds"
exit 0
