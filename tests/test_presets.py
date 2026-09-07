"""Presets: typed adoption bundles (D53).

Covers the loader's strict schema (rule 5 — every rejection names the
preset and the key), the list/show surfaces, apply's additive contracts
(D39 gate merge / D29 byte skills / D49 absent-key hints), idempotence,
the dogfooded parallel-workers skill (D19's byte-equality pin), the
packaging entry (a wheel without the preset files ships nothing), and
the end-to-end acceptance: a scratch git repo brought up with
`gov init --preset agent-heavy` goes green on `gov run --every-gate`,
as do the content presets' scratches (python-lib: a real pytest run and
a real `python -m build`; docs-bilingual: CHANGELOG/HIGHLIGHTS paired
green, unpaired red — the README's premise, proven).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from gov import cli, presets

REPO = Path(__file__).resolve().parent.parent
AGENT_HEAVY = "agent-heavy"
PYTHON_LIB = "python-lib"
DOCS_BILINGUAL = "docs-bilingual"


# --- the shipped bundle parses and means what the decision says -----------

def test_agent_heavy_bundle_loads():
    bundle = presets.load(AGENT_HEAVY)
    assert bundle["name"] == AGENT_HEAVY
    assert bundle["description"]
    assert [g["id"] for g in bundle["gates"]] == ["verify-decisions"]
    gate = bundle["gates"][0]
    assert gate["command"] == ["gov", "verify-decisions"]
    assert gate["paths"] == ["docs/decisions.md"]
    assert bundle["modes"] == {"governance": ["verify-decisions"]}
    assert bundle["skills"] == ["parallel-workers"]
    assert bundle["hints"] == {"note_presence_exempt": [".gov/tasks/**"]}


def test_python_lib_bundle_loads():
    """D53's staged python-lib preset: two build/test gates, mode wiring,
    deliberately lean (no skills, no hints)."""
    bundle = presets.load(PYTHON_LIB)
    assert bundle["name"] == PYTHON_LIB
    assert bundle["description"]
    assert [g["id"] for g in bundle["gates"]] == ["pytest", "build"]
    assert bundle["gates"][0]["command"] == ["python", "-m", "pytest", "-q"]
    assert bundle["gates"][0]["paths"] == ["**/*.py", "pyproject.toml"]
    assert bundle["gates"][1]["command"] == ["python", "-m", "build"]
    assert bundle["gates"][1]["paths"] == ["**/*.py", "pyproject.toml"]
    assert bundle["modes"] == {"all": ["pytest", "build"],
                               "quick": ["pytest"]}
    assert "skills" not in bundle and "hints" not in bundle


def test_docs_bilingual_bundle_loads():
    """D53's staged docs-bilingual preset: the CHANGELOG/HIGHLIGHTS sync
    guard (D37's gate, packaged), lean like python-lib."""
    bundle = presets.load(DOCS_BILINGUAL)
    assert bundle["name"] == DOCS_BILINGUAL
    assert bundle["description"]
    assert [g["id"] for g in bundle["gates"]] == ["doc-sync"]
    assert bundle["gates"][0]["command"] == ["gov", "verify-doc-sync"]
    assert bundle["gates"][0]["paths"] == ["CHANGELOG.md", "HIGHLIGHTS.md"]
    assert bundle["modes"] == {"all": ["doc-sync"]}
    assert "skills" not in bundle and "hints" not in bundle


def test_preset_show_prints_the_content_presets_items(capsys):
    for name, gate_ids, commands in (
            (PYTHON_LIB, ("pytest", "build"),
             ("python -m pytest -q", "python -m build")),
            (DOCS_BILINGUAL, ("doc-sync",), ("gov verify-doc-sync",))):
        assert cli.main(["preset", "show", name]) == 0
        out = capsys.readouterr().out
        for gid in gate_ids:
            assert gid in out
        for command in commands:
            assert command in out
        assert "all" in out                      # mode wiring shown
        assert "read-only" in out


def test_preset_list_names_the_bundle(capsys):
    assert cli.main(["preset", "list"]) == 0
    out = capsys.readouterr().out
    assert AGENT_HEAVY in out
    assert "Multi-agent parallel development" in out


def test_preset_list_names_the_content_presets(capsys):
    """D53's staged second stage: the two content presets ship on the same
    matrix, and `gov preset list` reads (and validates) every bundle."""
    assert cli.main(["preset", "list"]) == 0
    out = capsys.readouterr().out
    assert PYTHON_LIB in out
    assert "pytest and build" in out
    assert DOCS_BILINGUAL in out
    assert "CHANGELOG/HIGHLIGHTS sync guard" in out


def test_preset_show_prints_every_item_and_writes_nothing(tmp_path, capsys):
    assert cli.main(["preset", "show", AGENT_HEAVY]) == 0
    out = capsys.readouterr().out
    assert "verify-decisions" in out          # every gate
    assert "gov verify-decisions" in out      # its command
    assert "governance" in out                # every mode change
    assert "parallel-workers" in out          # every skill
    assert "note_presence_exempt" in out      # every hint
    assert "read-only" in out
    assert not list(tmp_path.iterdir())       # show writes nothing anywhere


def test_preset_show_unknown_name_lists_available(tmp_path, capsys):
    assert cli.main(["preset", "show", "no-such"]) == 2
    err = capsys.readouterr().err
    assert "no-such" in err and AGENT_HEAVY in err


# --- the loader's strict schema (rule 5: name the preset and the key) -----

def _write_bundle(root: Path, raw, name: str = "probe") -> Path:
    bundle = root / name
    (bundle / "skills" / "some-skill").mkdir(parents=True)
    (bundle / "skills" / "some-skill" / "SKILL.md").write_text("x\n", encoding="utf-8")
    (bundle / "preset.json").write_text(
        raw if isinstance(raw, str) else json.dumps(raw), encoding="utf-8")
    return root


def test_loader_rejects_unknown_key(tmp_path):
    _write_bundle(tmp_path, {"name": "probe", "description": "d", "gates": "no"})
    with pytest.raises(presets.PresetError) as e:
        presets.load("probe", root=tmp_path)
    assert "'probe'" in str(e.value) and "'gates'" in str(e.value)


def test_loader_rejects_missing_name_and_description(tmp_path):
    _write_bundle(tmp_path, {"description": "d"})
    with pytest.raises(presets.PresetError) as e:
        presets.load("probe", root=tmp_path)
    assert "'name'" in str(e.value)
    _write_bundle(tmp_path, {"name": "probe", "description": 7}, name="other")
    with pytest.raises(presets.PresetError) as e:
        presets.load("other", root=tmp_path)
    assert "'description'" in str(e.value)


def test_loader_rejects_name_directory_mismatch(tmp_path):
    _write_bundle(tmp_path, {"name": "elsewhere", "description": "d"})
    with pytest.raises(presets.PresetError) as e:
        presets.load("probe", root=tmp_path)
    assert "elsewhere" in str(e.value)


def test_loader_rejects_bad_json(tmp_path):
    _write_bundle(tmp_path, "{not json")
    with pytest.raises(presets.PresetError) as e:
        presets.load("probe", root=tmp_path)
    assert "not valid JSON" in str(e.value)


def test_loader_judges_gates_by_the_real_schema(tmp_path):
    """A gate fragment the runner would reject must fail the loader —
    same validator, not a parallel one (D39's shape rule)."""
    _write_bundle(tmp_path, {"name": "probe", "description": "d", "gates": [
        {"id": "a", "command": ["true"]},
        {"id": "a", "command": ["true"]},  # duplicate id
    ]})
    with pytest.raises(presets.PresetError) as e:
        presets.load("probe", root=tmp_path)
    assert "duplicate gate id" in str(e.value)
    _write_bundle(tmp_path, {"name": "other", "description": "d", "gates": [
        {"id": "a", "command": "not-an-array"},
    ]}, name="other")
    with pytest.raises(presets.PresetError) as e:
        presets.load("other", root=tmp_path)
    assert "command" in str(e.value)


def test_loader_rejects_mode_referencing_unknown_gate(tmp_path):
    """A mode may point at preset gates and shipped-template gates —
    never at a ghost."""
    _write_bundle(tmp_path, {"name": "probe", "description": "d",
                             "gates": [{"id": "a", "command": ["true"]}],
                             "modes": {"m": ["a", "ghost"]}})
    with pytest.raises(presets.PresetError) as e:
        presets.load("probe", root=tmp_path)
    assert "ghost" in str(e.value) and "'m'" in str(e.value)


def test_loader_accepts_mode_referencing_template_gate(tmp_path):
    _write_bundle(tmp_path, {"name": "probe", "description": "d",
                             "modes": {"m": ["self-test"]}})
    bundle = presets.load("probe", root=tmp_path)
    assert bundle["modes"] == {"m": ["self-test"]}


def test_loader_rejects_missing_skill_file_and_unknown_hint(tmp_path):
    _write_bundle(tmp_path, {"name": "probe", "description": "d",
                             "skills": ["ghost-skill"]})
    with pytest.raises(presets.PresetError) as e:
        presets.load("probe", root=tmp_path)
    assert "ghost-skill" in str(e.value)
    _write_bundle(tmp_path, {"name": "other", "description": "d",
                             "hints": {"not_a_manifest_key": ["x/**"]}},
                  name="other")
    with pytest.raises(presets.PresetError) as e:
        presets.load("other", root=tmp_path)
    assert "not_a_manifest_key" in str(e.value)
    _write_bundle(tmp_path, {"name": "third", "description": "d",
                             "hints": {"note_presence_exempt": "src/**"}},
                  name="third")
    with pytest.raises(presets.PresetError) as e:
        presets.load("third", root=tmp_path)
    assert "note_presence_exempt" in str(e.value)


# --- apply: the additive contracts ----------------------------------------

def _init(tmp_path):
    assert cli.init(tmp_path) == 0
    return tmp_path


def test_apply_lands_gates_skill_and_hint(tmp_path, capsys):
    _init(tmp_path)
    assert cli.main(["preset", "apply", AGENT_HEAVY,
                     "--project", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "added 1" in out and "verify-decisions" in out
    assert "created .agents/skills/parallel-workers/SKILL.md" in out
    assert "note_presence_exempt" in out

    cfg = json.loads((tmp_path / "gates.json").read_text(encoding="utf-8"))
    ids = [g["id"] for g in cfg["gates"]]
    assert "verify-decisions" in ids
    assert "verify-decisions" in cfg["modes"]["governance"]
    # merged result passes the real schema loader
    from gov import gates as gates_mod
    gates_mod.load_config(str(tmp_path / "gates.json"))

    skill = tmp_path / ".agents" / "skills" / "parallel-workers" / "SKILL.md"
    assert skill.exists()
    manifest = json.loads((tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["note_presence_exempt"] == [".gov/tasks/**"]


def test_apply_is_idempotent(tmp_path, capsys):
    _init(tmp_path)
    assert cli.main(["preset", "apply", AGENT_HEAVY,
                     "--project", str(tmp_path)]) == 0
    capsys.readouterr()
    snapshot = {
        "gates": (tmp_path / "gates.json").read_bytes(),
        "manifest": (tmp_path / ".gov" / "manifest.json").read_bytes(),
        "skill": (tmp_path / ".agents" / "skills" / "parallel-workers"
                  / "SKILL.md").read_bytes(),
    }
    assert cli.main(["preset", "apply", AGENT_HEAVY,
                     "--project", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "nothing to add" in out
    assert "already adopted" in out          # gates
    assert "already present — untouched" in out  # skill
    assert "local value kept" in out         # hint
    assert "already adopted — nothing written" in out
    assert (tmp_path / "gates.json").read_bytes() == snapshot["gates"]
    assert (tmp_path / ".gov" / "manifest.json").read_bytes() == snapshot["manifest"]
    assert (tmp_path / ".agents" / "skills" / "parallel-workers"
            / "SKILL.md").read_bytes() == snapshot["skill"]


def test_apply_appends_into_existing_template_modes(tmp_path):
    """The path agent-heavy's fresh `governance` mode never exercised alone:
    python-lib declares `all` and `quick`, which the shipped template
    ALREADY creates — D39's append ruling must preserve the local
    membership verbatim and add only the newly adopted ids."""
    from gov import gates as gates_mod
    _init(tmp_path)
    template = json.loads((REPO / "gov" / "templates" / "gates.json")
                          .read_text(encoding="utf-8"))
    assert template["modes"]["all"] and template["modes"]["quick"]

    assert cli.main(["preset", "apply", PYTHON_LIB,
                     "--project", str(tmp_path)]) == 0
    cfg = json.loads((tmp_path / "gates.json").read_text(encoding="utf-8"))
    assert cfg["modes"]["all"] == (template["modes"]["all"]
                                   + ["pytest", "build"])
    assert cfg["modes"]["quick"] == template["modes"]["quick"] + ["pytest"]
    assert cfg["modes"]["governance"] == template["modes"]["governance"]
    gates_mod.load_config(str(tmp_path / "gates.json"))


def test_merge_appends_only_newly_adopted_ids_into_existing_mode():
    """The shared machine (gates.merge_gates_by_id) under the preset
    ruling, pinned directly: an existing local mode gains exactly the
    ids this merge newly added — never a duplicate of an id it already
    carries, never a reordering of local membership."""
    from gov import gates as gates_mod
    local = {"gates": [{"id": "x", "command": ["true"]}],
             "modes": {"all": ["x"]}}
    incoming = {
        "gates": [{"id": "x", "command": ["true"]},   # already adopted
                  {"id": "y", "command": ["true"]}],  # new
        "modes": {"all": ["x", "y"]},
    }
    merged, added, notices = gates_mod.merge_gates_by_id(
        local, incoming, what="preset 'probe'", on_drift="keep")
    assert [g["id"] for g in added] == ["y"]
    assert merged["modes"]["all"] == ["x", "y"]
    assert merged["modes"]["all"].count("x") == 1


def test_merge_converge_gains_declared_ids_from_local_gates_too():
    """The converge ruling (presets only): a declared id resolves from
    the local gates as well as this round's additions; a declared id no
    gate carries is skipped and NAMED (rule 5); --adopt-new refuses the
    combo loudly — its membership stays added-only (D39)."""
    from gov import gates as gates_mod
    local = {"gates": [{"id": "x", "command": ["true"]},
                       {"id": "z", "command": ["true"]}],
             "modes": {"all": ["x"]}}
    incoming = {"gates": [{"id": "y", "command": ["true"]}],
                "modes": {"all": ["y", "z", "ghost"]}}
    merged, added, notices = gates_mod.merge_gates_by_id(
        local, incoming, what="preset 'probe'", on_drift="keep",
        mode_membership="converge")
    assert [g["id"] for g in added] == ["y"]
    assert merged["modes"]["all"] == ["x", "y", "z"]  # local order first
    assert any("ghost" in n and "skipped" in n for n in notices)
    with pytest.raises(ValueError):
        gates_mod.merge_gates_by_id(
            local, incoming, what="adopt-new", on_drift="refuse",
            mode_membership="converge")


def test_apply_converges_mode_membership_for_already_adopted_gates(
        tmp_path, capsys):
    """The verification drill's defect: gates already adopted (wired by
    hand) but membership never landed — the old apply reported "already
    adopted" and left the project D24-unreachable (the next `gov run`
    died on a config error). Apply converges: membership is written even
    when no gate is added this round; a converged re-apply writes
    nothing."""
    from gov import gates as gates_mod
    _init(tmp_path)
    gates_path = tmp_path / "gates.json"
    cfg = json.loads(gates_path.read_text(encoding="utf-8"))
    my_gate = {"id": "my-own-first", "label": "mine", "command": ["true"]}
    cfg["gates"].insert(1, my_gate)
    cfg["gates"] += [{"id": "pytest", "label": "hand-wired",
                      "command": ["python", "-m", "pytest", "-q"]},
                     {"id": "build", "label": "hand-wired",
                      "command": ["python", "-m", "build"]}]
    cfg["modes"]["all"] = ["self-test", "my-own-first", "notes", "pairing",
                           "note-presence", "conflict-markers", "archive",
                           "task"]
    gates_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    with pytest.raises(gates_mod.ConfigError):
        gates_mod.load_config(str(gates_path))  # the drill's D24 state

    assert cli.main(["preset", "apply", PYTHON_LIB,
                     "--project", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "nothing to add" in out                      # gates were present
    assert "mode 'all' += pytest, build" in out
    merged = json.loads(gates_path.read_text(encoding="utf-8"))
    assert merged["modes"]["all"] == cfg["modes"]["all"] + ["pytest", "build"]
    assert merged["modes"]["quick"] == ["notes", "pytest"]
    by_id = {g["id"]: g for g in merged["gates"]}
    assert by_id["pytest"]["label"] == "hand-wired"     # local object kept
    assert by_id["my-own-first"] == my_gate
    gates_mod.load_config(str(gates_path))              # reachable again

    before = gates_path.read_bytes()
    assert cli.main(["preset", "apply", PYTHON_LIB,
                     "--project", str(tmp_path)]) == 0
    assert "already adopted — nothing written" in capsys.readouterr().out
    assert gates_path.read_bytes() == before


def test_apply_skips_mode_ids_missing_from_the_project(tmp_path, capsys):
    """A preset mode id that no gate in the project carries (an adopter
    deleted the template gate) is skipped and named — never silently
    written into an invalid config."""
    from gov import gates as gates_mod
    _init(tmp_path)
    gates_path = tmp_path / "gates.json"
    cfg = json.loads(gates_path.read_text(encoding="utf-8"))
    cfg["gates"] = [g for g in cfg["gates"] if g["id"] != "self-test"]
    cfg["modes"]["all"] = [m for m in cfg["modes"]["all"] if m != "self-test"]
    cfg["modes"]["governance"] = []
    gates_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    capsys.readouterr()

    root = tmp_path / "bundles"
    _write_bundle(root, {"name": "probe", "description": "d",
                         "modes": {"all": ["self-test"]}})
    assert presets.apply(tmp_path, "probe", root=root) == 0
    out = capsys.readouterr().out
    assert "self-test" in out and "skipped" in out
    merged = json.loads(gates_path.read_text(encoding="utf-8"))
    assert "self-test" not in merged["modes"]["all"]
    gates_mod.load_config(str(gates_path))  # the skip kept the config valid


def test_apply_never_overwrites_a_local_same_id_gate(tmp_path, capsys):
    """D8/D39: the local gate IS the adopted state — kept and named."""
    _init(tmp_path)
    gates_path = tmp_path / "gates.json"
    cfg = json.loads(gates_path.read_text(encoding="utf-8"))
    mine = {"id": "verify-decisions", "label": "my own guard",
            "command": ["my-guard", "run"]}
    cfg["gates"].append(mine)
    cfg["modes"]["governance"].append("verify-decisions")
    gates_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    assert cli.main(["preset", "apply", AGENT_HEAVY,
                     "--project", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "kept your local version" in out
    merged = json.loads(gates_path.read_text(encoding="utf-8"))
    landed = [g for g in merged["gates"] if g["id"] == "verify-decisions"]
    assert landed == [mine]  # exactly one gate, the local object untouched


def test_apply_never_overwrites_an_existing_manifest_hint(tmp_path, capsys):
    """D49: the local value always wins; the notice says so."""
    _init(tmp_path)
    manifest_path = tmp_path / ".gov" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["note_presence_exempt"] = ["local/**"]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    assert cli.main(["preset", "apply", AGENT_HEAVY,
                     "--project", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "local value kept" in out
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["note_presence_exempt"] == ["local/**"]


def test_apply_skips_an_existing_skill(tmp_path, capsys):
    """D29: a project's own skill is never overwritten."""
    _init(tmp_path)
    skill = tmp_path / ".agents" / "skills" / "parallel-workers" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# my own protocol\n", encoding="utf-8")
    assert cli.main(["preset", "apply", AGENT_HEAVY,
                     "--project", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "untouched" in out
    assert skill.read_text(encoding="utf-8") == "# my own protocol\n"


def test_apply_without_init_refuses_loud(tmp_path, capsys):
    """The hard-coded contract: presets adopt into an INITIALIZED project —
    no improvised half-project."""
    assert cli.main(["preset", "apply", AGENT_HEAVY,
                     "--project", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert "gates.json not found" in err and "gov init" in err


def test_apply_unknown_preset_lists_available(tmp_path, capsys):
    _init(tmp_path)
    assert cli.main(["preset", "apply", "no-such-preset",
                     "--project", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert "no-such-preset" in err and AGENT_HEAVY in err


# --- init --preset: one command for a typed start --------------------------

def test_init_preset_on_fresh_project(tmp_path):
    assert cli.init(tmp_path, preset=AGENT_HEAVY) == 0
    cfg = json.loads((tmp_path / "gates.json").read_text(encoding="utf-8"))
    assert "verify-decisions" in [g["id"] for g in cfg["gates"]]
    assert "verify-decisions" in cfg["modes"]["governance"]
    assert (tmp_path / ".agents" / "skills" / "parallel-workers"
            / "SKILL.md").exists()
    manifest = json.loads((tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["note_presence_exempt"] == [".gov/tasks/**"]


def test_init_preset_retrofits_an_initialized_project(tmp_path):
    _init(tmp_path)
    assert cli.init(tmp_path, preset=AGENT_HEAVY) == 0
    cfg = json.loads((tmp_path / "gates.json").read_text(encoding="utf-8"))
    assert "verify-decisions" in [g["id"] for g in cfg["gates"]]


def test_init_preset_rejects_unknown_name_before_any_mutation(tmp_path, capsys):
    assert cli.init(tmp_path, preset="no-such") == 2
    err = capsys.readouterr().err
    assert "no-such" in err and AGENT_HEAVY in err
    assert not (tmp_path / ".gov").exists(), \
        "a bad preset name must never leave a half-initialized project"


def test_init_preset_does_not_combine_with_upgrade_or_adopt(tmp_path, capsys):
    assert cli.init(tmp_path, preset=AGENT_HEAVY, upgrade=True) == 2
    assert "--upgrade" in capsys.readouterr().err
    assert cli.init(tmp_path, preset=AGENT_HEAVY, adopt=["all"]) == 2
    assert "--adopt" in capsys.readouterr().err


def test_init_preset_missing_name_is_a_parse_error(tmp_path):
    assert cli.main(["init", "--project", str(tmp_path), "--preset"]) == 2


# --- dogfood: the live skill and the shipped template are one file --------

def test_preset_skill_matches_live_skill():
    """D19's pin: the template shipped to adopters and this repo's own
    .agents skill are byte-identical — we run the same protocol."""
    shipped = (REPO / "gov" / "templates" / "presets" / AGENT_HEAVY
               / "skills" / "parallel-workers" / "SKILL.md")
    live = REPO / ".agents" / "skills" / "parallel-workers" / "SKILL.md"
    assert shipped.read_text(encoding="utf-8") == live.read_text(encoding="utf-8"), (
        "parallel-workers: preset template and live skill drifted — align them")


# --- packaging: a wheel without the preset files ships nothing -------------

def test_presets_are_reachable_as_package_data():
    """`gov preset list` must work from an installed package, not only a
    checkout — importlib.resources reads package data, so this fails the
    moment the pyproject glob stops matching (the skills/*/SKILL.md
    precedent, D19). The content presets (D53's second stage) pin the
    glob for preset dirs that carry no skills/ subtree at all."""
    from importlib.resources import files
    root = files("gov.templates").joinpath("presets")
    names = sorted(p.name for p in root.iterdir()
                   if p.is_dir() and p.joinpath("preset.json").is_file())
    assert AGENT_HEAVY in names
    assert PYTHON_LIB in names
    assert DOCS_BILINGUAL in names
    skill = root / AGENT_HEAVY / "skills" / "parallel-workers" / "SKILL.md"
    assert b"gov acquire" in skill.read_bytes()
    # every shipped preset dir carries its README through the same glob
    for name in (AGENT_HEAVY, PYTHON_LIB, DOCS_BILINGUAL):
        assert (root / name / "README.md").is_file(), name


def test_package_data_declares_the_presets_glob():
    """The packaging entry itself is pinned: drop the presets glob and the
    wheel builds clean but `gov preset list` goes empty in installs."""
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert "presets/*/preset.json" in text
    assert "presets/*/skills/*/SKILL.md" in text


# --- acceptance: scratch repo, real subprocesses, the full matrix ---------

def _git_repo(root: Path, env: dict) -> None:
    subprocess.run(["git", "init", "-q", "."], cwd=root, check=True, env=env)
    for cmd in (["git", "config", "user.email", "t@t"],
                ["git", "config", "user.name", "t"]):
        subprocess.run(cmd, cwd=root, check=True, env=env)


def _gov_env(root: Path) -> dict:
    """Hermetic env whose PATH carries a `gov` shim running THIS tree —
    the scratch's gates invoke `gov ...` commands (D33's fixture walls).

    The shim is a POSIX shebang script: these acceptance tests are the
    POSIX side of the #168 portability story (a Windows equivalent would
    need a .bat shim — deferred with the rule-6 decision)."""
    bin_dir = root / "bin"
    bin_dir.mkdir(exist_ok=True)
    gov_shim = bin_dir / "gov"
    gov_shim.write_text(
        "#!/bin/sh\n"
        f"exec '{sys.executable}' -m gov \"$@\"\n", encoding="utf-8")
    gov_shim.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env["PYTHONPATH"] = str(REPO)
    env["GIT_CEILING_DIRECTORIES"] = str(root.parent)
    return env


posix_shim = pytest.mark.skipif(
    sys.platform == "win32",
    reason="the PATH `gov` shim is a POSIX shebang script")


@posix_shim
def test_acceptance_init_preset_then_every_gate_green(tmp_path):
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    env = _gov_env(tmp_path)
    _git_repo(scratch, env)
    r = subprocess.run(
        [sys.executable, "-m", "gov", "init", "--preset", AGENT_HEAVY],
        cwd=scratch, env=env, capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr

    cfg = json.loads((scratch / "gates.json").read_text(encoding="utf-8"))
    assert "verify-decisions" in [g["id"] for g in cfg["gates"]]
    assert (scratch / ".agents" / "skills" / "parallel-workers" / "SKILL.md").exists()
    manifest = json.loads((scratch / ".gov" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["note_presence_exempt"] == [".gov/tasks/**"]

    # the full matrix, inside the scratch, must be green
    run = subprocess.run(
        [sys.executable, "-m", "gov", "run", "--every-gate"],
        cwd=scratch, env=env, capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "PASS verify-decisions" in run.stdout

    # a repeated apply is a no-op: exit 0, zero writes
    before = {p: p.read_bytes() for p in (
        scratch / "gates.json", scratch / ".gov" / "manifest.json")}
    again = subprocess.run(
        [sys.executable, "-m", "gov", "preset", "apply", AGENT_HEAVY,
         "--project", "."],
        cwd=scratch, env=env, capture_output=True, text=True, timeout=120)
    assert again.returncode == 0, again.stdout + again.stderr
    assert "already adopted — nothing written" in again.stdout
    for p, content in before.items():
        assert p.read_bytes() == content


# --- acceptance: the content presets (D53's second stage) ------------------

def _build_available() -> bool:
    """The `build` gate shells out to `python -m build`; environments
    without the package (pip install build) skip loudly instead of
    failing on an environment gap that has nothing to do with presets."""
    import importlib.util
    return importlib.util.find_spec("build") is not None


@pytest.mark.skipif(not _build_available(),
                    reason="the python-lib build gate needs the 'build' "
                           "package (pip install build)")
@posix_shim
def test_acceptance_python_lib_scratch_green(tmp_path):
    """Minimal python project → plain init → apply python-lib → the full
    matrix is green with pytest and build actually executing."""
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    env = _gov_env(tmp_path)
    _git_repo(scratch, env)
    (scratch / "pyproject.toml").write_text(
        '[build-system]\n'
        'requires = ["setuptools>=61"]\n'
        'build-backend = "setuptools.build_meta"\n'
        '\n'
        '[project]\n'
        'name = "scratch-lib"\n'
        'version = "0.1.0"\n', encoding="utf-8")
    (scratch / "test_it.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8")

    r = subprocess.run([sys.executable, "-m", "gov", "init"],
                       cwd=scratch, env=env, capture_output=True, text=True,
                       timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    r = subprocess.run(
        [sys.executable, "-m", "gov", "preset", "apply", PYTHON_LIB,
         "--project", "."],
        cwd=scratch, env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "gates: added 2 (in preset order): pytest, build" in r.stdout

    cfg = json.loads((scratch / "gates.json").read_text(encoding="utf-8"))
    template = json.loads((REPO / "gov" / "templates" / "gates.json")
                          .read_text(encoding="utf-8"))
    # D39 append: template membership preserved, preset ids appended
    assert cfg["modes"]["all"] == template["modes"]["all"] + ["pytest", "build"]
    assert cfg["modes"]["quick"] == template["modes"]["quick"] + ["pytest"]

    run = subprocess.run(
        [sys.executable, "-m", "gov", "run", "--every-gate"],
        cwd=scratch, env=env, capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "PASS pytest" in run.stdout
    assert "PASS build" in run.stdout


@posix_shim
def test_acceptance_docs_bilingual_scratch_green_then_fail_loud(tmp_path):
    """Minimal bilingual docs repo (CHANGELOG.md + the HIGHLIGHTS file
    verify-doc-sync reads, each carrying the same version section) →
    plain init → apply docs-bilingual → green; and the README's stated
    premise proven: an unpaired CHANGELOG version turns the gate red —
    correct fail-loud, never a silent pass."""
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    env = _gov_env(tmp_path)
    _git_repo(scratch, env)
    (scratch / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [1.0.0] - 2026-09-05\n\n- first release\n",
        encoding="utf-8")
    (scratch / "gov").mkdir()
    (scratch / "gov" / "HIGHLIGHTS.md").write_text(
        "# Highlights\n\n## 1.0.0 — first release\n\n- first, usage-shaped\n",
        encoding="utf-8")

    r = subprocess.run([sys.executable, "-m", "gov", "init"],
                       cwd=scratch, env=env, capture_output=True, text=True,
                       timeout=300)
    assert r.returncode == 0, r.stdout + r.stderr
    r = subprocess.run(
        [sys.executable, "-m", "gov", "preset", "apply", DOCS_BILINGUAL,
         "--project", "."],
        cwd=scratch, env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "gates: added 1 (in preset order): doc-sync" in r.stdout

    run = subprocess.run(
        [sys.executable, "-m", "gov", "run", "--every-gate"],
        cwd=scratch, env=env, capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "PASS doc-sync" in run.stdout
    assert "1 version(s) paired" in run.stdout

    # the premise: a version that reaches CHANGELOG without its HIGHLIGHTS
    # section fails the gate loudly, naming the fix
    (scratch / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [1.1.0] - 2026-09-06\n\n- second release\n\n"
        "## [1.0.0] - 2026-09-05\n\n- first release\n", encoding="utf-8")
    red = subprocess.run(
        [sys.executable, "-m", "gov", "run", "--gate", "doc-sync"],
        cwd=scratch, env=env, capture_output=True, text=True, timeout=120)
    assert red.returncode == 1
    assert "FAIL doc-sync" in red.stdout
    assert "CHANGELOG has [1.1.0] but HIGHLIGHTS has" in red.stdout
