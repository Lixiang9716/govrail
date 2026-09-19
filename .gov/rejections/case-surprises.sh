#!/bin/sh
# gate: surprises
# Proves the surprises gate rejects (rule 6): a signature at the
# threshold without a linked process note goes red naming the sig, a
# note citing surprise:<sig> turns it green, a one-sided entry goes red,
# a corrupt ledger line is a config error (exit 2), and a below-threshold
# ledger passes untouched.
set -u
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

script="$PWD/scripts/check_surprises.py"
mkdir -p "$scratch/.gov" "$scratch/.agents/notes/implemented/process"

# Below threshold: two surprises, no note owed — green.
cat > "$scratch/.gov/surprises.jsonl" <<'EOF'
{"ts": "2026-09-19T00:00:00+00:00", "sig": "register-stale", "expectation": "row said 8 rules", "reality": "it has 10", "surface": "docs/truth-sources.md"}
{"ts": "2026-09-19T00:01:00+00:00", "sig": "register-stale", "expectation": "row drift again", "reality": "another stale row", "surface": null}
EOF
if python3 "$script" --root "$scratch" >"$scratch/out.txt" 2>&1; then
  : green
else
  echo "case-surprises: a below-threshold ledger went red" >&2
  cat "$scratch/out.txt" >&2
  exit 1
fi

# Third strike, no note: red, naming the sig and the fix.
cat >> "$scratch/.gov/surprises.jsonl" <<'EOF'
{"ts": "2026-09-19T00:02:00+00:00", "sig": "register-stale", "expectation": "third time", "reality": "same drift", "surface": null}
EOF
if python3 "$script" --root "$scratch" >"$scratch/out.txt" 2>&1; then
  echo "case-surprises: a three-strike signature without a note passed" >&2
  exit 1
fi
grep -q "sig 'register-stale' has 3 recorded surprises" "$scratch/out.txt" || {
  echo "case-surprises: the violation does not name the sig and count" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}

# A process note citing surprise:<sig> satisfies the escalation.
cat > "$scratch/.agents/notes/implemented/process/2026-09-19-fix.md" <<'EOF'
# Agent Note: fix the register drift
## Problem
rows drift.
## Decision
pin added; covers surprise:register-stale.
## Alternatives considered
none.
EOF
if python3 "$script" --root "$scratch" >"$scratch/out.txt" 2>&1; then
  grep -q "1 escalated with linked improvement" "$scratch/out.txt" || {
    echo "case-surprises: the green line does not count the escalation" >&2
    cat "$scratch/out.txt" >&2
    exit 1
  }
else
  echo "case-surprises: a linked improvement was rejected" >&2
  cat "$scratch/out.txt" >&2
  exit 1
fi

# A one-sided entry (empty reality) goes red even below threshold.
cat > "$scratch/.gov/surprises.jsonl" <<'EOF'
{"ts": "2026-09-19T00:00:00+00:00", "sig": "hollow", "expectation": "something", "reality": "", "surface": null}
EOF
if python3 "$script" --root "$scratch" >"$scratch/out.txt" 2>&1; then
  echo "case-surprises: a one-sided surprise passed the gate" >&2
  exit 1
fi
grep -q "one-sided surprise" "$scratch/out.txt" || {
  echo "case-surprises: the one-sided rejection is not named" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}

# A corrupt ledger line is a config error (rule 5), not a pass.
echo "not json at all" >> "$scratch/.gov/surprises.jsonl"
python3 "$script" --root "$scratch" >"$scratch/out.txt" 2>&1
[ $? = "2" ] || {
  echo "case-surprises: a corrupt ledger line is not a config error" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}

echo "case-surprises: rejection proof holds"
exit 0
