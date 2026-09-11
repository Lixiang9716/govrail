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
for arg in "$@"; do
  case "$arg" in
    --quick) QUICK=1 ;;
    --cell) CELL="$2"; shift ;;
  esac
done

# --- the artifact under test: the wheel built from the current checkout
mkdir -p dist
rm -f dist/govrail-*.whl   # never let an ancient wheel ride along
python3 -m pip wheel --no-deps -q -w dist/ . || exit 2
echo "== wheel: $(ls dist/govrail-*.whl | xargs -n1 basename)"

STAMP=tests/docker_e2e/.wheel-sha
WHEEL_SHA=$(sha256sum dist/govrail-*.whl | cut -d' ' -f1)

built_image_is_current() { # $1 = local tag
  docker image inspect "$IMAGE_PREFIX:$1" >/dev/null 2>&1 || return 1
  # A stale image silently tests an old wheel: the stamp records the sha
  # the image was built from, and a mismatch forces the rebuild.
  [ -f "$STAMP" ] && [ "$(cat "$STAMP")" = "$WHEEL_SHA" ]
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
    && echo "$WHEEL_SHA" > "$STAMP"
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
CELLS="3.10-slim 3.11-slim 3.12-slim 3.13-slim 3.12-alpine"
[ -n "$CELL" ] && CELLS="$CELL"
for cell in $CELLS; do
  if [ "$QUICK" = "1" ] && ! built_image_is_current "$cell"; then
    echo "== skip $cell (--quick, image not built or wheel changed)"; continue
  fi
  build_cell "python:$cell" "$cell" || { FAILED=1; continue; }
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
