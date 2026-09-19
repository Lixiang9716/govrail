#!/bin/sh
# gate: skill-coverage
# Proves the skill-coverage gate rejects (rule 6): a shipped command
# absent from the router skill goes red naming the command, a reasoned
# exclusion is honored, a stale exclusion and an unreadable registry
# both fail loud with exit 2, and a fully routed skill passes.
set -u
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

script="$PWD/scripts/check_skill_coverage.py"

# Fixture: a two-command registry and a config pointing at a skill file.
mk_registry() {
  mkdir -p "$scratch/gov"
  cat > "$scratch/gov/commands.py" <<'EOF'
COMMANDS = {
    "alpha": "do alpha",
    "beta": "do beta",
}
EOF
}
mk_config() {
  cat > "$scratch/cov.json" <<'EOF'
{"registry": "gov/commands.py", "skill": "SKILL.md", "exclusions": {}}
EOF
}
mk_registry
mk_config

# A fully routed skill passes.
printf -- "- \`gov alpha\` — routes alpha\n- \`gov beta\` — routes beta\n" \
  > "$scratch/SKILL.md"
if python3 "$script" --root "$scratch" --config "$scratch/cov.json" \
    >"$scratch/out.txt" 2>&1; then
  : green
else
  echo "case-skill-coverage: a fully routed skill went red" >&2
  cat "$scratch/out.txt" >&2
  exit 1
fi

# beta vanishes from the skill: red, naming the command and the fix.
printf -- "- \`gov alpha\` — routes alpha\n" > "$scratch/SKILL.md"
if python3 "$script" --root "$scratch" --config "$scratch/cov.json" \
    >"$scratch/out.txt" 2>&1; then
  echo "case-skill-coverage: an unrouted command passed the gate" >&2
  exit 1
fi
grep -q "command 'beta' is not routed" "$scratch/out.txt" || {
  echo "case-skill-coverage: the violation does not name the missing command" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}

# A reasoned exclusion is honored at its own scope.
cat > "$scratch/cov.json" <<'EOF'
{"registry": "gov/commands.py", "skill": "SKILL.md",
 "exclusions": {"beta": "internal plumbing, never invoked directly"}}
EOF
if python3 "$script" --root "$scratch" --config "$scratch/cov.json" \
    >"$scratch/out.txt" 2>&1; then
  grep -q "1 excluded with reason" "$scratch/out.txt" || {
    echo "case-skill-coverage: the green line does not count the exclusion" >&2
    cat "$scratch/out.txt" >&2
    exit 1
  }
else
  echo "case-skill-coverage: a reasoned exclusion was rejected" >&2
  cat "$scratch/out.txt" >&2
  exit 1
fi

# A stale exclusion (no such command) fails loud with exit 2.
cat > "$scratch/cov.json" <<'EOF'
{"registry": "gov/commands.py", "skill": "SKILL.md",
 "exclusions": {"gamma": "renamed away long ago"}}
EOF
if python3 "$script" --root "$scratch" --config "$scratch/cov.json" \
    >"$scratch/out.txt" 2>&1; then
  echo "case-skill-coverage: a stale exclusion passed the gate" >&2
  exit 1
fi
[ "$(python3 "$script" --root "$scratch" --config "$scratch/cov.json" \
    >/dev/null 2>&1; echo $?)" = "2" ] || {
  echo "case-skill-coverage: a stale exclusion is not a config error (exit 2)" >&2
  exit 1
}

# An unreadable registry fails loud with exit 2 (rule 5).
cat > "$scratch/gov/commands.py" <<'EOF'
COMMANDS = build_commands_dynamically()
EOF
cat > "$scratch/cov.json" <<'EOF'
{"registry": "gov/commands.py", "skill": "SKILL.md", "exclusions": {}}
EOF
python3 "$script" --root "$scratch" --config "$scratch/cov.json" \
  >"$scratch/out.txt" 2>&1
[ $? = "2" ] || {
  echo "case-skill-coverage: an unreadable registry is not a config error" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}

echo "case-skill-coverage: rejection proof holds"
exit 0
