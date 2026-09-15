"""The plane seal: the constitution is tamper-evident (D2's fix).

A sealed config that moves without an explicit re-baseline must go red,
naming the file — including the DELETION case the archive seal used to
miss. An apply-shaped flow may extend an intact chain but never launder
accumulated drift.
"""
from __future__ import annotations

import json

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
