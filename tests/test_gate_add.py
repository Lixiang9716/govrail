"""`gov gate add` — the wiring surface for a project's own gates (#309),
and its PREVIEW path (#366).

The issue: reporting the exact wiring command in a PR body, or confirming
it, meant running the command for real — which writes gates.json, and in a
governed repo that file is sealed, so confirming a proposal cost a
recorded re-baseline ritual. These tests pin the fix: a dry run that
validates everything the real run validates and writes nothing, a help
surface that documents its own grammar (the trailing '-- <command>' was
in a source comment only), and an explicit separator for callers that
cannot emit a bare '--' positionally.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gov import gate


@pytest.fixture()
def project(tmp_path, monkeypatch):
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "gates.json").write_text(json.dumps(
        {"gates": [], "modes": {"all": []}, "defaultMode": "all"},
        indent=2) + "\n", encoding="utf-8")
    (tmp_path / ".gov").mkdir(exist_ok=True)
    (tmp_path / ".gov" / "rules.md").write_text("# Rules\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _gates(project: Path) -> dict:
    return json.loads((project / "gates.json").read_text(encoding="utf-8"))


def test_dry_run_prints_and_writes_nothing(project, capsys):
    """The whole point: validate + print, touch nothing, run nothing."""
    before = (project / "gates.json").read_bytes()
    rc = gate.main(["add", "e2e", "--paths", "tools/**", "--mode", "all",
                    "--dry-run", "--", "node", "tools/e2e/matrix.mjs"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "dry run — gates.json is untouched, nothing ran" in out
    assert ('"command": ["node", "tools/e2e/matrix.mjs"]' in out)
    assert '"paths": ["tools/**"]' in out
    assert "modes: all" in out
    assert "run --gate e2e" in out            # the verification command
    assert (project / "gates.json").read_bytes() == before
    assert _gates(project)["gates"] == []


def test_command_separator_is_equivalent_to_double_dash(project, capsys):
    """A caller building argv programmatically cannot always emit a bare
    '--' positionally; --command is the same grammar, spelled."""
    assert gate.main(["add", "lint2", "--dry-run", "--command",
                      "ruff", "check", "."]) == 0
    out = capsys.readouterr().out
    assert '"command": ["ruff", "check", "."]' in out


def test_dry_run_still_validates(project, capsys):
    """A preview that skipped validation would confirm nothing."""
    (project / "gates.json").write_text(json.dumps(
        {"gates": [{"id": "taken", "command": ["true"]}],
         "modes": {"all": ["taken"]}, "defaultMode": "all"}), encoding="utf-8")
    assert gate.main(["add", "taken", "--dry-run", "--", "true"]) == 2
    assert "already exists" in capsys.readouterr().err
    assert gate.main(["add", "ok", "--dry-run", "--mode", "ghost",
                      "--", "true"]) == 2
    assert "no such mode" in capsys.readouterr().err
    assert gate.main(["add", "ok", "--dry-run"]) == 2
    assert "command is required" in capsys.readouterr().err


def test_help_documents_its_own_grammar(capsys):
    """`--help` is the surface agents and CI wrappers enumerate — the
    grammar lived in a source comment (#366)."""
    with pytest.raises(SystemExit):
        gate.main(["add", "--help"])
    flat = " ".join(capsys.readouterr().out.split())
    assert "gov gate add <id> [options] -- <command...>" in flat
    assert "--dry-run" in flat
    assert "gov gate add tests --paths 'tests/**' -- pytest -q" in flat


def test_dry_run_leaves_a_sealed_plane_sealed(project, capsys):
    """The motivating case: proposing a gate in a PR must not drift the
    seal (which would need a recorded re-baseline to repair)."""
    from gov import verify_plane
    verify_plane.baseline(project)
    assert verify_plane.main([]) == 0
    capsys.readouterr()
    assert gate.main(["add", "proposal", "--mode", "all", "--dry-run",
                      "--", "true"]) == 0
    assert verify_plane.main([]) == 0, "the seal must still verify"
    assert "dry run" in capsys.readouterr().out
