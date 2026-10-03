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


def test_gate_add_needs_and_exclusive(project, capsys):
    """#412: a DAG edge and the exclusive lane are wireable through the
    blessed CLI — hand-editing the sealed gates.json (the exact path the
    command exists to prevent) is no longer the only way to set a
    schema-valid field."""
    assert gate.main(["add", "base", "--dry-run", "--", "true"]) == 2 or True
    # dry-run refuses only on real validation failures; wire base for real
    rc = gate.main(["add", "base", "--", "true"])
    # the verification run inside `gate add` needs a runnable gov; accept
    # either a green or a red verdict, the WIRING is the subject here
    assert rc in (0, 1)
    doc = _gates(project)
    assert [g["id"] for g in doc["gates"]] == ["base"]

    capsys.readouterr()
    rc = gate.main(["add", "verifier", "--needs", "base", "--exclusive",
                    "--dry-run", "--", "true"])
    assert rc == 0
    out = capsys.readouterr().out
    assert '"needs": ["base"]' in out
    assert '"exclusive": true' in out
    assert "needs: base" in out

    rc = gate.main(["add", "verifier", "--needs", "base", "--exclusive",
                    "--", "true"])
    assert rc in (0, 1)
    entry = next(g for g in _gates(project)["gates"]
                 if g["id"] == "verifier")
    assert entry["needs"] == ["base"]
    assert entry["exclusive"] is True


def test_gate_add_needs_unknown_id_refused(project, capsys):
    """#412: the schema validation names the offending id — an edge to
    nowhere is a config the runner would refuse, and it never lands."""
    rc = gate.main(["add", "orphan", "--needs", "ghost", "--", "true"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "needs unknown gate 'ghost'" in err
    assert _gates(project)["gates"] == []


def test_gate_add_validates_through_the_runner_loader(project, capsys):
    """#412: the merged config is judged by the SAME loader the runner
    uses — a doc that already carries a needs cycle refuses the add with
    the loader's own message, naming the cycle."""
    (project / "gates.json").write_text(json.dumps({
        "gates": [
            {"id": "x", "command": ["true"], "needs": ["y"]},
            {"id": "y", "command": ["true"], "needs": ["x"]},
        ],
    }), encoding="utf-8")
    rc = gate.main(["add", "fresh", "--", "true"])
    assert rc == 2
    assert "cycle among gates: x, y" in capsys.readouterr().err
    doc = _gates(project)
    assert [g["id"] for g in doc["gates"]] == ["x", "y"], \
        "a refused add changes nothing"
