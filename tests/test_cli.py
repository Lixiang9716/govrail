import json
import sys
from pathlib import Path

from gov import __version__, cli


def test_init_creates_files(tmp_path):
    assert cli.init(tmp_path) == 0
    assert (tmp_path / ".gov" / "rules.md").exists()
    assert (tmp_path / ".gov" / "manifest.json").exists()
    assert (tmp_path / "gates.json").exists()
    assert (tmp_path / ".agents" / "notes" / "README.md").exists()
    assert (tmp_path / "AGENTS.md").exists()


def test_init_template_is_advisory_first(tmp_path):
    """A fresh install must not go red on the first run (P0 defect 3)."""
    assert cli.init(tmp_path) == 0
    cfg = json.loads((tmp_path / "gates.json").read_text(encoding="utf-8"))
    assert cfg["defaultMode"] == "all"
    pairing = [g for g in cfg["gates"] if g["id"] == "pairing"][0]
    assert pairing["allowFailure"] is True


def test_init_manifest_records_cli_version(tmp_path):
    assert cli.init(tmp_path) == 0
    manifest = json.loads((tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == __version__


def test_init_idempotent(tmp_path):
    assert cli.init(tmp_path) == 0
    before = (tmp_path / "gates.json").read_text(encoding="utf-8")
    assert cli.init(tmp_path) == 0
    assert (tmp_path / "gates.json").read_text(encoding="utf-8") == before


def test_uninstall_reverses(tmp_path):
    cli.init(tmp_path)
    (tmp_path / "keep.txt").write_text("keep", encoding="utf-8")
    assert cli.uninstall(tmp_path) == 0
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
    assert cli.init(tmp_path, hooks=True, ci=True) == 0
    assert (tmp_path / ".gov" / "hooks" / "pre-push").exists()
    git_hook = tmp_path / ".git" / "hooks" / "pre-push"
    assert git_hook.exists()
    if sys.platform != "win32":  # X_OK is meaningless on Windows (#168);
        # git-for-windows executes hooks regardless of the FS mode bit
        assert git_hook.stat().st_mode & 0o111  # executable
    workflow = tmp_path / ".github" / "workflows" / "gov.yml"
    assert workflow.exists()
    assert cli.init(tmp_path, hooks=True, ci=True) == 0  # idempotent re-run
    assert cli.uninstall(tmp_path) == 0
    assert not git_hook.exists()
    assert not workflow.exists()
    assert not (tmp_path / "gates.json").exists()


def test_init_hooks_refuses_foreign_hook(tmp_path):
    _git_repo(tmp_path)
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    (hooks / "pre-push").write_text("#!/bin/sh\nmy own hook\n", encoding="utf-8")
    assert cli.init(tmp_path, hooks=True) == 2
    assert (hooks / "pre-push").read_text(encoding="utf-8").startswith("#!/bin/sh\nmy own")
    assert not (tmp_path / "gates.json").exists()  # no half-initialized state


def test_init_hooks_needs_git(tmp_path):
    assert cli.init(tmp_path, hooks=True) == 2
    assert not (tmp_path / "gates.json").exists()


def test_init_ci_keeps_existing_workflow(tmp_path):
    wf = tmp_path / ".github" / "workflows" / "gov.yml"
    wf.parent.mkdir(parents=True, exist_ok=True)
    wf.write_text("mine: yes\n", encoding="utf-8")
    assert cli.init(tmp_path, ci=True) == 0
    assert wf.read_text(encoding="utf-8") == "mine: yes\n"


def test_init_template_modes_note_presence_and_governance(tmp_path):
    assert cli.init(tmp_path) == 0
    cfg = json.loads((tmp_path / "gates.json").read_text(encoding="utf-8"))
    ids = [g["id"] for g in cfg["gates"]]
    assert "note-presence" in ids
    # D24: the full matrix includes the tools' own smoke test — CI runs it
    # from the first push (a fresh install's unpinned govrail is watched).
    assert "self-test" in cfg["modes"]["all"]
    assert cfg["modes"]["governance"] == ["self-test"]  # shortcut stays


def test_init_injects_skills(tmp_path):
    assert cli.init(tmp_path) == 0
    for name in cli.SKILLS:
        p = tmp_path / ".agents" / "skills" / name / "SKILL.md"
        assert p.exists(), name
    manifest = json.loads((tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8"))
    assert ".agents/skills/recall-first/SKILL.md" in manifest["created"]


def test_init_never_overwrites_own_skill(tmp_path):
    own = tmp_path / ".agents" / "skills" / "code-review" / "SKILL.md"
    own.parent.mkdir(parents=True)
    own.write_text("my own review convention\n", encoding="utf-8")
    assert cli.init(tmp_path) == 0
    assert own.read_text(encoding="utf-8") == "my own review convention\n"
    manifest = json.loads((tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8"))
    assert ".agents/skills/code-review/SKILL.md" not in manifest["created"]


def test_uninstall_removes_injected_skills(tmp_path):
    cli.init(tmp_path)
    assert cli.uninstall(tmp_path) == 0
    assert not (tmp_path / ".agents" / "skills").exists()


def test_templates_match_live_skills():
    """The shipped templates and this repo's live skills are one source."""
    root = Path(__file__).resolve().parent.parent
    for name in cli.SKILLS:
        shipped = root / "gov" / "templates" / "skills" / name / "SKILL.md"
        live = root / ".agents" / "skills" / name / "SKILL.md"
        assert shipped.read_text(encoding="utf-8") == live.read_text(encoding="utf-8"), (
            f"{name}: template and live skill drifted — align them"
        )


def test_init_next_steps_match_reality(tmp_path, capsys):
    """No paired docs → no baseline advice (the old step 2 exit-2'd)."""
    assert cli.init(tmp_path) == 0
    out = capsys.readouterr().out
    assert "no paired docs detected" in out
    assert "verify-pairing --write" not in out


def test_init_next_steps_with_docs(tmp_path, capsys):
    (tmp_path / "README.md").write_text("# x\n", encoding="utf-8")
    assert cli.init(tmp_path) == 0
    out = capsys.readouterr().out
    assert "verify-pairing --write" in out
    assert "no paired docs detected" not in out


def test_hooks_retrofit_on_initialized_project(tmp_path):
    """F5: --hooks works incrementally; customizations stay untouched."""
    _git_repo(tmp_path)
    assert cli.init(tmp_path) == 0
    rules = tmp_path / ".gov" / "rules.md"
    rules.write_text(rules.read_text(encoding="utf-8") + "\n# CUSTOM RULE\n", encoding="utf-8")
    gates = tmp_path / "gates.json"
    customized = gates.read_text(encoding="utf-8").replace("note format", "CUSTOM LABEL")
    gates.write_text(customized, encoding="utf-8")
    assert cli.init(tmp_path, hooks=True, ci=True) == 0
    assert (tmp_path / ".git" / "hooks" / "pre-push").exists()
    assert (tmp_path / ".github" / "workflows" / "gov.yml").exists()
    assert "CUSTOM RULE" in rules.read_text(encoding="utf-8")      # untouched
    assert "CUSTOM LABEL" in gates.read_text(encoding="utf-8")     # untouched
    manifest = json.loads((tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8"))
    assert "pre-push" in manifest["gitHooks"]
    assert ".github/workflows/gov.yml" in manifest["created"]


def test_retrofit_is_idempotent(tmp_path):
    _git_repo(tmp_path)
    assert cli.init(tmp_path, hooks=True) == 0
    assert cli.init(tmp_path, hooks=True) == 0  # re-run: no-op, no duplicate
    manifest = json.loads((tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["gitHooks"] == ["pre-push"]


def test_retrofit_respects_foreign_hook(tmp_path):
    _git_repo(tmp_path)
    assert cli.init(tmp_path) == 0
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    (hooks / "pre-push").write_text("#!/bin/sh\nmine\n", encoding="utf-8")
    assert cli.init(tmp_path, hooks=True) == 2
    assert (hooks / "pre-push").read_text(encoding="utf-8") == "#!/bin/sh\nmine\n"


def test_uninstall_warns_about_customized_files(tmp_path, capsys):
    """F5: exact reversal stays, but customized content is named first."""
    _git_repo(tmp_path)
    assert cli.init(tmp_path) == 0
    rules = tmp_path / ".gov" / "rules.md"
    rules.write_text(rules.read_text(encoding="utf-8") + "\n# MY PRECIOUS RULE\n", encoding="utf-8")
    assert cli.uninstall(tmp_path) == 1  # two-step: warns, keeps everything
    err = capsys.readouterr().err
    assert "customized" in err and ".gov/rules.md" in err
    assert rules.exists()
    assert cli.uninstall(tmp_path, force=True) == 0
    assert not rules.exists()  # reversal semantics unchanged (D10)


def test_uninstall_twostep_requires_force(tmp_path, capsys):
    """F6: customized files → first run deletes nothing; --force proceeds."""
    _git_repo(tmp_path)
    assert cli.init(tmp_path) == 0
    rules = tmp_path / ".gov" / "rules.md"
    rules.write_text(rules.read_text(encoding="utf-8") + "\n# MY PRECIOUS RULE\n", encoding="utf-8")
    assert cli.uninstall(tmp_path) == 1  # warns, deletes NOTHING
    assert rules.exists()
    assert (tmp_path / "gates.json").exists()
    err = capsys.readouterr().err
    assert "nothing has been deleted" in err and "--force" in err
    assert cli.uninstall(tmp_path, force=True) == 0
    assert not rules.exists()
    assert not (tmp_path / "gates.json").exists()


def test_uninstall_without_customization_is_one_step(tmp_path):
    _git_repo(tmp_path)
    assert cli.init(tmp_path) == 0
    assert cli.uninstall(tmp_path) == 0  # no warning, no --force needed


def test_upgrade_report_sees_drift_never_writes(tmp_path, capsys):
    """Wish 8: --upgrade diffs templates vs local, changes nothing."""
    _git_repo(tmp_path)
    assert cli.init(tmp_path) == 0
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

    assert cli.init(tmp_path, upgrade=True) == 0
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


def test_upgrade_report_clean_project(tmp_path, capsys):
    _git_repo(tmp_path)
    assert cli.init(tmp_path) == 0
    assert cli.init(tmp_path, upgrade=True) == 0
    out = capsys.readouterr().out
    assert "every injected file matches the shipped templates — safe to refresh" in out


def test_upgrade_on_uninitialized_fails_loud(tmp_path):
    assert cli.init(tmp_path, upgrade=True) == 0  # no manifest yet: normal init path
    assert (tmp_path / ".gov" / "manifest.json").exists()


def test_adopt_lands_missing_never_overwrites(tmp_path, capsys):
    """Wish: new template files land; existing files are untouchable."""
    _git_repo(tmp_path)
    assert cli.init(tmp_path) == 0
    target = tmp_path / ".gov" / "rejections" / "README.md"
    target.unlink()
    assert cli.init(tmp_path, adopt=[".gov/rejections/README.md"]) == 0
    assert target.exists()  # landed
    own = b"my own convention\n"
    target.write_bytes(own)
    assert cli.init(tmp_path, adopt=[".gov/rejections/README.md"]) == 0
    assert target.read_bytes() == own  # never overwritten
    assert cli.init(tmp_path, adopt=["no/such/template"]) == 2  # fail loud
    manifest = json.loads((tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8"))
    assert ".gov/rejections/README.md" in manifest["created"]


def test_upgrade_report_marks_adoptable(tmp_path, capsys):
    _git_repo(tmp_path)
    assert cli.init(tmp_path) == 0
    (tmp_path / ".gov" / "rejections" / "README.md").unlink()
    assert cli.init(tmp_path, upgrade=True) == 0
    assert "adoptable: gov init --adopt .gov/rejections/README.md" in capsys.readouterr().out


def test_upgrade_distinguishes_upstream_moved_from_both_moved(tmp_path, capsys):
    """D34: provenance hashes answer 'did upstream move, should I re-adopt'."""
    import hashlib
    _git_repo(tmp_path)
    assert cli.init(tmp_path) == 0
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
    assert cli.init(tmp_path, upgrade=True) == 0
    out = capsys.readouterr().out
    assert "UPSTREAM MOVED — your copy is untouched" in out
    # (b) safe re-adopt: --adopt replaces the uncustomized copy
    assert cli.init(tmp_path, adopt=[".gov/rules.md"]) == 0
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
    assert cli.init(tmp_path, upgrade=True) == 0
    assert "BOTH MOVED" in capsys.readouterr().out


def test_adopt_preview_writes_nothing(tmp_path, capsys):
    _git_repo(tmp_path)
    assert cli.init(tmp_path) == 0
    target = tmp_path / ".gov" / "rejections" / "README.md"
    target.unlink()
    manifest_text_before = (tmp_path / ".gov" / "manifest.json").read_text(encoding="utf-8")
    assert cli.init(tmp_path, adopt=[".gov/rejections/README.md"],
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
    assert cli.init(tmp_path) == 0
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

    assert cli.init(tmp_path, adopt_new="gates.json") == 0
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
    assert cli.init(tmp_path) == 0
    before = (tmp_path / "gates.json").read_text(encoding="utf-8")
    assert cli.init(tmp_path, adopt_new="gates.json") == 0
    out = capsys.readouterr().out
    assert "nothing to add" in out
    assert (tmp_path / "gates.json").read_text(encoding="utf-8") == before


def test_adopt_new_refuses_non_additive_drift(tmp_path, capsys):
    """A shared gate id whose content differs is refused loudly; the
    local file is not touched."""
    _git_repo(tmp_path)
    assert cli.init(tmp_path) == 0
    gates_path = tmp_path / "gates.json"
    cfg = json.loads(gates_path.read_text(encoding="utf-8"))
    for g in cfg["gates"]:
        if g["id"] == "notes":
            g["label"] = "my own notes label"  # local customization
    gates_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    before = gates_path.read_text(encoding="utf-8")
    assert cli.init(tmp_path, adopt_new="gates.json") == 2
    err = capsys.readouterr().err
    assert "refused — non-additive drift" in err
    assert "notes" in err
    assert gates_path.read_text(encoding="utf-8") == before  # nothing written


def test_adopt_new_fail_loud_edges(tmp_path, capsys):
    _git_repo(tmp_path)
    assert cli.init(tmp_path) == 0
    # unsupported target
    assert cli.init(tmp_path, adopt_new="rules.md") == 2
    assert "supports 'gates.json' only" in capsys.readouterr().err
    # uninitialized project
    (tmp_path / ".gov" / "manifest.json").unlink()
    assert cli.init(tmp_path, adopt_new="gates.json") == 2
    assert "needs an initialized project" in capsys.readouterr().err


def test_cd_flag_targets_another_tree(tmp_path, capsys):
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


def test_cd_flag_chainable_git_semantics(tmp_path, capsys):
    wt = tmp_path / "wt-y"
    (wt / "a" / "b").mkdir(parents=True)
    assert cli.main(["-C", str(wt), "-C", "a", "-C", "b",
                     "init", "--project", "."]) == 0
    err = capsys.readouterr().err
    assert f"gov: targeting {tmp_path / 'wt-y' / 'a' / 'b'}" in err
    assert (wt / "a" / "b" / ".gov" / "manifest.json").exists()


def test_cd_flag_nonexistent_path_fails_loud(tmp_path, capsys):
    assert cli.main(["-C", str(tmp_path / "nope"), "doctor"]) == 2
    assert "no such directory" in capsys.readouterr().err


def test_cd_flag_requires_path(tmp_path, capsys):
    assert cli.main(["-C"]) == 2
    assert "requires a directory path" in capsys.readouterr().err
