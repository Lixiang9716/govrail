"""`gov update` — the one deliberate migration step (D58).

The dsh-mobile migration was rehearsed by hand (adopt → seal → pin →
ignore), and #259 asked for it as a command. These tests pin the
choreography: dry run by default changes NOTHING; --apply adopts only
the safe files, merges additive gates, refreshes the CI pin, re-seals
behind consent, and aligns the manifest; customized content is never
touched; and the preconditions (clean tree, initialized plane,
unattended consent) fail loud before any mutation.
"""
from __future__ import annotations

import json
import os
import subprocess

import pytest
import sys
from pathlib import Path

from gov import plane
from gov.version import __version__

PASS = [sys.executable, "-c", "pass"]

REPO = Path(__file__).resolve().parent.parent


def _repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path,
                   check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path,
                   check=True)


def _commit(tmp_path: Path, msg: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "commit", "-qm", msg],
        cwd=tmp_path, check=True)


def _fingerprint(root: Path) -> dict[Path, bytes]:
    """Every file EXCEPT .git/** — git refreshes its index as a side
    effect of read-only status calls, and the fingerprint is about the
    plane's state, not git's bookkeeping."""
    return {p: p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file() and ".git" not in p.parts}


def _invoke(argv: list[str], cwd: Path, *,
            consent: bool = False) -> int:
    """DEVNULL stdin: the consent preflight keys on isatty, and a CI
    runner may hand the subprocess a console — the test states its
    consent explicitly instead of depending on the host's stdin."""
    env = {**os.environ, "PYTHONPATH": str(REPO), "PYTHONUTF8": "1"}
    argv = argv + (["--confirm-unattended"] if consent else [])
    return subprocess.run(
        [sys.executable, "-m", "gov", *argv], cwd=cwd, check=False,
        stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=300, env=env,
        encoding="utf-8", errors="replace").returncode


def _setup(tmp_path: Path, *, old_pin: bool = True) -> None:
    _repo(tmp_path)
    assert plane.init(tmp_path, ci=True) == 0  # --ci generates the pinned workflow
    if old_pin:
        wf = tmp_path / ".github" / "workflows" / "gov.yml"
        text = wf.read_text(encoding="utf-8")
        wf.write_text(
            text.replace("__GOV_VERSION__", "0.1.2"), encoding="utf-8")
    manifest = tmp_path / ".gov" / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["version"] = "0.1.2"
    manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    _commit(tmp_path, "plane at 0.1.2")


def test_dry_run_changes_nothing(tmp_path):
    _setup(tmp_path)
    before = _fingerprint(tmp_path)
    assert _invoke(["update"], tmp_path, consent=True) == 0
    after = _fingerprint(tmp_path)
    assert before == after, "a dry run must not touch a byte"


def test_apply_migrates_end_to_end(tmp_path):
    _setup(tmp_path)
    assert _invoke(["update", "--apply", "--confirm-unattended"],
                   tmp_path, consent=True) == 0
    manifest = json.loads(
        (tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == __version__
    wf = (tmp_path / ".github" / "workflows" / "gov.yml").read_text(
        encoding="utf-8")
    assert f"pip install govrail=={__version__}" in wf
    gitignore = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert ".gov/history/" in gitignore
    assert (tmp_path / ".gov" / "plane-seal.json").is_file()
    assert (tmp_path / ".gov" / "rituals.jsonl").is_file()


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows reports the NUL device as a TTY, so the refusal's "
           "isatty preflight cannot be driven deterministically from a "
           "test; the POSIX jobs and the shared verify-plane consent "
           "semantics carry the coverage")
def test_apply_refuses_without_consent(tmp_path):
    """Non-interactive shell + no flag: the seal re-baseline is
    constitution acceptance — it refuses BEFORE touching anything."""
    _setup(tmp_path)
    before = _fingerprint(tmp_path)
    assert _invoke(["update", "--apply"], tmp_path, consent=False) == 2
    after = _fingerprint(tmp_path)
    assert before == after


def test_refuses_a_dirty_worktree(tmp_path):
    _setup(tmp_path)
    (tmp_path / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
    subprocess.run(["git", "add", "dirty.txt"], cwd=tmp_path, check=True)
    assert _invoke(["update", "--apply", "--confirm-unattended"],
                   tmp_path, consent=True) == 2
    err = subprocess.run(
        [sys.executable, "-m", "gov", "update", "--apply",
         "--confirm-unattended"], cwd=tmp_path, capture_output=True,
        text=True, encoding="utf-8", errors="replace").stderr
    assert "reviewable in isolation" in err


def test_refuses_an_uninitialized_project(tmp_path):
    _repo(tmp_path)
    assert _invoke(["update", "--apply", "--confirm-unattended"],
                   tmp_path) == 2


def test_custom_gates_survive_the_merge(tmp_path):
    """adopt-new is additive by id: the project's own gates survive, the
    newly shipped ones land, and the seal covers the merged file."""
    _setup(tmp_path)
    gates = tmp_path / "gates.json"
    cfg = json.loads(gates.read_text(encoding="utf-8"))
    cfg["gates"].append({"id": "mine", "command": PASS})
    gates.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    _commit(tmp_path, "custom gate")
    assert _invoke(["update", "--apply", "--confirm-unattended"],
                   tmp_path, consent=True) == 0
    merged = json.loads(gates.read_text(encoding="utf-8"))
    ids = {g["id"] for g in merged["gates"]}
    assert "mine" in ids and "plane" in ids  # custom + shipped coexist
    assert (tmp_path / ".gov" / "plane-seal.json").is_file()




import os as _os


POSIX_EXEC = pytest.mark.skipif(
    _os.name == "nt",
    reason="no POSIX mode bits on Windows: the exec-bit assertion "
           "tests a POSIX contract (init/update chmod 0o755 there)")


@POSIX_EXEC
def test_rewire_executed_hooks_copies_bytes_and_keeps_mode(tmp_path,
                                                            monkeypatch):
    """#331: adoption refreshed .gov/hooks/<name> while the executed copy
    kept running the OLD body — deprecation noise today, dead command
    spellings the day the aliases go. (The resolver reads the PROCESS
    cwd, so the test must chdir — the first draft rewrote this very
    repository's own hook.)"""
    from gov import update as update_mod
    _repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    tracked = tmp_path / ".gov" / "hooks"
    tracked.mkdir(parents=True)
    (tracked / "pre-commit").write_text(
        "#!/bin/sh\n# govrail: current\nrun_gov hooks pre-commit\n",
        encoding="utf-8")
    (hooks / "pre-commit").write_text(
        "#!/bin/sh\n# govrail: old\nrun_gov verify-pairing --staged\n",
        encoding="utf-8")
    assert update_mod._rewire_executed_hooks(tmp_path) == 1
    assert (hooks / "pre-commit").read_bytes() == \
        (tracked / "pre-commit").read_bytes()
    assert (hooks / "pre-commit").stat().st_mode & 0o111  # still executable
    # a second run is a no-op (bytes already equal)
    assert update_mod._rewire_executed_hooks(tmp_path) == 0


def test_rewire_executed_hooks_copies_bytes_on_every_platform(tmp_path,
                                                              monkeypatch):
    """The bytes contract is platform-free (the exec BIT is not, above):
    a shim on Windows has no 0o755 to preserve, but it must be the
    tracked revision, not the stale one."""
    from gov import update as update_mod
    _repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    tracked = tmp_path / ".gov" / "hooks"
    tracked.mkdir(parents=True)
    (tracked / "pre-commit").write_text(
        "#!/bin/sh\n# govrail: current\nrun_gov hooks pre-commit\n",
        encoding="utf-8")
    (hooks / "pre-commit").write_text(
        "#!/bin/sh\n# govrail: old\nrun_gov verify-pairing --staged\n",
        encoding="utf-8")
    assert update_mod._rewire_executed_hooks(tmp_path) == 1
    assert (hooks / "pre-commit").read_bytes() == \
        (tracked / "pre-commit").read_bytes()


def test_rewire_leaves_a_foreign_hook_alone(tmp_path, monkeypatch):
    from gov import update as update_mod
    _repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    tracked = tmp_path / ".gov" / "hooks"
    tracked.mkdir(parents=True)
    (tracked / "pre-commit").write_text("# govrail: ours\n", encoding="utf-8")
    (hooks / "pre-commit").write_text("#!/bin/sh\necho mine\n",
                                      encoding="utf-8")
    assert update_mod._rewire_executed_hooks(tmp_path) == 0
    assert "echo mine" in (hooks / "pre-commit").read_text(encoding="utf-8")


def test_doctor_names_executed_hook_drift(tmp_path, monkeypatch, capsys):
    """The doctor half of #331: executed vs tracked byte drift is named
    with the one-line fix."""
    from gov import doctor
    _repo(tmp_path)
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    tracked = tmp_path / ".gov" / "hooks"
    tracked.mkdir(parents=True)
    body = "#!/bin/sh\n# govrail: hook\nrun_gov hooks pre-push\n"
    (tracked / "pre-push").write_text(body, encoding="utf-8")
    (hooks / "pre-push").write_text(body, encoding="utf-8")
    for p in (tracked / "pre-push", hooks / "pre-push"):
        p.chmod(0o755)   # doctor's executability check is separate from drift
    monkeypatch.chdir(tmp_path)
    assert doctor.main(["--json"]) == 0
    import json as _json
    record = _json.loads(capsys.readouterr().out)
    names = {c["name"] for c in record["checks"]}
    assert "hook-sync:pre-push" not in names      # in sync: no note
    (hooks / "pre-push").write_text(body + "# stale\n", encoding="utf-8")
    assert doctor.main(["--json"]) == 0
    record = _json.loads(capsys.readouterr().out)
    drift = [c for c in record["checks"] if c["name"] == "hook-sync:pre-push"]
    assert drift and "differs from" in drift[0]["detail"]
