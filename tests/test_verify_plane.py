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
