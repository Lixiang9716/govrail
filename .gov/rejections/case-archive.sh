#!/bin/sh
# gate: archive
# Proves the archived-notes seal rejects: a tampered archived note fails
# the seal check naming the file, and re-sealing refuses — a drift is
# never washed by a second seal (rule 4, no laundering).
set -u
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

# Resolve the govrail package from this repository (self-test runs us
# with the repository root as cwd; `gov` may not be on PATH here).
repo_root=$(pwd)

cd "$scratch" || exit 1
note=.agents/notes/archived/process/2026-01-01-x.md
mkdir -p .agents/notes/archived/process
printf '# Agent Note: x\n\nStatus: archived\n' > "$note"

# Seal it: the manifest pins a sha256 per file.
PYTHONPATH="$repo_root" python3 -m gov archive-notes > out.txt 2>&1 || {
  echo "case-archive: sealing a fresh archive failed" >&2
  cat out.txt >&2
  exit 1
}
PYTHONPATH="$repo_root" python3 -m gov verify-archive > out.txt 2>&1 || {
  echo "case-archive: the freshly sealed archive did not verify" >&2
  cat out.txt >&2
  exit 1
}

# Editing a frozen note is the violation rule 4 exists to catch.
printf '# Agent Note: x  # edited after the seal\n\nStatus: archived\n' > "$note"
if PYTHONPATH="$repo_root" python3 -m gov verify-archive > out.txt 2>&1; then
  echo "case-archive: a tampered archived note passed the seal check" >&2
  cat out.txt >&2
  exit 1
fi
grep -q '2026-01-01-x.md' out.txt || {
  echo "case-archive: the drifted file is not named" >&2
  cat out.txt >&2
  exit 1
}

# Re-sealing must refuse: otherwise the drift could be laundered away.
if PYTHONPATH="$repo_root" python3 -m gov archive-notes > out.txt 2>&1; then
  echo "case-archive: re-sealing a drifted archive was allowed" >&2
  cat out.txt >&2
  exit 1
fi

echo "case-archive: rejection proof holds"
exit 0
