#!/bin/sh
# gate: doc-sync
# Proves the CHANGELOG ↔ HIGHLIGHTS pairing rejects (D37): a released
# version in CHANGELOG with no HIGHLIGHTS section goes red naming it, and
# the section closes the loop. A version only HIGHLIGHTS knows is caught
# too — the pairing is not one-directional.
set -u
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

# Resolve the govrail package from this repository (self-test runs us
# with the repository root as cwd; `gov` may not be on PATH here).
repo_root=$(pwd)

cd "$scratch" || exit 1
mkdir -p gov
printf '# Changelog\n\n## [0.14.0] (2026-09-04)\n\n### Features\n\n* x\n' > CHANGELOG.md
printf '# What'"'"'s new\n\n## 0.13.0 — old\n\n- y\n' > gov/HIGHLIGHTS.md

# The release merge's failure mode: CHANGELOG moved, HIGHLIGHTS did not.
if PYTHONPATH="$repo_root" python3 -m gov verify-doc-sync > out.txt 2>&1; then
  echo "case-doc-sync: a version without a HIGHLIGHTS section passed" >&2
  cat out.txt >&2
  exit 1
fi
grep -q '0.14.0' out.txt || {
  echo "case-doc-sync: the unpaired version is not named" >&2
  cat out.txt >&2
  exit 1
}

# The fix is the section: the gate turns green on it.
printf '# What'"'"'s new\n\n## 0.14.0 — new\n\n- x\n\n## 0.13.0 — old\n\n- y\n' > gov/HIGHLIGHTS.md
PYTHONPATH="$repo_root" python3 -m gov verify-doc-sync > out.txt 2>&1 || {
  echo "case-doc-sync: the paired tree was rejected" >&2
  cat out.txt >&2
  exit 1
}

# Ahead-of-release drift is the mirror violation.
printf '# Changelog\n\n## [0.13.0] (2026-09-04)\n\n### Features\n\n* y\n' > CHANGELOG.md
if PYTHONPATH="$repo_root" python3 -m gov verify-doc-sync > out.txt 2>&1; then
  echo "case-doc-sync: a HIGHLIGHTS section ahead of CHANGELOG passed" >&2
  cat out.txt >&2
  exit 1
fi

echo "case-doc-sync: rejection proof holds"
exit 0
