#!/bin/sh
# gate: decisions
# Proves the decisions gate rejects: a duplicated D-number and a gap in
# the series go red naming both, and a decision recording no options is
# refused — a decision recorded without what it beat invites
# re-litigation (D0/D3). A well-formed table passes first, so the reds
# are the violations and not the fixture.
set -u
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

# Resolve the govrail package from this repository (self-test runs us
# with the repository root as cwd; `gov` may not be on PATH here).
repo_root=$(pwd)

cd "$scratch" || exit 1
mkdir docs
printf '## D1 — a\n\n- **选项**：x\n\n- **状态**：已决\n' > docs/decisions.md
PYTHONPATH="$repo_root" python3 -m gov verify-decisions > out.txt 2>&1 || {
  echo "case-decisions: a well-formed table was rejected" >&2
  cat out.txt >&2
  exit 1
}

# Two branches allocating one number, and a hole between them.
printf '## D1 — a\n\n- **选项**：x\n\n## D1 — b\n\n- **选项**：x\n\n## D3 — c\n\n- **状态**：已决\n' > docs/decisions.md
if PYTHONPATH="$repo_root" python3 -m gov verify-decisions > out.txt 2>&1; then
  echo "case-decisions: a duplicate number passed the gate" >&2
  cat out.txt >&2
  exit 1
fi
grep -q 'duplicate' out.txt || {
  echo "case-decisions: the duplicate is not named" >&2
  cat out.txt >&2
  exit 1
}
grep -q 'missing: D2' out.txt || {
  echo "case-decisions: the gap is not named" >&2
  cat out.txt >&2
  exit 1
}
grep -q 'records no options' out.txt || {
  echo "case-decisions: the option-less entry is not named" >&2
  cat out.txt >&2
  exit 1
}

echo "case-decisions: rejection proof holds"
exit 0
