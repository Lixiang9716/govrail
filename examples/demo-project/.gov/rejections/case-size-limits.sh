#!/bin/sh
# gate: size-limits
# Proves the size gate rejects (rule 6): a module over its declared
# limit goes red naming path and count, an explicit override budget is
# honored at its own limit, and a within-limits tree passes.
set -u
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

python3 - "$scratch" <<'PYEOF'
import pathlib, sys
root = pathlib.Path(sys.argv[1])
gov = root / "gov"
gov.mkdir(parents=True)
# 40 lines: under the default budget of this fixture's config.
(gov / "small.py").write_text("\n".join(f"# l{i}" for i in range(40)) + "\n", encoding="utf-8")
# 120 lines: over the fixture's default of 100.
(gov / "big.py").write_text("\n".join(f"# l{i}" for i in range(120)) + "\n", encoding="utf-8")
(root / "limits.json").write_text(
    '{"default": 100, "scan": ["gov/*.py"], "overrides": {"gov/small.py": 50}}',
    encoding="utf-8")
PYEOF

script="$PWD/scripts/check_size_limits.py"

# A within-limits tree passes.
cat > "$scratch/limits-ok.json" <<EOF
{"default": 200, "scan": ["gov/*.py"], "overrides": {}}
EOF
if python3 "$script" --root "$scratch" --config "$scratch/limits-ok.json" >"$scratch/out.txt" 2>&1; then
  : green
else
  echo "case-size-limits: a within-limits tree went red" >&2
  cat "$scratch/out.txt" >&2
  exit 1
fi

# big.py is over the default budget: red, naming path and count.
if python3 "$script" --root "$scratch" --config "$scratch/limits.json" >"$scratch/out.txt" 2>&1; then
  echo "case-size-limits: an over-limit module passed the gate" >&2
  exit 1
fi
grep -q "gov/big.py: 120 lines (limit 100" "$scratch/out.txt" || {
  echo "case-size-limits: the violation does not name path and count" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}

# An override budget is honored exactly: small.py (40 lines) under its
# 50-line override stays green when only small.py is scanned.
cat > "$scratch/limits-small.json" <<EOF
{"default": 100, "scan": ["gov/small.py"], "overrides": {"gov/small.py": 50}}
EOF
if python3 "$script" --root "$scratch" --config "$scratch/limits-small.json" >"$scratch/out.txt" 2>&1; then
  : green
else
  echo "case-size-limits: an override budget rejected a within-limit file" >&2
  cat "$scratch/out.txt" >&2
  exit 1
fi

echo "case-size-limits: rejection proof holds"
exit 0
