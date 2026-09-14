#!/bin/sh
# gate: archive
# Proves the demo's archived-notes seal rejects: a tampered archived note
# fails naming the file, and re-sealing refuses to launder the drift.
set -u
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
cd "$scratch" || exit 1

note=.agents/notes/archived/process/2026-01-01-x.md
mkdir -p .agents/notes/archived/process
printf '# Agent Note: x\n\nStatus: archived\n' > "$note"

gov archive-notes > /dev/null 2>&1 || {
  echo "case-archive: sealing a fresh archive failed" >&2
  exit 1
}
gov verify-archive > /dev/null 2>&1 || {
  echo "case-archive: the fresh seal did not verify" >&2
  exit 1
}
printf '# Agent Note: x — TAMPERED\n' > "$note"
if gov verify-archive > /dev/null 2>&1; then
  echo "case-archive: a tampered archived note passed the seal check" >&2
  exit 1
fi
if gov archive-notes > /dev/null 2>&1; then
  echo "case-archive: re-sealing a drifted archive was allowed" >&2
  exit 1
fi
echo "case-archive: rejection proof holds"
