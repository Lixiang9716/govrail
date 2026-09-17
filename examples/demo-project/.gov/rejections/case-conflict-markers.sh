#!/bin/sh
# gate: conflict-markers
# Proves the conflict-markers gate rejects (#104/D38): a file staged with
# git conflict markers must go red naming file:line, the escape hatch must
# tolerate a deliberate literal, and a clean tree must pass.
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

# The near-miss from the issue: markers staged during a rebase.
printf 'intro\n<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> side\n' > doc.md
if PYTHONPATH="$repo_root" python3 -m gov verify-conflict-markers > out.txt 2>&1; then
  echo "case-conflict-markers: a marked file passed the gate" >&2
  exit 1
fi
grep -q 'doc.md:2' out.txt || {
  echo "case-conflict-markers: finding does not name file:line" >&2
  cat out.txt >&2
  exit 1
}

# The escape hatch: a deliberate literal with the ignore token passes.
printf 'resolved by hand\n' > doc.md
printf 'literal marker below is intentional gov:ignore-marker\n' > lit.md
printf '<<<<<<< HEAD gov:ignore-marker\n' >> lit.md
if PYTHONPATH="$repo_root" python3 -m gov verify-conflict-markers > out.txt 2>&1; then
  :
else
  echo "case-conflict-markers: the ignore token was not tolerated" >&2
  cat out.txt >&2
  exit 1
fi

# A clean tree passes.
rm doc.md lit.md
if PYTHONPATH="$repo_root" python3 -m gov verify-conflict-markers > out.txt 2>&1; then
  echo "case-conflict-markers: rejection proof holds"
  exit 0
fi
echo "case-conflict-markers: a clean tree went red" >&2
cat out.txt >&2
exit 1
