#!/bin/sh
# gate: doc-budgets
# Proves the doc-budgets gate rejects (rule 6): an over-ceiling doc goes
# red naming path and counts, a missing declared doc goes red as a stale
# row, an unknown config key fails loud with exit 2, and a within-budget
# tree passes.
set -u
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

script="$PWD/scripts/check_doc_budgets.py"
mkdir -p "$scratch/docs"

# Fixture docs: 40 chars (inside every budget below) and 120 chars.
printf 'x%.0s' $(seq 1 40) > "$scratch/docs/small.md"
printf 'y%.0s' $(seq 1 120) > "$scratch/docs/big.md"
cat > "$scratch/budgets.json" <<'EOF'
{"limits": {"docs/small.md": 100, "docs/big.md": 100}}
EOF

# big.md over its ceiling: red, naming path and counts.
if python3 "$script" --root "$scratch" --config "$scratch/budgets.json" \
    >"$scratch/out.txt" 2>&1; then
  echo "case-doc-budgets: an over-ceiling doc passed the gate" >&2
  exit 1
fi
grep -q "docs/big.md: 120 characters (budget 100" "$scratch/out.txt" || {
  echo "case-doc-budgets: the violation does not name path and counts" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}

# Raising the ceiling to cover both: green.
cat > "$scratch/budgets.json" <<'EOF'
{"limits": {"docs/small.md": 100, "docs/big.md": 200}}
EOF
if python3 "$script" --root "$scratch" --config "$scratch/budgets.json" \
    >"$scratch/out.txt" 2>&1; then
  grep -q "2 doc(s) within" "$scratch/out.txt" || {
    echo "case-doc-budgets: the green line does not count the docs" >&2
    cat "$scratch/out.txt" >&2
    exit 1
  }
else
  echo "case-doc-budgets: within-budget docs went red" >&2
  cat "$scratch/out.txt" >&2
  exit 1
fi

# A declared doc that vanished: red as a stale row (rule 5).
cat > "$scratch/budgets.json" <<'EOF'
{"limits": {"docs/small.md": 100, "docs/ghost.md": 100}}
EOF
if python3 "$script" --root "$scratch" --config "$scratch/budgets.json" \
    >"$scratch/out.txt" 2>&1; then
  echo "case-doc-budgets: a missing declared doc passed the gate" >&2
  exit 1
fi
grep -q "docs/ghost.md: declared in the budget config but missing" \
  "$scratch/out.txt" || {
  echo "case-doc-budgets: the stale row is not named" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}

# An unknown config key fails loud with exit 2.
cat > "$scratch/budgets.json" <<'EOF'
{"limits": {"docs/small.md": 100}, "word": true}
EOF
python3 "$script" --root "$scratch" --config "$scratch/budgets.json" \
  >"$scratch/out.txt" 2>&1
[ $? = "2" ] || {
  echo "case-doc-budgets: an unknown config key is not a config error" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}

# A generated region inside a doc is stripped before measuring: growth
# in the block does not eat the curated budget.
printf 'c%.0s' $(seq 1 60) > "$scratch/docs/curated.md"
cat >> "$scratch/docs/curated.md" <<'EOF'
<!-- gov:commands BEGIN — generated -->
zzzz
<!-- gov:commands END -->
EOF
cat > "$scratch/budgets.json" <<'EOF'
{"limits": {"docs/curated.md": 80}}
EOF
if python3 "$script" --root "$scratch" --config "$scratch/budgets.json" \
    >"$scratch/out.txt" 2>&1; then
  : green
else
  echo "case-doc-budgets: generated-region growth ate the curated budget" >&2
  cat "$scratch/out.txt" >&2
  exit 1
fi

echo "case-doc-budgets: rejection proof holds"
exit 0
