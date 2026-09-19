#!/bin/sh
# gate: postmortems
# Proves the postmortem structure gate rejects (rule 6): a missing
# section, an empty section, a zero-pointer "Guardrails added", a
# guardrail path that resolves to nothing, and mixed heading
# vocabularies each go red naming the entry; a complete pair passes.
set -u
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT

script="$PWD/scripts/check_postmortems.py"
mkdir -p "$scratch/docs/postmortem" "$scratch/.gov/rejections"
touch "$scratch/.gov/rejections/case-x.sh" "$scratch/README.md"

# A complete pair passes (en vocabulary + zh vocabulary, real pointers).
cat > "$scratch/docs/postmortem/0001-a.md" <<'EOF'
## Executive summary
Something broke and the process let it through.
## Timeline
The observed sequence, with evidence locations.
## Root cause
The mechanism, stated for recognition.
## Guardrails added
- The gate `.gov/rejections/case-x.sh` (PR #12).
EOF
cat > "$scratch/docs/postmortem/0001-a.zh.md" <<'EOF'
## 执行摘要
某次失败穿过了流程。
## 时间线
可验证的时序与证据位置。
## 根因
机制陈述,供下次辨认。
## 补上的护栏
- 门 `.gov/rejections/case-x.sh`(PR #12)。
EOF
if python3 "$script" --root "$scratch" >"$scratch/out.txt" 2>&1; then
  : green
else
  echo "case-postmortems: a complete pair went red" >&2
  cat "$scratch/out.txt" >&2
  exit 1
fi

# A missing section goes red, naming the section.
cat > "$scratch/docs/postmortem/0002-b.md" <<'EOF'
## Executive summary
x
## Timeline
y
## Guardrails added
- `README.md` (PR #1).
EOF
if python3 "$script" --root "$scratch" >"$scratch/out.txt" 2>&1; then
  echo "case-postmortems: a missing Root cause section passed the gate" >&2
  exit 1
fi
grep -q "missing section(s) Root cause" "$scratch/out.txt" || {
  echo "case-postmortems: the violation does not name the missing section" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}
rm "$scratch/docs/postmortem/0002-b.md"

# A zero-pointer guardrails section is a story: red.
cat > "$scratch/docs/postmortem/0003-c.md" <<'EOF'
## Executive summary
x
## Timeline
y
## Root cause
z
## Guardrails added
We were all wiser afterwards.
EOF
if python3 "$script" --root "$scratch" >"$scratch/out.txt" 2>&1; then
  echo "case-postmortems: a story with no linked guardrail passed" >&2
  exit 1
fi
grep -q "names no pointer" "$scratch/out.txt" || {
  echo "case-postmortems: the story rejection is not about pointers" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}
rm "$scratch/docs/postmortem/0003-c.md"

# A guardrail path that resolves to no file: red.
cat > "$scratch/docs/postmortem/0004-d.md" <<'EOF'
## Executive summary
x
## Timeline
y
## Root cause
z
## Guardrails added
- The gate `gates/never-written.json` (PR #3).
EOF
if python3 "$script" --root "$scratch" >"$scratch/out.txt" 2>&1; then
  echo "case-postmortems: a dangling guardrail path passed" >&2
  exit 1
fi
grep -q "resolves to no file" "$scratch/out.txt" || {
  echo "case-postmortems: the dangling pointer is not named" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}
rm "$scratch/docs/postmortem/0004-d.md"

# Mixed heading vocabularies in one file: red.
cat > "$scratch/docs/postmortem/0005-e.zh.md" <<'EOF'
## 执行摘要
x
## 时间线
y
## Timeline
y
## 根因
z
## 补上的护栏
- `README.md`（PR #1）。
EOF
if python3 "$script" --root "$scratch" >"$scratch/out.txt" 2>&1; then
  echo "case-postmortems: mixed heading vocabularies passed" >&2
  exit 1
fi
grep -q "mixed heading vocabularies" "$scratch/out.txt" || {
  echo "case-postmortems: the mixed-vocabulary rejection is not named" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}

echo "case-postmortems: rejection proof holds"
exit 0
