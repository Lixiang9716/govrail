"""The Docker E2E matrix, wired into the regression suite (D58).

Opt-in by design: a matrix run builds images and takes minutes, which is
a deliberate act. Set GOV_DOCKER_E2E=1 to include it (CI: one env var on
the ubuntu job, which has Docker); without it the suite SKIPS, loudly
naming why — never silently passing.
"""
import os
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
RUN_SH = HERE / "docker_e2e" / "run.sh"


def _docker_ready() -> bool:
    try:
        r = subprocess.run(["docker", "info", "--format", "ok"],
                           capture_output=True, text=True, timeout=30)
        return r.returncode == 0 and "ok" in r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return False


@pytest.mark.skipif(os.environ.get("GOV_DOCKER_E2E") != "1",
                    reason="set GOV_DOCKER_E2E=1 to run the Docker matrix "
                           "(builds images; minutes, not seconds)")
@pytest.mark.skipif(not _docker_ready(),
                    reason="GOV_DOCKER_E2E=1 but the Docker daemon is "
                           "unreachable")
def test_docker_e2e_matrix():
    """Every deterministic cell (Python 3.10-3.13 + musl + non-root)
    must report ALL PASS; the network PyPI cell is allowed to SKIP but
    never to FAIL."""
    r = subprocess.run(["bash", str(RUN_SH)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       timeout=3600)
    assert r.returncode == 0, (
        "the Docker E2E matrix went red:\n"
        f"--- stdout\n{r.stdout}\n--- stderr\n{r.stderr}")
    assert "ALL PASS" in r.stdout
    assert "FAIL" not in r.stdout.replace(
        "never to FAIL", "").replace("FAILs", ""), \
        "a FAIL marker leaked into a green run"
