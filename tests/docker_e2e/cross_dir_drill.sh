#!/usr/bin/env bash
# The dir-format cross-container drill (D58, batch 4): two REAL
# containers, two SEPARATE clones of one origin — the exact layout D40's
# collision net exists for. The decisions source is `dir` format (one
# file per decision), whose claim is: appends are STRUCTURALLY
# conflict-free (no textual merge to resolve), while the numbering net
# still catches a double allocation — and once one agent renumbers
# against the other, the appends are absorbed with no cleanup drama.
#
#   1. both agents allocate D2 from the same base and push their own
#      refs (each `decision add` creates its own file — no git conflict);
#   2. agent A fetches agent B: verify-decisions --base goes red naming
#      the D2 number collision;
#   3. agent B renumbers against agent A (next --base, explicit --id),
#      pushes again;
#   4. verify-decisions --base turns GREEN — both appends absorbed.
#
# (The lease-sharing property is drilled separately in
# cross_container_drill.sh — leases need the SHARED common dir; decision
# collisions live in REPO HISTORY and need separate branches. Different
# mechanisms, different topologies — that is the point of having both.)
#
# Usage: cross_dir_drill.sh [image]
set -u

IMAGE=${1:-govrail-e2e:3.12-slim}
WORK=$(mktemp -d /tmp/gov-crossdir-XXXXXX)
FAILED=0

cleanup() {
  docker rm -f "$NA" "$NB" >/dev/null 2>&1
  # pushes wrote root-owned objects into the host-side clones; the image
  # root hands ownership back before the host rm
  docker run --rm -v "$WORK":/work "$IMAGE" \
    chown -R "$(id -u):$(id -g)" /work >/dev/null 2>&1
  rm -rf "$WORK"
}
trap cleanup EXIT

report() {
  if [ "$2" = "ok" ]; then echo "E2E $1: PASS"
  else echo "E2E $1: FAIL — $3"; FAILED=1; fi
}

# --- origin + one clone per agent (host-side, bind-mounted) -------------
git init -q --bare -b main "$WORK/origin.git"
git init -q "$WORK/seed"
cd "$WORK/seed"
git config user.email t@t; git config user.name t
mkdir -p docs/decisions .gov
printf '## D1 — adopt\n\n- **选项**：gov init\n\n- **状态**：已决\n' \
  > docs/decisions/D1-adopt.md
printf '{"path": "docs/decisions", "format": "dir"}' > .gov/decisions.json
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

# --- both agents allocate D2 from the same base -------------------------
docker exec "$NA" bash -c 'cd /work && printf "agent a plan\n\n- **选项**：a\n\n- **状态**：已决\n" > /tmp/d2.md && gov decision add --from /tmp/d2.md && git add -A && git -c commit.gpgsign=false commit -qm "a allocates D2" && git push -q origin agent-a' \
  && report dir_a_adds_D2 ok || report dir_a_adds_D2 fail "agent a could not add+push D2"
docker exec "$NB" bash -c 'cd /work && printf "agent b plan\n\n- **选项**：b\n\n- **状态**：已决\n" > /tmp/d2.md && gov decision add --from /tmp/d2.md && git add -A && git -c commit.gpgsign=false commit -qm "b allocates D2" && git push -q origin agent-b' \
  && report dir_b_adds_own_file ok || report dir_b_adds_own_file fail "agent b could not add+push its own D2 file (no git conflict — structural freedom)"

# --- the net: agent a runs the gate against agent b's branch ------------
VD=$(docker exec "$NA" bash -c 'cd /work && git fetch -q origin agent-b && gov verify-decisions --base origin/agent-b 2>&1')
if [ $? -ne 0 ] && echo "$VD" | grep -q "D2"; then
  report dir_collision_named ok
else
  report dir_collision_named fail "the gate did not name the D2 collision: $VD"
fi

# --- absorption: agent b renumbers against agent a ----------------------
# The refusal message prescribes the flow: "pre-partitioning across
# branches needs every sibling to land" — merge the sibling FIRST (its
# D2 file arrives), THEN renumber own D2 to D3 with no local gap.
docker exec "$NB" bash -c 'cd /work && git fetch -q origin agent-a && git merge -q --no-edit origin/agent-a && rm docs/decisions/D2-agent-b-plan.md && printf "agent b plan\n\n- **选项**：b\n\n- **状态**：已决\n" > /tmp/d3.md && gov decision add --from /tmp/d3.md --id D3 && git add -A && git -c commit.gpgsign=false commit -qm "b renumbers to D3" && git push -q origin agent-b' \
  && report dir_b_renumbers ok || report dir_b_renumbers fail "agent b could not renumber against agent a"
VD=$(docker exec "$NA" bash -c 'cd /work && git fetch -q origin agent-b && gov verify-decisions --base origin/agent-b 2>&1')
if [ $? -eq 0 ]; then report dir_absorbed ok
else report dir_absorbed fail "the renumbered dir appends did not absorb: $VD"; fi

if [ "$FAILED" = "1" ]; then
  echo "cross-container dir drill: FAIL"; exit 1
fi
echo "cross-container dir drill: ALL PASS"
