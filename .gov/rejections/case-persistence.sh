#!/bin/sh
# gate: persistence
# Proves the persistence gate rejects (rule 6): touching a live schema
# without a record is red; a broken chain is red; a TODO draft is red;
# a stale catalog is red; an unreadable schema is exit 2; a complete
# chain with a fresh catalog passes.
set -u
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

script="$PWD/scripts/check_persistence.py"
mkdir -p "$scratch/docs/persistence/schemas" "$scratch/docs/persistence/changes"

mk_type() {  # $1 = name; writes a schema and prints its digest
  cat > "$scratch/docs/persistence/schemas/$1.schema.json" <<EOF
{"type": "$1", "artifact": ".gov/$1.json", "kind": "json-object",
 "writer": "x.py", "readers": ["x"], "fields": {"a": "string"}}
EOF
  python3 -c "import hashlib,sys;print(hashlib.sha256(open('$scratch/docs/persistence/schemas/$1.schema.json','rb').read()).hexdigest())"
}

D1=$(mk_type alpha)
D2=$(mk_type beta)
cat > "$scratch/docs/persistence/changes/0001-baseline.md" <<EOF
# Persistence change 0001: baseline
\`\`\`json
{"record": "0001", "date": "2026-09-19", "class": "baseline",
 "changes": {"alpha": {"before": null, "after": "$D1"},
             "beta": {"before": null, "after": "$D2"}}}
\`\`\`
EOF
python3 "$script" --root "$scratch" --update >/dev/null 2>&1
if python3 "$script" --root "$scratch" >"$scratch/out.txt" 2>&1; then
  : green
else
  echo "case-persistence: a complete chain went red" >&2
  cat "$scratch/out.txt" >&2
  exit 1
fi

# Touch the live schema without a record: red (anchor breaks).
sed -i 's/"a": "string"/"a": "string-tampered"/' \
  "$scratch/docs/persistence/schemas/alpha.schema.json"
if python3 "$script" --root "$scratch" >"$scratch/out.txt" 2>&1; then
  echo "case-persistence: an unacknowledged schema edit passed" >&2
  exit 1
fi
grep -q "live schema digest differs" "$scratch/out.txt" || {
  echo "case-persistence: the anchor violation is not named" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}
D1b=$(mk_type alpha)  # restore

# Broken chain: successor's before != predecessor's after.
D2NEW=$(mk_type beta > /dev/null; mk_type beta)
cat > "$scratch/docs/persistence/changes/0002-tweak.md" <<EOF
# Persistence change 0002: tweak beta
\`\`\`json
{"record": "0002", "date": "2026-09-19", "class": "compatible",
 "changes": {"beta": {"before": "deadbeef", "after": "$D2NEW"}}}
\`\`\`
EOF
if python3 "$script" --root "$scratch" >"$scratch/out.txt" 2>&1; then
  echo "case-persistence: a broken chain passed" >&2
  exit 1
fi
grep -q "does not chain" "$scratch/out.txt" || {
  echo "case-persistence: the chain break is not named" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}
rm "$scratch/docs/persistence/changes/0002-tweak.md"

# A TODO draft is red.
cat > "$scratch/docs/persistence/changes/0003-wip.md" <<EOF
# Persistence change 0003: wip
TODO: fill the digests
\`\`\`json
{"record": "0003", "date": "2026-09-19", "class": "compatible",
 "changes": {"beta": {"before": "$D2NEW", "after": "$D2NEW"}}}
\`\`\`
EOF
if python3 "$script" --root "$scratch" >"$scratch/out.txt" 2>&1; then
  echo "case-persistence: a TODO draft passed" >&2
  exit 1
fi
grep -q "unfinished draft" "$scratch/out.txt" || {
  echo "case-persistence: the TODO rejection is not named" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}
rm "$scratch/docs/persistence/changes/0003-wip.md"

# A stale catalog is red until regenerated.
echo '{"types": {}}' > "$scratch/docs/persistence/catalog.json"
if python3 "$script" --root "$scratch" >"$scratch/out.txt" 2>&1; then
  echo "case-persistence: a stale catalog passed" >&2
  exit 1
fi
grep -q "catalog.json is stale" "$scratch/out.txt" || {
  echo "case-persistence: the stale catalog is not named" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}
python3 "$script" --root "$scratch" --update >/dev/null 2>&1

# An unreadable schema is a config error (exit 2).
echo "not json" > "$scratch/docs/persistence/schemas/alpha.schema.json"
python3 "$script" --root "$scratch" >"$scratch/out.txt" 2>&1
[ $? = "2" ] || {
  echo "case-persistence: an unreadable schema is not a config error" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}

echo "case-persistence: rejection proof holds"
exit 0
