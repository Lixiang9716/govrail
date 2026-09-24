import json
import sys
from pathlib import Path

import pytest

from gov import __version__, cli, plane


def test_init_creates_files(tmp_path):
    assert plane.init(tmp_path) == 0
    assert (tmp_path / ".gov" / "rules.md").exists()
    assert (tmp_path / ".gov" / "manifest.json").exists()
    assert (tmp_path / "gates.json").exists()
    assert (tmp_path / ".agents" / "notes" / "README.md").exists()
    assert (tmp_path / "AGENTS.md").exists()


def test_init_template_is_advisory_first(tmp_path):
    """A fresh install must not go red on the first run (P0 defect 3)."""
    assert plane.init(tmp_path) == 0
    cfg = json.loads((tmp_path / "gates.json").read_text(encoding="utf-8"))
    assert cfg["defaultMode"] == "all"
    pairing = [g for g in cfg["gates"] if g["id"] == "pairing"][0]
    assert pairing["allowFailure"] is True


def test_init_manifest_records_cli_version(tmp_path):
    assert plane.init(tmp_path) == 0
    manifest = json.loads((tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == __version__


def test_init_idempotent(tmp_path):
    assert plane.init(tmp_path) == 0
    before = (tmp_path / "gates.json").read_text(encoding="utf-8")
    assert plane.init(tmp_path) == 0
    assert (tmp_path / "gates.json").read_text(encoding="utf-8") == before


def test_uninstall_reverses(tmp_path):
    plane.init(tmp_path)
    (tmp_path / "keep.txt").write_text("keep", encoding="utf-8")
    assert plane.uninstall(tmp_path) == 0
    assert (tmp_path / "keep.txt").exists()
    assert not (tmp_path / ".gov").exists()
    assert not (tmp_path / "gates.json").exists()


def test_init_help_no_side_effect(tmp_path):
    assert cli.main(["init", "--help"]) == 0
    assert cli.main(["init", "--version"]) == 0


def test_init_unknown_arg_rejected(tmp_path):
    assert cli.main(["init", "--bogus"]) == 2


def _git_repo(tmp_path):
    import subprocess
    for cmd in (
        ["git", "init", "-q", "."],
        ["git", "config", "user.email", "t@t"],
        ["git", "config", "user.name", "t"],
    ):
        subprocess.run(cmd, cwd=tmp_path, check=True)


def test_init_hooks_and_ci_roundtrip(tmp_path):
    _git_repo(tmp_path)
    assert plane.init(tmp_path, hooks=True, ci=True) == 0
    assert (tmp_path / ".gov" / "hooks" / "pre-push").exists()
    git_hook = tmp_path / ".git" / "hooks" / "pre-push"
    assert git_hook.exists()
    if sys.platform != "win32":  # X_OK is meaningless on Windows (#168);
        # git-for-windows executes hooks regardless of the FS mode bit
        assert git_hook.stat().st_mode & 0o111  # executable
    workflow = tmp_path / ".github" / "workflows" / "gov.yml"
    assert workflow.exists()
    assert plane.init(tmp_path, hooks=True, ci=True) == 0  # idempotent re-run
    assert plane.uninstall(tmp_path) == 0
    assert not git_hook.exists()
    assert not workflow.exists()
    assert not (tmp_path / "gates.json").exists()


def test_init_hooks_refuses_foreign_hook(tmp_path):
    _git_repo(tmp_path)
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    (hooks / "pre-push").write_text("#!/bin/sh\nmy own hook\n", encoding="utf-8")
    assert plane.init(tmp_path, hooks=True) == 2
    assert (hooks / "pre-push").read_text(encoding="utf-8").startswith("#!/bin/sh\nmy own")
    assert not (tmp_path / "gates.json").exists()  # no half-initialized state


def test_init_hooks_needs_git(tmp_path):
    assert plane.init(tmp_path, hooks=True) == 2
    assert not (tmp_path / "gates.json").exists()


def test_init_ci_keeps_existing_workflow(tmp_path):
    wf = tmp_path / ".github" / "workflows" / "gov.yml"
    wf.parent.mkdir(parents=True, exist_ok=True)
    wf.write_text("mine: yes\n", encoding="utf-8")
    assert plane.init(tmp_path, ci=True) == 0
    assert wf.read_text(encoding="utf-8") == "mine: yes\n"


def test_init_template_modes_note_presence_and_governance(tmp_path):
    assert plane.init(tmp_path) == 0
    cfg = json.loads((tmp_path / "gates.json").read_text(encoding="utf-8"))
    ids = [g["id"] for g in cfg["gates"]]
    assert "note-presence" in ids
    # D4 (reversal): the vendor's own 53-case smoke test is OUT of the
    # shipped DAG — it pinned every adopter's push to govrail's release
    # health. govrail itself keeps the gate in ITS OWN gates.json.
    assert "self-test" not in ids
    assert "self-test" not in cfg["modes"]["all"]
    # the plane seal ships instead: the constitution is tamper-evident
    assert "plane" in ids
    assert cfg["modes"]["governance"] == ["plane"]  # shortcut stays, re-aimed
    staged = {g["id"]: g.get("stages", []) for g in cfg["gates"]}
    assert staged["pairing"] == ["pre-commit"]
    assert staged["conflict-markers"] == ["pre-commit"]


def test_init_injects_skills(tmp_path):
    assert plane.init(tmp_path) == 0
    for name in plane.SKILLS:
        p = tmp_path / ".agents" / "skills" / name / "SKILL.md"
        assert p.exists(), name
    manifest = json.loads((tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8"))
    assert ".agents/skills/recall-first/SKILL.md" in manifest["created"]


def test_init_never_overwrites_own_skill(tmp_path):
    own = tmp_path / ".agents" / "skills" / "code-review" / "SKILL.md"
    own.parent.mkdir(parents=True)
    own.write_text("my own review convention\n", encoding="utf-8")
    assert plane.init(tmp_path) == 0
    assert own.read_text(encoding="utf-8") == "my own review convention\n"
    manifest = json.loads((tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8"))
    assert ".agents/skills/code-review/SKILL.md" not in manifest["created"]


def test_uninstall_removes_injected_skills(tmp_path):
    plane.init(tmp_path)
    assert plane.uninstall(tmp_path) == 0
    assert not (tmp_path / ".agents" / "skills").exists()


def test_templates_match_live_skills():
    """The shipped templates and this repo's live skills are one source."""
    root = Path(__file__).resolve().parent.parent
    for name in plane.SKILLS:
        shipped = root / "gov" / "templates" / "skills" / name / "SKILL.md"
        live = root / ".agents" / "skills" / name / "SKILL.md"
        assert shipped.read_text(encoding="utf-8") == live.read_text(encoding="utf-8"), (
            f"{name}: template and live skill drifted — align them"
        )


def test_init_next_steps_match_reality(tmp_path, capsys):
    """No paired docs → no baseline advice (the old step 2 exit-2'd)."""
    assert plane.init(tmp_path) == 0
    out = capsys.readouterr().out
    assert "no paired docs detected" in out
    assert "verify-pairing --write" not in out
    # D1 guidance: the shipped gates guard the governance plane — init
    # says so and points at the presets for typed project gates.
    assert "governance plane" in out
    assert "gov preset list" in out


def test_init_next_steps_with_docs(tmp_path, capsys):
    """A monolingual project (docs, no counterparts) gets the #315 branch:
    the pairing baseline is NOT recommended — it would fail on day one."""
    (tmp_path / "README.md").write_text("# x\n", encoding="utf-8")
    assert plane.init(tmp_path) == 0
    out = capsys.readouterr().out
    assert "single-language project" in out
    assert "verify pairing --write" in out  # canonical spelling (#316)
    assert "verify-pairing" not in out      # never the deprecated alias
    assert "no paired docs detected" not in out


def test_init_next_steps_with_paired_docs(tmp_path, capsys):
    """A project with actual counterparts gets the baseline advice."""
    (tmp_path / "README.md").write_text("# x\n", encoding="utf-8")
    (tmp_path / "README.zh.md").write_text("# x\n", encoding="utf-8")
    assert plane.init(tmp_path) == 0
    out = capsys.readouterr().out
    assert "gov verify pairing --write" in out
    assert "single-language project" not in out


def test_init_next_steps_leads_with_gate_add(tmp_path, capsys):
    """#309: wiring the first product gate is step 1, and it names the
    scaffolding command — the shipped gates guard governance, not code."""
    (tmp_path / "README.md").write_text("# x\n", encoding="utf-8")
    assert plane.init(tmp_path) == 0
    out = capsys.readouterr().out
    assert "gov gate add" in out
    first_step = out.split("next steps:")[1].strip().splitlines()[0]
    assert "gate" in first_step


def test_hooks_retrofit_on_initialized_project(tmp_path):
    """F5: --hooks works incrementally; customizations stay untouched."""
    _git_repo(tmp_path)
    assert plane.init(tmp_path) == 0
    rules = tmp_path / ".gov" / "rules.md"
    rules.write_text(rules.read_text(encoding="utf-8") + "\n# CUSTOM RULE\n", encoding="utf-8")
    gates = tmp_path / "gates.json"
    customized = gates.read_text(encoding="utf-8").replace("note format", "CUSTOM LABEL")
    gates.write_text(customized, encoding="utf-8")
    assert plane.init(tmp_path, hooks=True, ci=True) == 0
    assert (tmp_path / ".git" / "hooks" / "pre-push").exists()
    assert (tmp_path / ".github" / "workflows" / "gov.yml").exists()
    assert "CUSTOM RULE" in rules.read_text(encoding="utf-8")      # untouched
    assert "CUSTOM LABEL" in gates.read_text(encoding="utf-8")     # untouched
    manifest = json.loads((tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8"))
    assert "pre-push" in manifest["gitHooks"]
    assert ".github/workflows/gov.yml" in manifest["created"]


def test_retrofit_is_idempotent(tmp_path):
    _git_repo(tmp_path)
    assert plane.init(tmp_path, hooks=True) == 0
    assert plane.init(tmp_path, hooks=True) == 0  # re-run: no-op, no duplicate
    manifest = json.loads((tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["gitHooks"] == ["pre-push"]


def test_hooks_retrofit_does_not_adopt_a_platform(tmp_path):
    """#373: the git-hook verb is not the platform verb. A retrofit named
    for its hooks adopted .claude/settings.json — a repo-visible config
    the caller never asked for; a fresh init has been explicit-only since
    D60, and the retrofit path now matches."""
    _git_repo(tmp_path)
    assert plane.init(tmp_path) == 0
    assert plane.init(tmp_path, hooks=True) == 0
    assert not (tmp_path / ".claude" / "settings.json").exists()
    manifest = json.loads((tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["platforms"] == []
    assert plane.init(tmp_path, platforms=["claude"]) == 0  # explicit still works
    assert (tmp_path / ".claude" / "settings.json").exists()


def test_retrofit_respects_foreign_hook(tmp_path):
    _git_repo(tmp_path)
    assert plane.init(tmp_path) == 0
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    (hooks / "pre-push").write_text("#!/bin/sh\nmine\n", encoding="utf-8")
    assert plane.init(tmp_path, hooks=True) == 2
    assert (hooks / "pre-push").read_text(encoding="utf-8") == "#!/bin/sh\nmine\n"


def test_uninstall_warns_about_customized_files(tmp_path, capsys):
    """F5: exact reversal stays, but customized content is named first."""
    _git_repo(tmp_path)
    assert plane.init(tmp_path) == 0
    rules = tmp_path / ".gov" / "rules.md"
    rules.write_text(rules.read_text(encoding="utf-8") + "\n# MY PRECIOUS RULE\n", encoding="utf-8")
    assert plane.uninstall(tmp_path) == 1  # two-step: warns, keeps everything
    err = capsys.readouterr().err
    assert "customized" in err and ".gov/rules.md" in err
    assert rules.exists()
    assert plane.uninstall(tmp_path, force=True) == 0
    assert not rules.exists()  # reversal semantics unchanged (D10)


def test_uninstall_twostep_requires_force(tmp_path, capsys):
    """F6: customized files → first run deletes nothing; --force proceeds."""
    _git_repo(tmp_path)
    assert plane.init(tmp_path) == 0
    rules = tmp_path / ".gov" / "rules.md"
    rules.write_text(rules.read_text(encoding="utf-8") + "\n# MY PRECIOUS RULE\n", encoding="utf-8")
    assert plane.uninstall(tmp_path) == 1  # warns, deletes NOTHING
    assert rules.exists()
    assert (tmp_path / "gates.json").exists()
    err = capsys.readouterr().err
    assert "nothing has been deleted" in err and "--force" in err
    assert plane.uninstall(tmp_path, force=True) == 0
    assert not rules.exists()
    assert not (tmp_path / "gates.json").exists()


def test_uninstall_without_customization_is_one_step(tmp_path):
    _git_repo(tmp_path)
    assert plane.init(tmp_path) == 0
    assert plane.uninstall(tmp_path) == 0  # no warning, no --force needed


def test_upgrade_report_sees_drift_never_writes(tmp_path, capsys):
    """Wish 8: --upgrade diffs templates vs local, changes nothing."""
    _git_repo(tmp_path)
    assert plane.init(tmp_path) == 0
    rules = tmp_path / ".gov" / "rules.md"
    before = rules.read_text(encoding="utf-8")
    # simulate radiant: a project rule appended + an older init version
    rules.write_text(before + "\n## 8. Project rule (custom)\ncustom content\n", encoding="utf-8")
    manifest = json.loads((tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8"))
    manifest["version"] = "0.6.5"
    manifest.pop("templates", None)  # a 0.6.5-era manifest has no hashes
    (tmp_path / ".gov" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    # and a template addition the old init never created
    (tmp_path / ".gov" / "rejections" / "README.md").unlink()

    assert plane.init(tmp_path, upgrade=True) == 0
    out = capsys.readouterr().out
    assert "nothing is changed by this report" in out
    assert "DIFFERS (customized locally and/or template evolved since v0.6.5 (no adoption hash recorded))" in out
    assert "shipped-template/.gov/rules.md" in out
    assert "+## 8. Project rule (custom)" in out  # the diff shows the customization
    assert "rejections/README.md" in out and "MISSING" in out
    # never writes:
    assert rules.read_text(encoding="utf-8").endswith("custom content\n")
    assert not (tmp_path / ".gov" / "rejections" / "README.md").exists()
    assert "safe to refresh" not in out  # drift exists


def test_preview_on_an_uninitialized_project_refuses_and_writes_nothing(
        tmp_path, capsys):
    """`--preview` promises "show what would land, write nothing", and the
    fresh-init path ignored it: the flag fell through and wrote the whole
    plane — thirteen files — reported as a preview. It refuses now; the
    composition check names the real rule first (preview rides with
    --adopt), the state check names the missing manifest second."""
    assert plane.init(tmp_path, preview=True) == 2
    err = capsys.readouterr().err
    assert "--preview rides with --adopt" in err
    assert list(tmp_path.iterdir()) == [], "a refused preview left files"


def test_bare_preview_on_an_initialized_project_refuses(tmp_path, capsys):
    """The review blocker: on an initialized project a bare `--preview`
    answered "already initialized", exit 0 — the flag silently dropped
    one branch over from where #235 fixed it."""
    assert plane.init(tmp_path) == 0
    capsys.readouterr()
    assert plane.init(tmp_path, preview=True) == 2
    assert "--preview rides with --adopt" in capsys.readouterr().err
    assert (tmp_path / ".gov" / "manifest.json").exists(), \
        "the refused preview disturbed the initialized project"


def test_upgrade_with_preview_refuses(tmp_path, capsys):
    """`--upgrade --preview` ran the report as if --preview existed; the
    upgrade report is already read-only, and a silently ignored modifier
    is a lie about what ran."""
    assert plane.init(tmp_path) == 0
    capsys.readouterr()
    assert plane.init(tmp_path, upgrade=True, preview=True) == 2
    assert "--preview rides with --adopt" in capsys.readouterr().err


def test_preset_with_preview_refuses(tmp_path, capsys):
    """`--preset X --preview` applied the preset with the flag dropped."""
    assert plane.init(tmp_path, preset="agent-heavy", preview=True) == 2
    assert "--preview rides with --adopt" in capsys.readouterr().err
    assert not (tmp_path / ".gov").exists(), "a refused preview wrote a plane"


def test_adopt_on_an_uninitialized_project_refuses(tmp_path, capsys):
    """`--adopt X` on a bare directory fell through to a plain fresh init
    with the adoption target quietly dropped — a fresh init already
    installs the current templates, so there is nothing to adopt into."""
    assert plane.init(tmp_path, adopt=[".gov/rejections/README.md"]) == 2
    err = capsys.readouterr().err
    assert "--adopt needs an initialized project" in err
    assert not (tmp_path / ".gov").exists(), "a refused adopt wrote a plane"


def test_upgrade_report_clean_project(tmp_path, capsys):
    _git_repo(tmp_path)
    assert plane.init(tmp_path) == 0
    assert plane.init(tmp_path, upgrade=True) == 0
    out = capsys.readouterr().out
    assert "every injected file matches the shipped templates — safe to refresh" in out


def test_upgrade_on_uninitialized_fails_loud(tmp_path, capsys):
    """The name was right and the body was not: this used to assert the
    silent full init that a "reads, never writes" flag performed on a
    project with no manifest (the deferred MEDIUM of round 5)."""
    assert plane.init(tmp_path, upgrade=True) == 2
    assert "--upgrade needs an initialized project" in capsys.readouterr().err
    assert not (tmp_path / ".gov").exists(), "a refused upgrade wrote a plane"


def test_adopt_lands_missing_never_overwrites(tmp_path, capsys):
    """Wish: new template files land; existing files are untouchable."""
    _git_repo(tmp_path)
    assert plane.init(tmp_path) == 0
    target = tmp_path / ".gov" / "rejections" / "README.md"
    target.unlink()
    assert plane.init(tmp_path, adopt=[".gov/rejections/README.md"]) == 0
    assert target.exists()  # landed
    own = b"my own convention\n"
    target.write_bytes(own)
    assert plane.init(tmp_path, adopt=[".gov/rejections/README.md"]) == 0
    assert target.read_bytes() == own  # never overwritten
    assert plane.init(tmp_path, adopt=["no/such/template"]) == 2  # fail loud
    manifest = json.loads((tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8"))
    assert ".gov/rejections/README.md" in manifest["created"]


def test_upgrade_report_marks_adoptable(tmp_path, capsys):
    _git_repo(tmp_path)
    assert plane.init(tmp_path) == 0
    (tmp_path / ".gov" / "rejections" / "README.md").unlink()
    assert plane.init(tmp_path, upgrade=True) == 0
    assert "adoptable: gov init --adopt .gov/rejections/README.md" in capsys.readouterr().out


def test_upgrade_distinguishes_upstream_moved_from_both_moved(tmp_path, capsys):
    """D34: provenance hashes answer 'did upstream move, should I re-adopt'."""
    import hashlib
    _git_repo(tmp_path)
    assert plane.init(tmp_path) == 0
    manifest_p = tmp_path / ".gov" / "manifest.json"
    manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
    assert ".gov/rules.md" in manifest["templates"]  # hashes recorded at init

    rules = tmp_path / ".gov" / "rules.md"
    # (a) upstream moved: local differs from the CURRENT template but is
    # byte-equal to what the (old, recorded) template shipped
    rules.write_text(rules.read_text(encoding="utf-8") + "\nOLD TEMPLATE TAIL\n", encoding="utf-8")
    manifest["templates"][".gov/rules.md"] = hashlib.sha256(
        rules.read_bytes()).hexdigest()
    manifest_p.write_text(json.dumps(manifest), encoding="utf-8")
    assert plane.init(tmp_path, upgrade=True) == 0
    out = capsys.readouterr().out
    assert "UPSTREAM MOVED — your copy is untouched" in out
    # (b) safe re-adopt: --adopt replaces the uncustomized copy
    assert plane.init(tmp_path, adopt=[".gov/rules.md"]) == 0
    out = capsys.readouterr().out
    assert "re-adopted .gov/rules.md (your copy was uncustomized;" in out
    assert "manifest updated" in out  # side effects disclosed (#open-2)
    m2 = json.loads(manifest_p.read_text(encoding="utf-8"))
    assert m2["templates"][".gov/rules.md"] != "0" * 64  # hash refreshed
    # (c) both moved: local customized AND recorded != current
    rules.write_text(rules.read_text(encoding="utf-8") + "\n# MY RULE\n", encoding="utf-8")
    manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
    manifest["templates"][".gov/rules.md"] = "0" * 64
    manifest_p.write_text(json.dumps(manifest), encoding="utf-8")
    assert plane.init(tmp_path, upgrade=True) == 0
    assert "BOTH MOVED" in capsys.readouterr().out


def test_adopt_preview_writes_nothing(tmp_path, capsys):
    _git_repo(tmp_path)
    assert plane.init(tmp_path) == 0
    target = tmp_path / ".gov" / "rejections" / "README.md"
    target.unlink()
    manifest_text_before = (tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8")
    assert plane.init(tmp_path, adopt=[".gov/rejections/README.md"],
                    preview=True) == 0
    out = capsys.readouterr().out
    assert "would create .gov/rejections/README.md" in out
    assert "preview only — nothing was written" in out
    assert not target.exists()  # nothing landed
    manifest = json.loads((tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest == json.loads(manifest_text_before)  # manifest untouched


def test_adopt_new_merges_missing_shipped_gates(tmp_path, capsys):
    """#108/D39: additive adoption — new shipped gates land by id, local
    gates preserved, result passes schema validation."""
    _git_repo(tmp_path)
    assert plane.init(tmp_path) == 0
    tpl = json.loads((Path(__file__).parent.parent / "gov" / "templates"
                      / "gates.json").read_text(encoding="utf-8"))
    shipped_ids = {g["id"] for g in tpl["gates"]}
    assert "conflict-markers" in shipped_ids  # the 0.15.0 case from #108

    gates_path = tmp_path / "gates.json"
    cfg = json.loads(gates_path.read_text(encoding="utf-8"))
    local_gate = {"id": "local-gate", "label": "mine",
                  "command": ["gov", "run-local"]}
    cfg["gates"] = [g for g in cfg["gates"] if g["id"] != "conflict-markers"]
    cfg["gates"].append(local_gate)
    cfg["modes"]["all"] = [m for m in cfg["modes"]["all"]
                           if m != "conflict-markers"] + ["local-gate"]
    gates_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    manifest_before = (tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8")

    assert plane.init(tmp_path, adopt_new="gates.json") == 0
    out = capsys.readouterr().out
    assert "added 1 shipped gate(s): conflict-markers" in out
    assert "preserved untouched" in out
    assert "schema validation" in out

    merged = json.loads(gates_path.read_text(encoding="utf-8"))
    ids = [g["id"] for g in merged["gates"]]
    assert ids.count("conflict-markers") == 1
    assert "local-gate" in ids
    # every local gate byte-identical (same object, same serialization)
    assert local_gate in merged["gates"]
    for g in cfg["gates"]:
        assert g in merged["gates"]
    # modes extended with the newly adopted id only
    assert "conflict-markers" in merged["modes"]["all"]
    assert merged["modes"]["all"].count("local-gate") == 1
    # merged result validates under the real schema loader
    from gov import gates as gates_mod
    gates_mod.load_config(str(gates_path))
    # manifest untouched — the file stays customized, no false provenance
    assert (tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8") == manifest_before


def test_adopt_new_nothing_to_add(tmp_path, capsys):
    _git_repo(tmp_path)
    assert plane.init(tmp_path) == 0
    before = (tmp_path / "gates.json").read_text(encoding="utf-8")
    assert plane.init(tmp_path, adopt_new="gates.json") == 0
    out = capsys.readouterr().out
    assert "nothing to add" in out
    assert (tmp_path / "gates.json").read_text(encoding="utf-8") == before


def test_adopt_new_refuses_non_additive_drift(tmp_path, capsys):
    """A shared gate id whose content differs is refused loudly; the
    local file is not touched."""
    _git_repo(tmp_path)
    assert plane.init(tmp_path) == 0
    gates_path = tmp_path / "gates.json"
    cfg = json.loads(gates_path.read_text(encoding="utf-8"))
    for g in cfg["gates"]:
        if g["id"] == "notes":
            g["label"] = "my own notes label"  # local customization
    gates_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    before = gates_path.read_text(encoding="utf-8")
    assert plane.init(tmp_path, adopt_new="gates.json") == 2
    err = capsys.readouterr().err
    assert "refused — non-additive drift" in err
    assert "notes" in err
    assert gates_path.read_text(encoding="utf-8") == before  # nothing written


def test_adopt_new_fail_loud_edges(tmp_path, capsys):
    _git_repo(tmp_path)
    assert plane.init(tmp_path) == 0
    # unsupported target
    assert plane.init(tmp_path, adopt_new="rules.md") == 2
    assert "supports 'gates.json' only" in capsys.readouterr().err
    # uninitialized project
    (tmp_path / ".gov" / "manifest.json").unlink()
    assert plane.init(tmp_path, adopt_new="gates.json") == 2
    assert "needs an initialized project" in capsys.readouterr().err


@pytest.fixture
def cwd_restored(monkeypatch):
    """-C chdirs the PROCESS by design; restore the caller's cwd after."""
    monkeypatch.chdir(Path.cwd())


def test_cd_flag_targets_another_tree(tmp_path, capsys, cwd_restored):
    """#121: `gov -C <path> <cmd>` acts on that tree and names the root."""
    import subprocess
    wt = tmp_path / "wt-x"
    (wt / "sub").mkdir(parents=True)
    for cmd in (
        ["git", "init", "-q", "."],
        ["git", "config", "user.email", "t@t"],
        ["git", "config", "user.name", "t"],
    ):
        subprocess.run(cmd, cwd=wt, check=True)
    # -C into a SUBDIRECTORY: the announcement still names the work-tree
    # root — exactly what cd + root anchoring would resolve to.
    assert cli.main(["-C", str(wt / "sub"), "init", "--project", "."]) == 0
    err = capsys.readouterr().err
    # git prints the toplevel with forward slashes even on Windows; the
    # announcement quotes it verbatim - accept either separator (#168).
    assert (f"gov: targeting {wt}" in err
            or f"gov: targeting {wt.as_posix()}" in err)
    # init resolves --project against the new cwd (it does not anchor to
    # the git root); the root-relative tools (run/verify-*/doctor) do.
    assert (wt / "sub" / ".gov" / "manifest.json").exists()


def test_cd_flag_chainable_git_semantics(tmp_path, capsys, cwd_restored):
    wt = tmp_path / "wt-y"
    (wt / "a" / "b").mkdir(parents=True)
    assert cli.main(["-C", str(wt), "-C", "a", "-C", "b",
                     "init", "--project", "."]) == 0
    err = capsys.readouterr().err
    assert f"gov: targeting {tmp_path / 'wt-y' / 'a' / 'b'}" in err
    assert (wt / "a" / "b" / ".gov" / "manifest.json").exists()


def test_cd_flag_nonexistent_path_fails_loud(tmp_path, capsys, cwd_restored):
    assert cli.main(["-C", str(tmp_path / "nope"), "doctor"]) == 2
    assert "no such directory" in capsys.readouterr().err


def test_cd_flag_requires_path(tmp_path, capsys, cwd_restored):
    assert cli.main(["-C"]) == 2
    assert "requires a directory path" in capsys.readouterr().err


def test_init_preserves_existing_gitignore(tmp_path):
    """H-1: init appends its ignore line to an existing .gitignore — the
    rewrite used to destroy the project's own entries."""
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("node_modules/\n*.pyc\ndist/", encoding="utf-8")
    assert plane.init(tmp_path) == 0
    lines = gitignore.read_text(encoding="utf-8").splitlines()
    assert lines[:3] == ["node_modules/", "*.pyc", "dist/"]
    # #325/#353: the runtime lock artifacts are ignored too — the task
    # allocator's flock anchor and the persistent decision lock.
    assert lines[-2:] == [".gov/tasks/.new.lock", "docs/.decision.lock"]
    assert ".gov/history/" in lines
    assert lines.count(".gov/history/") == 1  # appended once, idempotent


def test_init_gitignore_edges_survive(tmp_path):
    """H-1 edges: a byte-level append keeps CRLF endings intact, and an
    empty file gains the line without a leading blank."""
    crlf = tmp_path / "crlf"
    crlf.mkdir()
    (crlf / ".gitignore").write_bytes(b"node_modules/\r\n*.pyc\r\n")
    assert plane.init(crlf) == 0
    assert ((crlf / ".gitignore").read_bytes()
            == b"node_modules/\r\n*.pyc\r\n.gov/history/\n"
               b".gov/tasks/.new.lock\ndocs/.decision.lock\n")
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / ".gitignore").write_bytes(b"")
    assert plane.init(empty) == 0
    assert (empty / ".gitignore").read_bytes() \
            == b".gov/history/\n.gov/tasks/.new.lock\ndocs/.decision.lock\n"


def test_uninstall_removes_gov_hooks_at_resolved_path(tmp_path):
    """H-2: uninstall removes the hooks where they actually run
    (core.hooksPath), not just .git/hooks — a surviving hook kept
    invoking the uninstalled gov and hung every push."""
    import subprocess
    _git_repo(tmp_path)
    subprocess.run(["git", "config", "core.hooksPath", ".githooks"],
                   cwd=tmp_path, check=True)
    assert plane.init(tmp_path, hooks=True) == 0
    hook = tmp_path / ".githooks" / "pre-push"
    assert hook.exists()  # installed where hooks actually run
    assert plane.uninstall(tmp_path) == 0
    assert not hook.exists()
    assert not (tmp_path / ".gov").exists()  # the rest reversed as usual


def test_uninstall_never_deletes_foreign_hooks(tmp_path, capsys):
    """H-2: a manifest-listed hook is only unlinked when it still is a
    gov hook — a foreign script is named and left in place."""
    _git_repo(tmp_path)
    assert plane.init(tmp_path, hooks=True) == 0
    hook = tmp_path / ".git" / "hooks" / "pre-push"
    foreign = "#!/bin/sh\necho my own hook\n"
    hook.write_text(foreign, encoding="utf-8")  # replaced after init
    assert plane.uninstall(tmp_path) == 0
    assert hook.exists()
    assert hook.read_text(encoding="utf-8") == foreign
    assert "not a gov hook" in capsys.readouterr().err


def test_uninstall_preserves_customized_decision_log(tmp_path, capsys):
    """H-4: the decisions log is project memory, not a template copy —
    customized content survives uninstall (it used to be unlinked
    silently), --force included."""
    import subprocess
    _git_repo(tmp_path)
    assert plane.init(tmp_path) == 0
    log = tmp_path / "docs" / "decisions.md"
    log.write_text(
        log.read_text(encoding="utf-8")
        + "\n## D1 — Keep the gate\n\n- **Decision**: the gate stays.\n"
          "- **Alternatives**: removing it (drift returns silently).\n",
        encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "log a decision"],
                   cwd=tmp_path, check=True)
    assert plane.uninstall(tmp_path, force=True) == 0
    assert log.exists()
    assert "the gate stays" in log.read_text(encoding="utf-8")
    assert not (tmp_path / ".gov").exists()  # the plane itself still goes
    err = capsys.readouterr().err
    assert "docs/decisions.md" in err and "leaving it" in err


def test_copy_is_atomic_on_crash(tmp_path):
    """H-3: _copy lands via temp+replace — byte-exact content, no .tmp
    residue, no half-written stub a re-run init would adopt."""
    dest = tmp_path / "gates.json"
    template = plane.TEMPLATES.joinpath("gates.json")
    plane._copy(template, dest)
    assert dest.read_bytes() == template.read_bytes()
    assert list(tmp_path.glob("*.tmp")) == []
    if sys.platform != "win32":  # mode bits are a POSIX story (#168)
        assert dest.stat().st_mode & 0o044  # not mkstemp's 0600


def test_add_ons_preserves_manifest_keys(tmp_path):
    """#14: an add-on retrofit merges into the manifest — the "templates"
    adoption-hash record (`init --adopt`, D34) must survive, not be
    dropped by a three-key rewrite."""
    assert plane.init(tmp_path) == 0
    manifest_p = tmp_path / ".gov" / "manifest.json"
    manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
    manifest["templates"] = {".gov/rules.md": "deadbeef"}
    manifest_p.write_text(json.dumps(manifest), encoding="utf-8")
    assert plane._add_ons(tmp_path, manifest_p, hooks=False, ci=False) == 0
    merged = json.loads(manifest_p.read_text(encoding="utf-8"))
    assert merged["templates"] == {".gov/rules.md": "deadbeef"}
    assert merged["version"] == __version__
    assert "gates.json" in merged["created"]  # known keys still updated


# --- N10/N13: init refuses to follow user-planted symlinks ------------

def test_init_refuses_a_symlinked_gov_dir(tmp_path, capsys):
    """A .gov symlink re-points every state write — ledgers, seals,
    receipts — at a path outside the repository. Nothing follows it."""
    import os
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "link-target-gov").symlink_to(outside, target_is_directory=True)
    # place the symlink AT .gov
    os.rename(tmp_path / "link-target-gov", tmp_path / ".gov")
    assert plane.init(tmp_path) == 2
    err = capsys.readouterr().err
    assert ".gov" in err and "symlink" in err
    assert list(outside.iterdir()) == [], "a refused init wrote through"


def test_init_refuses_a_symlinked_gitignore(tmp_path, capsys):
    """N13/N10: a stow/dotfiles .gitignore link is neither read THROUGH
    (external content copied into the tracked file) nor silently
    replaced by a plain file — the adoption refuses, naming the link."""
    real = tmp_path / "my-dotfiles-gitignore"
    real.write_text("node_modules/\n", encoding="utf-8")
    (tmp_path / ".gitignore").symlink_to(real)
    assert plane.init(tmp_path) == 2
    err = capsys.readouterr().err
    assert ".gitignore" in err and "symlink" in err
    # the link survives, still pointing at the managed file
    assert (tmp_path / ".gitignore").is_symlink()
    assert real.read_text(encoding="utf-8") == "node_modules/\n"
    assert not (tmp_path / "gates.json").exists(), "a refused init half-wrote"


def test_uninstall_refuses_to_edit_a_symlinked_agents_md(tmp_path, capsys):
    """N10: the reference line lives in the file the link points at —
    removing it through the link is an edit to a file the plane does
    not own. Named, exit 1, the operator decides."""
    _git_repo(tmp_path)
    assert plane.init(tmp_path) == 0
    real = tmp_path / "dotfiles"
    real.mkdir()
    (real / "AGENTS.md").write_text(
        "my rules\n<!-- gov:rules --> Read .gov/rules.md and follow it "
        "before starting work.\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").unlink()
    (tmp_path / "AGENTS.md").symlink_to(real / "AGENTS.md")
    capsys.readouterr()
    assert plane.uninstall(tmp_path) == 1
    err = capsys.readouterr().err
    assert "AGENTS.md" in err and "symlink" in err
    # the managed file keeps both lines — untouched
    assert "gov:rules" in (real / "AGENTS.md").read_text(encoding="utf-8")


def test_init_output_tells_the_operator_to_commit(tmp_path, capsys):
    """#251: every recovery path assumes the generated files are in git —
    say so before the operator's first mistake, not after."""
    assert plane.init(tmp_path) == 0
    out = capsys.readouterr().out
    assert "commit the generated governance files now" in out


def test_init_writes_the_pairing_config_rules_md_points_at(tmp_path):
    """#367: rules.md calls `.gov/pairing.json` the home of the naming
    conventions and gates.json lists it in two gates' `paths` — but
    nothing created it, so the reference was false for every fresh
    adopter, and creating it by hand in a sealed repo cost a recorded
    re-baseline for content that equals the defaults it overrides."""
    import json as _json
    from gov import verify_translation_pairing as vtp
    assert plane.init(tmp_path) == 0
    cfg = tmp_path / ".gov" / "pairing.json"
    assert cfg.is_file(), "rules.md points at this file; init must write it"
    written = _json.loads(cfg.read_text(encoding="utf-8"))
    assert written == vtp.DEFAULT_CONFIG, (
        "the written file must BE the defaults — an explicit config that "
        "changed behavior would be a silent re-typing of the plane")


def test_adopt_writes_the_pairing_config_where_it_is_missing(tmp_path,
                                                            capsys):
    assert plane.init(tmp_path) == 0
    (tmp_path / ".gov" / "pairing.json").unlink()
    assert plane.init(tmp_path, adopt=[".gov/pairing.json"]) == 0
    out = capsys.readouterr().out
    assert ".gov/pairing.json" in out
    assert (tmp_path / ".gov" / "pairing.json").is_file()
