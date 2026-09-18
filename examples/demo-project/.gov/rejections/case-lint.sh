#!/bin/sh
# gate: lint
# Proves the lint gate can go red (rule 6): a fixture module carrying a
# pyflakes violation (unused import) is named file and rule; the same
# fixture clean passes. The violation class is the one this PR's own
# CI caught (62 unused imports riding a mechanical rewiring).
set -u
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

mkdir -p "$scratch/pkg"
printf 'import os\nx = 1\n' > "$scratch/pkg/bad.py"
printf 'y = 2\n' > "$scratch/pkg/fine.py"

if ruff check "$scratch" >"$scratch/out.txt" 2>&1; then
  echo "case-lint: an unused import passed the gate" >&2
  exit 1
fi
grep -q 'pkg/bad.py' "$scratch/out.txt" || {
  echo "case-lint: the finding does not name the file" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}
grep -q 'F401' "$scratch/out.txt" || {
  echo "case-lint: the finding does not name the rule" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}

rm "$scratch/pkg/bad.py"
if ruff check "$scratch" >"$scratch/out.txt" 2>&1; then
  echo "case-lint: rejection proof holds"
  exit 0
fi
echo "case-lint: a clean fixture went red" >&2
cat "$scratch/out.txt" >&2
exit 1
