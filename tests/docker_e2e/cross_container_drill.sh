#!/usr/bin/env bash
# The cross-container drill (D58, batch 2): two REAL containers sharing
# ONE repository — the same clone bind-mounted into both — doing the two
# things the plane promises parallel agents can survive.
#
#   1. decision collision — both agents allocate D2 from the same base
#      and push to their own refs; the verify-decisions --base net must
#      name the collision loudly at gate time (D40).
#   2. lease contention across containers — agent A's lease (TTL) blocks
#      agent B (exit 3), then expires and B takes over (D52). The lease
#      lives in the git COMMON dir (D52's exact sharing domain), which
#      the shared clone mount makes common by construction.
#
# Why one shared clone (not two clones): D52's leases span the worktrees
# OF ONE CLONE — separate clones have separate lock domains by design,
# and the plane's parallel model is worktree-per-agent over a shared
# common dir. Two containers mounting the same clone is that model with
# a container boundary drawn through it.
#
# Usage: cross_container_drill.sh [image]   (default govrail-e2e:3.12-slim)
# Prints E2E lines; exits non-zero on any failure.
set -u

IMAGE=${1:-govrail-e2e:3.12-slim}
WORK=$(mktemp -d /tmp/gov-cross-XXXXXX)
FAILED=0

cleanup() {
  docker rm -f "$NA" "$NB" >/dev/null 2>&1
  # the drill's files are root-owned (written inside containers); the
  # host user cannot rm them — let the image's root do it
  docker run --rm -v "$WORK":/work "$IMAGE" \
    bash -c 'rm -rf /work/.[!.]* /work/*' >/dev/null 2>&1
  rm -rf "$WORK"
}
trap cleanup EXIT

report() { # $1 = scenario, $2 = ok|fail, $3 = detail
  if [ "$2" = "ok" ]; then echo "E2E $1: PASS"
  else echo "E2E $1: FAIL — $3"; FAILED=1; fi
}

# --- origin (bare) + ONE clone that both containers will share ---------
git init -q --bare -b main "$WORK/origin.git"  # HEAD must name the pushed branch, or clones are born empty
git init -q "$WORK/seed"
cd "$WORK/seed"
git config user.email t@t; git config user.name t
mkdir docs
printf '## D1 — adopt\n\n- **选项**：gov init\n\n- **状态**：已决\n' > docs/decisions.md
printf '# demo\n' > README.md
git add -A
git -c commit.gpgsign=false commit -qm seed
git push -q "$WORK/origin.git" HEAD:refs/heads/main
git clone -q "$WORK/origin.git" "$WORK/shared"

# --- two containers, one clone ------------------------------------------
# /work is the SHARED clone; /origin is the bare remote so pushes from
# inside a container can reach it (the clone's remote URL is a host
# path no container can see, rewritten below).
NA=$(docker run -d --rm -v "$WORK/shared":/work -v "$WORK/origin.git":/origin \
  "$IMAGE" sleep infinity) || { echo "cannot start agent A"; exit 2; }
NB=$(docker run -d --rm -v "$WORK/shared":/work -v "$WORK/origin.git":/origin \
  "$IMAGE" sleep infinity) || { echo "cannot start agent B"; docker rm -f "$NA" >/dev/null; exit 2; }
# root in the containers owns nothing on the host side, so git's
# ownership guard is disarmed first.
docker exec "$NA" git config --global --add safe.directory '*'
docker exec "$NB" git config --global --add safe.directory '*'
docker exec "$NA" bash -c 'git config --global user.email t@t && git config --global user.name a'
docker exec "$NB" bash -c 'git config --global user.email t@t && git config --global user.name b'
# set-url must run INSIDE the clone: git remote is per-repository state
docker exec "$NA" bash -c 'cd /work && git remote set-url origin /origin'
docker exec "$NB" bash -c 'cd /work && git remote set-url origin /origin'

# --- drill 1: both agents allocate D2 from the same base ---------------
docker exec "$NA" bash -c 'cd /work && printf "## D2 — agent a plan\n\n- **选项**：a\n\n- **状态**：已决\n" >> docs/decisions.md && git add -A && git -c commit.gpgsign=false commit -qm "a allocates D2" && git push -q origin HEAD:refs/heads/agent-a' \
  && report decision_a_push ok || report decision_a_push fail "agent a could not push its D2"
docker exec "$NB" bash -c 'cd /work && printf "## D2 — agent b plan\n\n- **选项**：b\n\n- **状态**：已决\n" >> docs/decisions.md && git add -A && git -c commit.gpgsign=false commit -qm "b allocates D2" && git push -q origin HEAD:refs/heads/agent-b' \
  && report decision_b_push ok || report decision_b_push fail "agent b could not push its D2"
# the net: agent a fetches agent b's branch and runs the gate against it
docker exec "$NA" bash -c 'cd /work && git fetch -q origin agent-b && ! gov verify-decisions --base origin/agent-b > /tmp/vd.txt 2>&1'
VD=$(docker exec "$NA" cat /tmp/vd.txt)
# The gate names D2 either way: "number collision" when the base's D2
# is new to the local series, "duplicate decision entry" when both sides
# already landed it (this drill's shape — the union sees D2 twice).
if echo "$VD" | grep -q "D2" && echo "$VD" | grep -qiE "collision|duplicate"; then
  report decision_collision_named ok
else
  report decision_collision_named fail "the gate did not name the D2 collision: $VD"
fi

# --- drill 2: lease contention across containers ------------------------
# A takes a 4s lease; B is busy; A never releases; the lease expires and
# B takes it over — all state crossing the container boundary through
# the shared git common dir.
docker exec "$NA" bash -c 'cd /work && gov acquire shared/drill --agent A --ttl 4' >/dev/null 2>&1 \
  && report lease_a_acquires ok || report lease_a_acquires fail "A could not acquire"
docker exec "$NB" bash -c 'cd /work && gov acquire shared/drill --agent B --ttl 4' >/dev/null 2>&1
rc_busy=$?
if [ "$rc_busy" = "3" ]; then report lease_b_busy ok
else report lease_b_busy fail "expected exit 3 (busy) while A held the lease, got $rc_busy"; fi
sleep 4.3
takeover=$(docker exec "$NB" bash -c 'cd /work && gov acquire shared/drill --agent B' 2>&1)
if [ $? -eq 0 ]; then report lease_b_takeover ok
else report lease_b_takeover fail "B could not take over after TTL: $takeover"; fi
docker exec "$NB" bash -c 'cd /work && gov release shared/drill --agent B' >/dev/null 2>&1 \
  && report lease_b_releases ok || report lease_b_releases fail "B could not release"

if [ "$FAILED" = "1" ]; then
  echo "cross-container drill: FAIL"; exit 1
fi
echo "cross-container drill: ALL PASS"
