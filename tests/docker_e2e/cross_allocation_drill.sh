#!/usr/bin/env bash
# The base-aware allocation drill (D58, batch 14): two REAL containers,
# two SEPARATE clones — the layout where `decision next --base` exists.
# The arc is D40's happy path: agent B, having fetched agent A's branch,
# asks for the next number AGAINST that branch and gets the number the
# eventual merged history will show — so no collision is ever created,
# and the verify net confirms the absorption.
#
#   1. agent A allocates D2 (next/add/push);
#   2. agent B, on its own branch, asks `decision next --base
#      origin/agent-a` — the answer must be D3 (A's D2 is visible
#      through the base), NOT the stale D2;
#   3. B adds D3, pushes; A runs verify-decisions --base: GREEN —
#      both appends absorbed, no collision ever created.
#
# Usage: cross_allocation_drill.sh [image]
set -u

IMAGE=${1:-govrail-e2e:3.12-slim}
WORK=$(mktemp -d /tmp/gov-alloc-XXXXXX)
FAILED=0

cleanup() {
  docker rm -f "$NA" "$NB" >/dev/null 2>&1
  docker run --rm -v "$WORK":/work "$IMAGE" \
    chown -R "$(id -u):$(id -g)" /work >/dev/null 2>&1
  rm -rf "$WORK"
}
trap cleanup EXIT

report() {
  if [ "$2" = "ok" ]; then echo "E2E $1: PASS"
  else echo "E2E $1: FAIL — $3"; FAILED=1; fi
}

# --- origin + one clone per agent ---------------------------------------
git init -q --bare -b main "$WORK/origin.git"
git init -q "$WORK/seed"
cd "$WORK/seed"
git config user.email t@t; git config user.name t
mkdir docs
printf '## D1 — adopt\n\n- **选项**：gov init\n\n- **状态**：已决\n' > docs/decisions.md
printf '# demo\n' > README.md
git add -A
git -c commit.gpgsign=false commit -qm seed
git push -q "$WORK/origin.git" HEAD:refs/heads/main
git clone -q "$WORK/origin.git" "$WORK/agent-a"
git clone -q "$WORK/origin.git" "$WORK/agent-b"
git -C "$WORK/agent-a" checkout -q -b agent-a
git -C "$WORK/agent-b" checkout -q -b agent-b

NA=$(docker run -d --rm -v "$WORK/agent-a:/work" -v "$WORK/origin.git":/origin \
  "$IMAGE" sleep infinity) || { echo "cannot start agent A"; exit 2; }
NB=$(docker run -d --rm -v "$WORK/agent-b:/work" -v "$WORK/origin.git":/origin \
  "$IMAGE" sleep infinity) || { echo "cannot start agent B"; docker rm -f "$NA" >/dev/null; exit 2; }
for who in "$NA" "$NB"; do
  docker exec "$who" git config --global --add safe.directory '*'
  docker exec "$who" bash -c 'git config --global user.email t@t && git config --global user.name agent'
  docker exec "$who" bash -c 'cd /work && git remote set-url origin /origin'
done

# --- agent A allocates D2 and pushes -------------------------------------
docker exec "$NA" bash -c 'cd /work && printf "agent a plan\n\n- **选项**：a\n\n- **状态**：已决\n" > /tmp/d2.md && gov decision add --from /tmp/d2.md && git add -A && git -c commit.gpgsign=false commit -qm "a allocates D2" && git push -q origin agent-a' \
  && report alloc_a_adds ok || report alloc_a_adds fail "agent a could not add+push D2"

# --- agent B asks the base-aware question --------------------------------
# B has NOT fetched agent-a yet: its own next says D2 (the stale view).
stale=$(docker exec "$NB" bash -c 'cd /work && gov decision next')
# the base must be a RESOLVABLE ref: a bare branch-name fetch writes
# only FETCH_HEAD, and trend/decision's --base needs the tracking ref.
# The fetch runs INSIDE /work — without cd it runs in /workspace, fails
# silently, and the base-aware next reads a ref that was never fetched.
docker exec "$NB" bash -c 'cd /work && git fetch -q origin +refs/heads/agent-a:refs/remotes/origin/agent-a'
answer=$(docker exec "$NB" bash -c 'cd /work && gov decision next --base origin/agent-a' 2>&1)
if [ "$stale" = "D2" ] && echo "$answer" | grep -q "D3"; then
  report alloc_base_aware ok
else
  report alloc_base_aware fail "stale next=$stale, base-aware next=$answer (expected D2 then D3)"
fi

# --- B follows the advice: D3, pushed ------------------------------------
if ! docker exec "$NB" bash -c 'cd /work && git merge -q --no-edit origin/agent-a && printf "agent b plan\n\n- **选项**：b\n\n- **状态**：已决\n" > /tmp/d3.md && gov decision add --from /tmp/d3.md --id D3 && git add -A && git -c commit.gpgsign=false commit -qm "b allocates D3" && git push -q origin agent-b' > /tmp/b-add.log 2>&1; then
  report alloc_b_adds_D3 fail "$(tail -2 /tmp/b-add.log | tr '\n' ' ')"
else
  report alloc_b_adds_D3 ok
fi

# --- the net confirms absorption: no collision, both appends present ----
VD=$(docker exec "$NA" bash -c 'cd /work && git fetch -q origin agent-b && gov verify-decisions --base origin/agent-b 2>&1')
if [ $? -eq 0 ]; then report alloc_absorbed ok
else report alloc_absorbed fail "the base-aware allocation did not absorb: $VD"; fi

if [ "$FAILED" = "1" ]; then
  echo "cross-container allocation drill: FAIL"; exit 1
fi
echo "cross-container allocation drill: ALL PASS"
