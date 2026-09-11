#!/usr/bin/env bash
# Build + run the Docker E2E matrix (D55).
#
#   tests/docker_e2e/run.sh                # build (if missing) + run all cells
#   tests/docker_e2e/run.sh --quick        # only already-built images
#   tests/docker_e2e/run.sh --cell 3.12-slim
#
# Every cell prints one "E2E <scenario>: PASS|FAIL" line per scenario and
# a final tally; the script exits non-zero if any deterministic cell has
# a FAIL. Skipped/optional cells (the from-PyPI adopter install needs
# network) are reported but do not fail the run.
set -u

cd "$(dirname "$0")/../.."
REPO=$(pwd)
MIRROR=${GOV_DOCKER_MIRROR:-docker.m.daocloud.io}
PIP_INDEX=${GOV_PIP_INDEX_URL:-https://pypi.org/simple}
IMAGE_PREFIX=${GOV_E2E_IMAGE_PREFIX:-govrail-e2e}
VERSION=$(python3 -c 'import re;print(re.search(r"__version__ = \"([^\"]+)\"", open("gov/version.py").read()).group(1))')
QUICK=0
CELL=""
NIGHTLY=0
for arg in "$@"; do
  case "$arg" in
    --quick) QUICK=1 ;;
    --nightly) NIGHTLY=1; CELL="nightly" ;;
    --cell) CELL="$2"; shift ;;
  esac
done

# --- the artifact under test: the wheel built from the current checkout
mkdir -p dist
rm -f dist/govrail-*.whl   # never let an ancient wheel ride along
python3 -m pip wheel --no-deps -q -w dist/ . || exit 2
echo "== wheel: $(ls dist/govrail-*.whl | xargs -n1 basename)"

# The stamp covers everything an image bakes: the wheel AND the inner
# suite — and it is PER CELL, because one cell's build must never mark
# another cell current: the gbk image derives from 3.12-slim, and a
# global stamp let a stale base hide behind gbk's fresh build.
baked_sha() { { sha256sum dist/govrail-*.whl | cut -d' ' -f1
                sha256sum tests/docker_e2e/inner_e2e.py | cut -d' ' -f1; } \
              | sha256sum | cut -d' ' -f1; }
stamp_path() { echo "tests/docker_e2e/.stamp-$1"; }

built_image_is_current() { # $1 = local tag
  docker image inspect "$IMAGE_PREFIX:$1" >/dev/null 2>&1 || return 1
  # A stale image silently tests an old wheel: the cell's stamp records
  # the baked-content sha, and a mismatch forces the rebuild.
  local sp; sp=$(stamp_path "$1")
  [ -f "$sp" ] && [ "$(cat "$sp")" = "$(baked_sha)" ]
}

build_cell() { # $1 = base repository:tag on the mirror, $2 = local tag
  local base="$1" name="$2"
  if built_image_is_current "$name"; then
    echo "== image $IMAGE_PREFIX:$name already built"; return 0
  fi
  echo "== building $IMAGE_PREFIX:$name from $MIRROR/$base"
  docker build --quiet \
    --build-arg "BASE=$MIRROR/$base" \
    --build-arg "PIP_INDEX_URL=$PIP_INDEX" \
    --build-arg "EXPECTED_VERSION=$VERSION" \
    -f tests/docker_e2e/Dockerfile.e2e -t "$IMAGE_PREFIX:$name" "$REPO" \
    && baked_sha > "$(stamp_path "$name")"
}

build_cell_from() { # $1 = FROM image, $2 = dockerfile, $3 = local tag
  local from="$1" df="$2" name="$3"
  if built_image_is_current "$name"; then
    echo "== image $IMAGE_PREFIX:$name already built"; return 0
  fi
  echo "== building $IMAGE_PREFIX:$name from $from"
  docker build --quiet --build-arg "EXPECTED_VERSION=$VERSION" -f "$df" -t "$IMAGE_PREFIX:$name" "$REPO" \
    && baked_sha > "$(stamp_path "$name")"
}

run_cell() { # $1 = tag; $2 = name; extra docker args via $3...
  local tag="$1"; shift; local name="$1"; shift
  echo "== cell $name"
  local out
  out=$(docker run --rm "$@" "$IMAGE_PREFIX:$tag" 2>&1)
  echo "$out" | sed 's/^/    /'
  if echo "$out" | grep -q "FAIL"; then
    echo "== cell $name: FAIL"; FAILED=1
  else
    echo "== cell $name: PASS"
  fi
}

FAILED=0
# 3.10-bookworm pins the previous-Debian glibc. 3.10-bullseye (one
# OLDER) was attempted and DROPPED: post-EOL, deb.debian.org serves a
# stale security index and archive.debian.org's frozen set is skewed
# against the baked base image — apt closure is broken either way. An
# EOL-suite cell needs a pre-baked image, which is nightly territory,
# not a per-PR cell.
CELLS="3.10-slim 3.11-slim 3.12-slim 3.13-slim 3.12-alpine 3.10-bookworm"
SPECIAL="gbk cross crossdir pypi nightly"
if [ -n "$CELL" ]; then
  case " $SPECIAL " in
    *" $CELL "*) CELLS="" ;;  # dedicated blocks below own this cell
    *) CELLS="$CELL" ;;
  esac
fi
for cell in $CELLS; do
  if [ "$QUICK" = "1" ] && ! built_image_is_current "$cell"; then
    echo "== skip $cell (--quick, image not built or content changed)"; continue
  fi
  case "$cell" in
    3.10-bookworm) base="python:3.10-slim-bookworm" ;;
    3.10-bullseye) base="python:3.10-slim-bullseye" ;;
    *) base="python:$cell" ;;
  esac
  build_cell "$base" "$cell" || { FAILED=1; continue; }
  run_cell "$cell" "$cell"
done

# non-root adopter on one cell: file ownership and permission edges
if [ -z "$CELL" ] || [ "$CELL" = "3.12-slim" ]; then
  docker image inspect "$IMAGE_PREFIX:3.12-slim" >/dev/null 2>&1 && {
    echo "== cell 3.12-slim-nonroot (user 1000)"
    out=$(docker run --rm --user 1000:1000 -w /tmp \
      "$IMAGE_PREFIX:3.12-slim" python /usr/local/bin/inner_e2e.py 2>&1)
    echo "$out" | sed 's/^/    /'
    if echo "$out" | grep -q "FAIL"; then echo "== cell nonroot: FAIL"; FAILED=1
    else echo "== cell nonroot: PASS"; fi
  }
fi

# the hostile-locale cell: zh_CN.GBK baked, every scenario under it
if [ -z "$CELL" ] || [ "$CELL" = "gbk" ]; then
  if [ "$QUICK" = "1" ] && ! built_image_is_current "gbk"; then
    echo "== skip gbk (--quick)"; else
  build_cell "python:3.12-slim" "3.12-slim" || { FAILED=1; }  # gbk derives from it: the base must be current first
  build_cell_from "govrail-e2e:3.12-slim" tests/docker_e2e/Dockerfile.gbk "gbk" \
    || { FAILED=1; }
  if ! [ "$FAILED" = "1" ]; then run_cell "gbk" "gbk-locale"; fi
  fi
fi

# the cross-container drill: two REAL containers, one shared repository
if [ -z "$CELL" ] || [ "$CELL" = "cross" ]; then
  build_cell "python:3.12-slim" "3.12-slim" || { FAILED=1; }
  echo "== cell cross-container drill"
  out=$(bash tests/docker_e2e/cross_container_drill.sh "$IMAGE_PREFIX:3.12-slim" 2>&1)
  echo "$out" | sed 's/^/    /'
  if echo "$out" | grep -q "FAIL"; then echo "== cell cross: FAIL"; FAILED=1
  else echo "== cell cross: PASS"; fi
fi

# the cross-container dir-format drill: collision -> renumber -> absorb
if [ -z "$CELL" ] || [ "$CELL" = "crossdir" ]; then
  build_cell "python:3.12-slim" "3.12-slim" || { FAILED=1; }
  echo "== cell cross-container dir drill"
  out=$(bash tests/docker_e2e/cross_dir_drill.sh "$IMAGE_PREFIX:3.12-slim" 2>&1)
  echo "$out" | sed 's/^/    /'
  if echo "$out" | grep -q "FAIL"; then echo "== cell crossdir: FAIL"; FAILED=1
  else echo "== cell crossdir: PASS"; fi
fi

# the nightly scale tier: 10,000 files, one cell, explicit opt-in
if [ "$NIGHTLY" = "1" ] || [ "$CELL" = "nightly" ]; then
  build_cell "python:3.12-slim" "3.12-slim" || { FAILED=1; }
  echo "== cell nightly (10k files; GOV_E2E_NIGHTLY=1)"
  out=$(docker run --rm -e GOV_E2E_NIGHTLY=1     "$IMAGE_PREFIX:3.12-slim" python /usr/local/bin/inner_e2e.py perf_night 2>&1)
  echo "$out" | sed 's/^/    /'
  if echo "$out" | grep -q "FAIL"; then echo "== cell nightly: FAIL"; FAILED=1
  else echo "== cell nightly: PASS"; fi
fi

# the adopter-from-PyPI cell: real network, real published wheel.
# Optional — a mirror outage reports SKIP, never a red run.
if [ -z "$CELL" ] || [ "$CELL" = "pypi" ]; then
  echo "== cell pypi-adopter (network; SKIP on outage)"
  out=$(docker run --rm -e PIP_INDEX_URL="$PIP_INDEX" \
    "$MIRROR/library/python:3.12-slim" bash -lc "
      pip install -q \"govrail==$VERSION\" && \
      gov --version | grep -q '$VERSION' && \
      echo E2E pypi-adopter: PASS" 2>&1)
  echo "$out" | sed 's/^/    /'
  if echo "$out" | grep -q "PASS"; then echo "== cell pypi-adopter: PASS"
  else echo "== cell pypi-adopter: SKIP (network/index unavailable)"; fi
fi

if [ "$FAILED" = "1" ]; then
  echo "docker e2e matrix: FAIL"; exit 1
fi
echo "docker e2e matrix: ALL PASS (deterministic cells)"
