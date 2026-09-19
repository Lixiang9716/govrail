"""The plane seal: the constitution is tamper-evident (D2's fix).

A sealed config that moves without an explicit re-baseline must go red,
naming the file — including the DELETION case the archive seal used to
miss. An apply-shaped flow may extend an intact chain but never launder
accumulated drift.
"""
from __future__ import annotations

import json

import pytest

from gov import verify_plane


def _init_plane(tmp_path):
    (tmp_path / ".gov").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".gov" / "rules.md").write_text("# rules v1\n", encoding="utf-8")
    (tmp_path / "gates.json").write_text('{"gates": []}\n', encoding="utf-8")
    verify_plane.baseline(tmp_path)


def test_sealed_plane_is_green(tmp_path):
    _init_plane(tmp_path)
    assert verify_plane.violations(tmp_path) == []


def test_edited_rule_is_drift(tmp_path):
    _init_plane(tmp_path)
    (tmp_path / ".gov" / "rules.md").write_text("# rules TAMPERED\n",
                                                encoding="utf-8")
    drift = verify_plane.violations(tmp_path)
    assert any("rules.md" in d and "differs" in d for d in drift)


def test_deleted_gate_config_is_drift(tmp_path):
    """The M2 lesson, applied to the plane: deletions are the loudest
    drift and must never read as 'nothing to check'."""
    _init_plane(tmp_path)
    (tmp_path / "gates.json").unlink()
    drift = verify_plane.violations(tmp_path)
    assert any("gates.json" in d and "gone" in d for d in drift)


def test_new_unsealed_config_is_named(tmp_path):
    _init_plane(tmp_path)
    (tmp_path / ".gov" / "pairing.json").write_text("{}\n", encoding="utf-8")
    drift = verify_plane.violations(tmp_path)
    assert any("pairing.json" in d and "not sealed" in d for d in drift)


def test_write_extends_an_intact_chain(tmp_path):
    _init_plane(tmp_path)
    (tmp_path / ".gov" / "pairing.json").write_text("{}\n", encoding="utf-8")
    verify_plane.baseline(tmp_path)  # what `--write` does
    assert verify_plane.violations(tmp_path) == []
    seal = json.loads((tmp_path / ".gov" / "plane-seal.json")
                      .read_text(encoding="utf-8"))
    assert ".gov/pairing.json" in seal["files"]


def test_tampered_seal_is_unreadable_prerequisite(tmp_path):
    _init_plane(tmp_path)
    seal = tmp_path / ".gov" / "plane-seal.json"
    seal.write_text("{not json", encoding="utf-8")
    drift = verify_plane.violations(tmp_path)
    assert drift and "cannot read" in drift[0]


def test_run_precheck_catches_drift_despite_disabled_plane_gate(tmp_path, monkeypatch, capsys):
    """The reflexive gap (N1): the in-DAG plane gate lives inside the
    sealed file, so tampering that disables its own detector must STILL
    be caught — the out-of-band precheck reads the seal and the config
    bytes without trusting anything from gates.json."""
    from gov import gates as gates_mod
    _init_plane(tmp_path)
    monkeypatch.chdir(tmp_path)
    cfg = json.loads((tmp_path / "gates.json").read_text(encoding="utf-8"))
    for g in cfg["gates"]:
        g["enabled"] = False  # silence the in-DAG detector
    (tmp_path / "gates.json").write_text(json.dumps(cfg), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        gates_mod._plane_precheck()
    assert exc.value.code == 1
    assert "drifted from its seal" in capsys.readouterr().err


def test_run_precheck_quiet_on_intact_plane(tmp_path, monkeypatch):
    from gov import gates as gates_mod
    _init_plane(tmp_path)
    monkeypatch.chdir(tmp_path)
    gates_mod._plane_precheck()  # no SystemExit


def test_run_precheck_refuses_unsealed_plane(tmp_path, monkeypatch, capsys):
    """N2: deleting the seal file is the same attack as disabling the
    gate, one level up. The discriminator is the constitution: a
    governed project (rules.md present) never sits in "constitution
    without seal" — that state refuses with the one-command remedy."""
    from gov import gates as gates_mod
    (tmp_path / ".gov").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".gov" / "rules.md").write_text("# rules\n", encoding="utf-8")
    (tmp_path / "gates.json").write_text('{"gates": []}\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc:
        gates_mod._plane_precheck()
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "seal is GONE" in err and "verify-plane --write" in err


def test_run_precheck_noop_for_bare_configs(tmp_path, monkeypatch):
    """A bare gates.json (scratch configs, tests, tools that never
    adopted the plane) has no constitution and no seal — nothing to
    judge, and `gov run` must keep working on it."""
    from gov import gates as gates_mod
    (tmp_path / "gates.json").write_text('{"gates": []}\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    gates_mod._plane_precheck()  # no SystemExit


def test_write_refused_without_terminal_and_recorded_with_consent(
        tmp_path, monkeypatch, capsys):
    """N3: --write is a recorded ritual. Without a terminal it refuses;
    with --confirm-unattended it lands, and the receipt (caller, mode,
    diff) is printed and recorded INSIDE the seal."""
    import io as _io
    import json as _json
    from gov import verify_plane as vp
    _init_plane(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", _io.StringIO())  # not a tty
    monkeypatch.setenv("GOV_CALLER", "agent-7")
    (tmp_path / ".gov" / "pairing.json").write_text("{}\n", encoding="utf-8")

    # bare --write without a terminal: refused (exit 2), nothing landed
    assert vp.main(["--write"]) == 2
    assert "UNATTENDED" in capsys.readouterr().err
    seal = _json.loads((tmp_path / ".gov" / "plane-seal.json")
                       .read_text(encoding="utf-8"))
    assert ".gov/pairing.json" not in seal["files"]

    # --confirm-unattended: recorded as machine consent under the caller
    capsys.readouterr()
    vp.main(["--write", "--confirm-unattended", "--reason", "test: reviewed re-baseline"])
    out = capsys.readouterr().out
    assert "+ .gov/pairing.json:" in out
    assert "UNATTENDED machine consent" in out and "agent-7" in out
    seal = _json.loads((tmp_path / ".gov" / "plane-seal.json")
                       .read_text(encoding="utf-8"))
    assert seal["last_rebaseline"]["caller"] == "agent-7"
    assert seal["last_rebaseline"]["unattended"] is True


def test_seal_covers_governance_behavior_files(tmp_path):
    """N4: decisions.json / surfaces.json / .gov/rejections/** change
    governance behavior — present means sealed, gone means named."""
    (tmp_path / ".gov").mkdir(parents=True)
    (tmp_path / ".gov" / "rules.md").write_text("# rules\n", encoding="utf-8")
    (tmp_path / "gates.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".gov" / "decisions.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / ".gov" / "rejections").mkdir()
    (tmp_path / ".gov" / "rejections" / "case-x.sh").write_text(
        "#!/bin/sh\nexit 0\n", encoding="utf-8")
    verify_plane.baseline(tmp_path)
    # a rejection case goes missing: named, never silent
    (tmp_path / ".gov" / "rejections" / "case-x.sh").unlink()
    drift = verify_plane.violations(tmp_path)
    assert any("case-x.sh" in d and "gone" in d for d in drift)


def test_non_object_seal_is_unreadable_not_a_crash(tmp_path):
    """A legal-JSON-but-not-a-seal file (`[]`, `42`, non-object "files")
    is a named unreadable-seal prerequisite, never an AttributeError."""
    _init_plane(tmp_path)
    seal = tmp_path / ".gov" / "plane-seal.json"
    for bad in ("[]", "42", '{"files": []}'):
        seal.write_text(bad, encoding="utf-8")
        drift = verify_plane.violations(tmp_path)
        assert drift and "cannot read" in drift[0]


def test_non_object_seal_main_exits_2(tmp_path, monkeypatch):
    _init_plane(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".gov" / "plane-seal.json").write_text("42", encoding="utf-8")
    assert verify_plane.main([]) == 2


def test_stripped_sealed_files_with_surviving_plane_is_drift(tmp_path, monkeypatch):
    """The `if not files` short-circuit must not preempt violations():
    deleting every sealed file while .gov/manifest.json survives is N2/N7
    drift (exit 1), not a green 'no plane config found'."""
    _init_plane(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".gov" / "manifest.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / ".gov" / "rules.md").unlink()
    (tmp_path / "gates.json").unlink()
    (tmp_path / ".gov" / "plane-seal.json").unlink()
    assert verify_plane.main([]) == 1


def test_write_warns_when_previous_seal_unreadable(tmp_path, monkeypatch, capsys):
    """#4: --write over an unreadable previous seal continues (explicit
    consent) but the swallow is loud, never silent."""
    import io as _io
    _init_plane(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", _io.StringIO())  # not a tty
    monkeypatch.setenv("GOV_CALLER", "agent-8")
    (tmp_path / ".gov" / "plane-seal.json").write_text("[]", encoding="utf-8")
    assert verify_plane.main(["--write", "--confirm-unattended", "--reason", "test: reviewed re-baseline"]) == 0
    assert "WARNING" in capsys.readouterr().err
    seal = json.loads((tmp_path / ".gov" / "plane-seal.json")
                      .read_text(encoding="utf-8"))
    assert ".gov/rules.md" in seal["files"]  # the re-baseline still landed


def test_rebaseline_names_the_consent_ledger(tmp_path, monkeypatch, capsys):
    """#200: the consent record must be auditable — the output says
    where it lives instead of leaving the operator to find it."""
    from gov import verify_plane as vp
    (tmp_path / ".gov").mkdir(parents=True)
    (tmp_path / "gates.json").write_text("{}", encoding="utf-8")
    import subprocess
    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)
    (tmp_path / ".gov" / "rituals.jsonl").write_text("", encoding="utf-8")
    # anchor_to_git_root climbs from cwd: without this chdir the in-process
    # --write re-baselines the LIVE plane mid-suite (real ledger lines).
    monkeypatch.chdir(tmp_path)
    rc = vp.main(["--write", "--confirm-unattended", "--reason", "test: reviewed re-baseline"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "consent recorded in" in out and "rituals.jsonl" in out
