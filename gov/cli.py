#!/usr/bin/env python3
"""gov — install, uninstall, run, and self-test the governance plane.

Subcommands delegate to the modules in this package; ``init`` injects the
templates shipped as package data, and ``uninstall`` reverses it exactly via
the ``.gov/manifest.json`` it wrote. ``init --hooks`` additionally installs a
``pre-push`` hook that runs the gate DAG, and ``init --ci`` generates a
GitHub Actions workflow — both recorded in the manifest and reversed by
``uninstall``. ``init --hooks --pre-commit`` additionally installs the
optional pre-commit hook: the cheap content gates (pairing sidecar
freshness, conflict markers) on the staged files only, so pairing drift
surfaces at ``git commit`` instead of one stage later at push (#110).
``init --preset <name>`` applies a typed adoption bundle right after
init (D53); the ``preset`` subcommand lists, shows, and applies the
shipped presets.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path
from typing import Any

from . import archive_notes, audit_notes, change_scope, gates, locks, recall, review
from . import doctor, note, presets, receipt, self_test, trend, whatsnew
from . import decision, task, verify_archive, verify_decisions, verify_doc_sync
from . import verify_conflict_markers
from . import verify_note_presence
from . import verify_notes, verify_rubric
from . import verify_translation_pairing
from . import __version__

TEMPLATES = files("gov.templates")
REFERENCE_MARKER = "<!-- gov:rules -->"
REFERENCE_LINE = (
    f"{REFERENCE_MARKER} Read .gov/rules.md and follow it before starting work."
)
HOOK_MARKER = "# govrail:"
# The agent skills that travel with the plane: injected like rules.md,
# create-if-missing, never overwriting a project's own skill.
SKILLS = ("recall-first", "pre-push-checks", "code-review", "archive-agent-notes")


def _copy(source, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as f:
        dest.write_bytes(f.read())


def _remove_empty_dirs(root: Path) -> None:
    """Remove empty parent dirs, deepest first, stopping at the first non-empty."""
    p = root
    while p != p.parent:
        try:
            p.rmdir()
        except OSError:
            break
        p = p.parent


def _hook_conflict(project: Path, name: str = "pre-push") -> bool:
    """True when .git/hooks/<name> exists and is not a gov hook."""
    git_hook = project / ".git" / "hooks" / name
    if not git_hook.exists():
        return False
    try:
        existing = git_hook.read_text(encoding="utf-8")
    except OSError:
        return True
    return HOOK_MARKER not in existing


def _install_hook(project: Path, name: str = "pre-push") -> None:
    """Write .gov/hooks/<name> and wire it into .git/hooks (both executable)."""
    data = TEMPLATES.joinpath(name).read_bytes()
    hook_dir = project / ".gov" / "hooks"
    hook_dir.mkdir(parents=True, exist_ok=True)
    for dest in (hook_dir / name, project / ".git" / "hooks" / name):
        dest.write_bytes(data)
        dest.chmod(0o755)


def _install_ci(project: Path, created: list[str]) -> None:
    """Generate .github/workflows/gov.yml only when it does not exist."""
    workflow = project / ".github" / "workflows" / "gov.yml"
    if workflow.exists():
        print("init: .github/workflows/gov.yml already exists; leaving it untouched")
        return
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_bytes(TEMPLATES.joinpath("gov.yml").read_bytes())
    created.append(".github/workflows/gov.yml")


def init(project: Path, hooks: bool = False, ci: bool = False,
         upgrade: bool = False, adopt: list[str] | None = None,
         report_json: bool = False, preview: bool = False,
         adopt_new: str | None = None, pre_commit: bool = False,
         preset: str | None = None) -> int:
    project = project.resolve()
    if not project.is_dir():
        print(f"init: {project} is not a directory", file=sys.stderr)
        return 2
    if pre_commit and not hooks:
        # The pre-commit hook rides with --hooks: both are git-hook add-ons
        # recorded in one manifest, and an accidental lone --pre-commit must
        # fail loud (rule 5), not silently skip the pre-push runner.
        print("init: --pre-commit installs alongside --hooks "
              "(the optional commit-stage gates ride with the hook runner)",
              file=sys.stderr)
        return 2
    if preset is not None:
        if upgrade or adopt is not None or adopt_new is not None:
            print("init: --preset composes with a fresh init (--hooks/--ci "
                  "fine); it does not combine with --upgrade/--adopt/"
                  "--adopt-new", file=sys.stderr)
            return 2
        # Fail loud BEFORE any mutation (rule 5): an unknown or malformed
        # preset name must never leave a half-initialized project.
        try:
            presets.load(preset)
        except presets.PresetError as e:
            print(f"init: {e}", file=sys.stderr)
            return 2
    manifest_path = project / ".gov" / "manifest.json"
    if adopt_new is not None and not manifest_path.exists():
        print("init: --adopt-new needs an initialized project", file=sys.stderr)
        return 2
    if manifest_path.exists():
        if adopt_new is not None:
            return _adopt_new(project, manifest_path, adopt_new)
        if adopt is not None:
            return _adopt(project, manifest_path, adopt, preview=preview)
        if upgrade:
            return _upgrade_report(project, manifest_path, json_mode=report_json)
        if not (hooks or ci):
            print(f"init: {project} is already initialized")
            if preset is not None:
                # Retrofitting a preset onto an initialized project: same
                # additive contract, same idempotence.
                return presets.apply(project, preset)
            return 0
        rc = _add_ons(project, manifest_path, hooks, ci,  # F5: retrofit path
                      pre_commit=pre_commit)
        if rc == 0 and preset is not None:
            rc = presets.apply(project, preset)
        return rc

    # Pre-flight the add-ons: fail loud before mutating anything, so a
    # conflict never leaves a half-initialized project with no manifest.
    if hooks and not (project / ".git").is_dir():
        print("init: --hooks needs a git repository (no .git found)", file=sys.stderr)
        return 2
    for name in (("pre-push",) if hooks and not pre_commit
                 else ("pre-push", "pre-commit") if hooks
                 else ()):
        if _hook_conflict(project, name):
            print(
                f"init: refusing to overwrite {project / '.git' / 'hooks' / name} — "
                "it is not a gov hook; merge the two by hand",
                file=sys.stderr,
            )
            return 2

    gov_dir = project / ".gov"
    created: list[str] = []
    git_hooks: list[str] = []

    _copy(TEMPLATES.joinpath("rules.md"), gov_dir / "rules.md")

    if not (project / "gates.json").exists():
        _copy(TEMPLATES.joinpath("gates.json"), project / "gates.json")
        created.append("gates.json")

    notes_readme = project / ".agents" / "notes" / "README.md"
    if not notes_readme.exists():
        _copy(TEMPLATES.joinpath("notes-README.md"), notes_readme)
        created.append(".agents/notes/README.md")

    for name in SKILLS:
        skill = project / ".agents" / "skills" / name / "SKILL.md"
        if skill.exists():
            continue  # a project's own skill is never overwritten
        _copy(TEMPLATES.joinpath("skills") / name / "SKILL.md", skill)
        created.append(f".agents/skills/{name}/SKILL.md")

    rejections_readme = gov_dir / "rejections" / "README.md"
    if not rejections_readme.exists():
        _copy(TEMPLATES.joinpath("rejections-README.md"), rejections_readme)
        created.append(".gov/rejections/README.md")

    ag = project / "AGENTS.md"
    if ag.exists():
        text = ag.read_text(encoding="utf-8")
        if REFERENCE_MARKER not in text:
            if text and not text.endswith("\n"):
                text += "\n"
            ag.write_text(text + REFERENCE_LINE + "\n", encoding="utf-8")
    else:
        ag.write_text(REFERENCE_LINE + "\n", encoding="utf-8")

    if hooks:
        _install_hook(project, "pre-push")
        git_hooks.append("pre-push")
        if pre_commit:
            _install_hook(project, "pre-commit")
            git_hooks.append("pre-commit")
    if ci:
        _install_ci(project, created)

    (gov_dir / "manifest.json").write_text(
        json.dumps(
            {"version": __version__, "created": created, "gitHooks": git_hooks,
             "templates": _template_hashes(project, created)},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"init: initialized {project}")
    print("  .gov/rules.md (rules)")
    if created:
        print("  " + ", ".join(created) + " (created; project had none)")
    print("  AGENTS.md reference line")
    if hooks:
        print("  .gov/hooks/pre-push + .git/hooks/pre-push (runs gov run before push)")
        if pre_commit:
            print("  .gov/hooks/pre-commit + .git/hooks/pre-commit "
                  "(cheap content gates on staged files — opt-in, #110)")
    if ci and ".github/workflows/gov.yml" in created:
        print("  .github/workflows/gov.yml (CI runs gov run)")

    if "gates.json" in created:
        # A read-only existence probe picks the advice (not D13's rejected
        # auto-baselining — nothing is judged or written): with no docs to
        # pair, the baseline step cannot succeed and is not suggested.
        has_docs = (project / "README.md").exists() or any(
            (project / "docs").glob("*.md")
        )
        print("next steps:")
        print("  1. gov run                        # pairing runs advisory until baselined")
        if has_docs:
            print("  2. gov verify-pairing --write     # baseline doc pairs (writes .i18n.yaml records)")
            print("  3. remove \"allowFailure\" from the pairing gate in gates.json to enforce")
        else:
            print("  2. no paired docs detected — leave pairing advisory, or disable it:")
            print("     set \"enabled\": false on the pairing gate in gates.json")

    if preset is not None:
        # D53: one command for "a new project of this type" — init lands
        # the generic floor, the preset adds the typed patch on top.
        return presets.apply(project, preset)
    return 0


def _template_hashes(project: Path, created: list[str]) -> dict[str, str]:
    """sha256 of each shipped template actually adopted (D34 provenance).

    Files the project already owned (create-if-missing did not land) have
    no entry: nothing was adopted, so there is nothing to re-adopt.
    """
    import hashlib
    hashes: dict[str, str] = {}
    inv = dict(_inventory(set(created)))
    hashes[".gov/rules.md"] = hashlib.sha256(
        TEMPLATES.joinpath("rules.md").read_bytes()).hexdigest()  # always written
    for rel in created:
        tpl = inv.get(rel)
        if tpl is not None:
            hashes[rel] = hashlib.sha256(tpl.read_bytes()).hexdigest()
    return hashes


def _inventory(created: set[str]) -> list[tuple[str, Any]]:
    """Every template-injectable file: (rel path, shipped template)."""
    expected: list[tuple[str, Any]] = [
        (".gov/rules.md", TEMPLATES.joinpath("rules.md")),
        (".agents/notes/README.md", TEMPLATES.joinpath("notes-README.md")),
        (".gov/rejections/README.md", TEMPLATES.joinpath("rejections-README.md")),
        (".gov/hooks/pre-push", TEMPLATES.joinpath("pre-push")),
        (".gov/hooks/pre-commit", TEMPLATES.joinpath("pre-commit")),
    ]
    expected += [
        (f".agents/skills/{name}/SKILL.md", TEMPLATES.joinpath("skills") / name / "SKILL.md")
        for name in SKILLS
    ]
    if "gates.json" in created:
        expected.append(("gates.json", TEMPLATES.joinpath("gates.json")))
    if ".github/workflows/gov.yml" in created:
        expected.append((".github/workflows/gov.yml", TEMPLATES.joinpath("gov.yml")))
    return expected


def _adopt(project: Path, manifest_path: Path, targets: list[str],
           preview: bool = False) -> int:
    """Wish 1/D29 + D34: apply template files that are locally MISSING —
    never overwrite a customized file. A copy that is byte-identical to
    what was adopted (provenance hash) may be safely re-adopted when the
    upstream template moved; ``--preview`` shows what would land and
    writes nothing; the manifest update is disclosed, never silent.
    """
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"init: corrupt manifest {manifest_path}: {e}", file=sys.stderr)
        return 2
    created = list(data.get("created", []))
    inventory = dict(_inventory(set(data.get("created", []))))
    if targets and targets != ["all"]:
        unknown = [t for t in targets if t not in inventory]
        if unknown:
            print(f"init: not a template file: {', '.join(unknown)} "
                  f"(known: {', '.join(sorted(inventory))})", file=sys.stderr)
            return 2
        selected = targets
    else:
        selected = [rel for rel in inventory if not (project / rel).exists()]

    import hashlib
    recorded = dict(data.get("templates", {}))
    if preview:
        # D34: preview shows exactly what would land, writes nothing.
        # A bare preview cross-references the drift inventory — the entry
        # must be self-explaining, not a bare banner (round feedback).
        if not targets or targets == ["all"]:
            missing_n = sum(1 for rel, _ in inventory.items()
                            if not (project / rel).exists())
            drifted_n = sum(
                1 for rel, tpl in inventory.items()
                if (project / rel).exists()
                and (project / rel).read_bytes() != tpl.read_bytes()
            )
            print(f"adoptable: {missing_n} missing, {drifted_n} drifted "
                  f"(vs shipped templates)")
            print("  gov init --upgrade lists them with per-file diffs;")
            print("  gov init --adopt <file> --preview diffs one file")
        for rel in selected:
            tpl_bytes = inventory[rel].read_bytes()
            dest = project / rel
            if not dest.exists():
                print(f"--- would create {rel} ({len(tpl_bytes)} bytes) ---")
                text = tpl_bytes.decode("utf-8", errors="replace").splitlines()
                for line in text[:40]:
                    print(f"  {line}")
                if len(text) > 40:
                    print(f"  …and {len(text) - 40} more line(s)")
            else:
                import difflib
                diff = list(difflib.unified_diff(
                    dest.read_text(encoding="utf-8", errors="replace").splitlines(),
                    tpl_bytes.decode("utf-8", errors="replace").splitlines(),
                    fromfile=f"local/{rel}", tofile=f"shipped-template/{rel}",
                    lineterm=""))
                print(f"--- {rel}: adoption would replace it with the shipped "
                      "template (diff below) ---")
                for line in diff[:40]:
                    print(f"  {line}")
                if len(diff) > 40:
                    print(f"  …and {len(diff) - 40} more line(s)")
        print("init: preview only — nothing was written")
        return 0

    applied = re_adopted = 0
    for rel in selected:
        dest = project / rel
        tpl_bytes = inventory[rel].read_bytes()
        tpl_h = hashlib.sha256(tpl_bytes).hexdigest()
        if dest.exists():
            local_h = hashlib.sha256(dest.read_bytes()).hexdigest()
            adopted_h = recorded.get(rel)
            if adopted_h == local_h and local_h != tpl_h:
                # The copy is byte-identical to what was adopted and the
                # template moved since — replacing it loses nothing (D34).
                dest.write_bytes(tpl_bytes)
                recorded[rel] = tpl_h
                re_adopted += 1
                print(f"init: re-adopted {rel} (your copy was uncustomized; "
                      "the upstream template had moved)")
                continue
            print(f"init: {rel} already present — untouched (never overwritten; "
                  "preview with --preview)")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(tpl_bytes)
        if rel not in created:
            created.append(rel)
        recorded[rel] = tpl_h
        if rel.endswith(("pre-push", "pre-commit")):
            dest.chmod(0o755)
        print(f"init: adopted {rel}")
        applied += 1
    if not applied and not re_adopted:
        print("init: nothing to adopt (no missing template files)")
    manifest_path.write_text(
        json.dumps({"version": __version__, "created": created,
                    "gitHooks": data.get("gitHooks", []),
                    "templates": recorded}, indent=2) + "\n",
        encoding="utf-8",
    )
    if applied or re_adopted:
        # D34: side effects are disclosed, never silent.
        print(f"init: manifest updated — {applied} adopted, {re_adopted} "
              "re-adopted; template hashes recorded")
    return 0


def _adopt_new(project: Path, manifest_path: Path, target: str) -> int:
    """Issue #108/D39: additive adoption of NEW shipped entries into a
    customized gates.json. Gate id is identity: shipped gates whose id is
    absent locally are appended; every local gate is preserved untouched;
    shared ids whose content differs are non-additive drift — refused
    loud (rule 5), nothing written. The merge itself is the plane's one
    gates-merge semantics (gates.merge_gates_by_id), shared with preset
    apply — only the drift ruling differs ("refuse" here; a preset keeps
    the local gate).
    """
    if target != "gates.json":
        print(f"init: --adopt-new supports 'gates.json' only, not '{target}' "
              "(other customized files keep the hand-merge path, D27/D34)",
              file=sys.stderr)
        return 2
    local_path = project / "gates.json"
    if not manifest_path.exists():
        print("init: --adopt-new needs an initialized project", file=sys.stderr)
        return 2
    if not local_path.exists():
        print(f"init: {local_path} does not exist — a fresh `gov init "
              "--adopt gates.json` lands the whole template instead",
              file=sys.stderr)
        return 2
    try:
        local = json.loads(local_path.read_text(encoding="utf-8"))
        tpl = json.loads(TEMPLATES.joinpath("gates.json").read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"init: cannot read gates.json for --adopt-new: {e}", file=sys.stderr)
        return 2

    def _gates(doc: Any, what: str) -> list[dict] | None:
        if not isinstance(doc, dict) or not isinstance(doc.get("gates"), list) \
                or any(not isinstance(g, dict) or not isinstance(g.get("id"), str)
                       or not g["id"] for g in doc["gates"]):
            print(f"init: {what} gates.json is structurally invalid for "
                  "--adopt-new (needs an object with a 'gates' array of "
                  "objects carrying string ids)", file=sys.stderr)
            return None
        return doc["gates"]

    if _gates(local, "local") is None or _gates(tpl, "shipped template") is None:
        return 2

    try:
        merged, added, modes_note = gates.merge_gates_by_id(
            local, tpl, what="the template", on_drift="refuse")
    except gates.DriftRefused as e:
        print("init: --adopt-new refused — non-additive drift: shipped "
              f"gate(s) differ from your local version: {', '.join(e.ids)}"
              "; merge those by hand (see `gov init --upgrade` for the diff)",
              file=sys.stderr)
        return 2
    if not added:
        print("init: adopt-new gates.json — nothing to add (every shipped "
              "gate id is already present locally)")
        return 0

    text = json.dumps(merged, indent=2) + "\n"
    # Rule 6 in spirit: validate before landing — never write a gates.json
    # the runner itself would reject.
    import tempfile
    fd, tmp = tempfile.mkstemp(dir=project, suffix=".gates.json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        gates.load_config(tmp)
    except Exception as e:  # noqa: BLE001 — any validation failure is fatal
        os.unlink(tmp)
        print(f"init: --adopt-new refused — merged gates.json fails schema "
              f"validation: {e}", file=sys.stderr)
        return 2
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    local_path.write_text(text, encoding="utf-8")

    print(f"init: adopt-new gates.json — added {len(added)} shipped gate(s): "
          + ", ".join(g["id"] for g in added))
    print(f"  all {len(local['gates'])} local gate(s) preserved untouched")
    for note in modes_note:
        print(f"  {note}")
    print("  merged gates.json passes schema validation; manifest untouched "
          "(your gates.json stays customized)")
    return 0


def _upgrade_report(project: Path, manifest_path: Path,
                    json_mode: bool = False) -> int:
    """Wish 8/D27: show how the shipped templates and this project drifted.

    Reads, never writes: per-file diff of every injected file against the
    current package template, with the manifest's init version for era
    context. Adopting a change stays a human act (D23's two-step).
    """
    import difflib

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"init: corrupt manifest {manifest_path}: {e}", file=sys.stderr)
        return 2
    created = set(data.get("created", []))
    init_version = data.get("version", "unknown")

    expected = _inventory(created)

    current: list[str] = []
    missing: list[str] = []
    differing: list[tuple[str, Any]] = []
    opt_in = {".gov/hooks/pre-push", ".gov/hooks/pre-commit"}  # add-ons, not always-injected
    for rel, tpl in expected:
        local = project / rel
        if not local.exists():
            if rel in opt_in:
                continue  # absent add-on is not drift
            missing.append(rel)
            continue
        try:
            if local.read_bytes() == tpl.read_bytes():
                current.append(rel)
            else:
                differing.append((rel, tpl))
        except OSError:
            differing.append((rel, tpl))

    if json_mode:
        # Wish 6c/D30: machine-readable drift — an agent decides adoptions
        # programmatically (stdout is exactly one JSON value).
        opt_in = {".gov/hooks/pre-push", ".gov/hooks/pre-commit"}
        files_out = []
        for rel, tpl in expected:
            local = project / rel
            if not local.exists():
                status = "absent-add-on" if rel in opt_in else "missing"
            elif local.read_bytes() == tpl.read_bytes():
                status = "matches"
            else:
                status = "differs"
            era = None
            if status == "differs":
                import hashlib
                local_h = hashlib.sha256((project / rel).read_bytes()).hexdigest()
                adopted_h = recorded.get(rel)
                if adopted_h is None:
                    era = "ambiguous"
                elif local_h == adopted_h:
                    era = "upstream-moved"
                else:
                    era = "both-moved"
            files_out.append({
                "path": rel,
                "status": status,
                "era": era,
                "adoptable": status == "missing" or era == "upstream-moved",
            })
        print(json.dumps({
            "initialized_with": init_version,
            "package": __version__,
            "files": files_out,
        }, indent=2))
        return 0
    print(f"init: upgrade report for {project} — nothing is changed by this report")
    print(f"  initialized with govrail {init_version} · this package {__version__}")
    if init_version != "unknown" and init_version != __version__:
        print(f"  newer releases exist — gov whatsnew --since {init_version} "
              "shows what arrived and how to use it")
    for rel in current:
        print(f"  {rel:<40} matches the shipped template")
    for rel in missing:
        print(f"  {rel:<40} MISSING — adoptable: gov init --adopt {rel}")
    import hashlib
    recorded = data.get("templates", {})
    for rel, tpl in differing:
        local_b = (project / rel).read_bytes()
        local_h = hashlib.sha256(local_b).hexdigest()
        adopted_h = recorded.get(rel)
        if adopted_h is None:
            era = ("customized locally" if init_version == __version__
                   else "customized locally and/or template evolved "
                        f"since v{init_version} (no adoption hash recorded)")
        elif local_h == adopted_h:
            era = ("UPSTREAM MOVED — your copy is untouched since adoption; "
                   "`gov init --adopt " + rel + "` takes the new template safely")
        else:
            era = ("BOTH MOVED — your customization AND the upstream template "
                   "evolved; merge by hand (two-step)")
        print(f"  {rel:<40} DIFFERS ({era}):")
        diff = list(
            difflib.unified_diff(
                tpl.read_text(encoding="utf-8").splitlines(),
                (project / rel).read_text(encoding="utf-8").splitlines(),
                fromfile=f"shipped-template/{rel}",
                tofile=f"local/{rel}",
                lineterm="",
            )
        )
        shown = diff[:40]
        for line in shown:
            print(f"      {line}")
        if len(diff) > len(shown):
            print(f"      ... ({len(diff) - len(shown)} more diff line(s))")

    if not missing and not differing:
        print("  every injected file matches the shipped templates — safe to refresh")
        return 0
    print("  to adopt a template change: edit the file by hand (customized files")
    print("  first — see the two-step philosophy); a fresh `gov init` after")
    print("  `gov uninstall` re-injects everything and warns per D23.")
    return 0


def _add_ons(project: Path, manifest_path: Path, hooks: bool, ci: bool,
             pre_commit: bool = False) -> int:
    """Install --hooks/--ci on an already-initialized project (F5).

    Only the requested add-ons are touched — rules, gates, notes, skills,
    and the AGENTS.md reference line stay exactly as they are, so
    retrofitting a hook never resets customizations.
    """
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"init: corrupt manifest {manifest_path}: {e}", file=sys.stderr)
        return 2
    created = list(data.get("created", []))
    git_hooks = list(data.get("gitHooks", []))

    if hooks:
        if not (project / ".git").is_dir():
            print("init: --hooks needs a git repository (no .git found)", file=sys.stderr)
            return 2
        for name in (("pre-push", "pre-commit") if pre_commit else ("pre-push",)):
            if _hook_conflict(project, name):
                print(
                    f"init: refusing to overwrite "
                    f"{project / '.git' / 'hooks' / name} — "
                    "it is not a gov hook; merge the two by hand",
                    file=sys.stderr,
                )
                return 2
        _install_hook(project, "pre-push")
        if "pre-push" not in git_hooks:
            git_hooks.append("pre-push")
        print("init: installed .gov/hooks/pre-push + .git/hooks/pre-push (runs gov run before push)")
        if pre_commit:
            _install_hook(project, "pre-commit")
            if "pre-commit" not in git_hooks:
                git_hooks.append("pre-commit")
            print("init: installed .gov/hooks/pre-commit + .git/hooks/pre-commit "
                  "(cheap content gates on staged files — opt-in, #110)")
    if ci:
        before = len(created)
        _install_ci(project, created)
        if len(created) > before:
            print("init: created .github/workflows/gov.yml (CI runs gov run)")
        # _install_ci itself reports the already-exists case.

    manifest_path.write_text(
        json.dumps(
            {"version": __version__, "created": created, "gitHooks": git_hooks},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


def _template_for(rel: str):
    """The shipped template a created file came from, if any."""
    if rel == "gates.json":
        return TEMPLATES.joinpath("gates.json")
    if rel == ".agents/notes/README.md":
        return TEMPLATES.joinpath("notes-README.md")
    if rel == ".gov/rejections/README.md":
        return TEMPLATES.joinpath("rejections-README.md")
    if rel == ".github/workflows/gov.yml":
        return TEMPLATES.joinpath("gov.yml")
    if rel.startswith(".agents/skills/") and rel.endswith("/SKILL.md"):
        return TEMPLATES.joinpath("skills") / rel.split("/")[2] / "SKILL.md"
    return None


def uninstall(project: Path, force: bool = False) -> int:
    project = project.resolve()
    manifest = project / ".gov" / "manifest.json"
    if not manifest.exists():
        print(f"uninstall: {project} is not initialized", file=sys.stderr)
        return 2
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"uninstall: corrupt manifest {manifest}: {e}", file=sys.stderr)
        return 2

    # F5: exact reversal stays (D10), but customized content is never
    # deleted silently — anything that drifted from its shipped template
    # is named before it goes.
    customized = []
    candidates = [(".gov/rules.md", TEMPLATES.joinpath("rules.md"))]
    for rel in data.get("created", []):
        t = _template_for(rel)
        if t is not None:
            candidates.append((rel, t))
    for rel, t in candidates:
        p = project / rel
        try:
            if p.is_file() and p.read_bytes() != t.read_bytes():
                customized.append(rel)
        except OSError:
            pass
    if customized:
        # F6: a genuine two-step — without --force this run deletes
        # nothing. The message must never promise an abort the code does
        # not perform.
        if force:
            print(
                "uninstall: --force — deleting customized file(s) that differ "
                "from the shipped template:",
                file=sys.stderr,
            )
            for rel in customized:
                print(f"  {rel}", file=sys.stderr)
        else:
            print(
                "uninstall: WARNING — customized file(s) differ from the shipped "
                "template; nothing has been deleted:",
                file=sys.stderr,
            )
            for rel in customized:
                print(f"  {rel}", file=sys.stderr)
            print(
                "  copy out anything you want to keep, then re-run with --force "
                "to uninstall anyway",
                file=sys.stderr,
            )
            return 1

    ag = project / "AGENTS.md"
    if ag.exists():
        kept = [line for line in ag.read_text(encoding="utf-8").splitlines()
                if REFERENCE_MARKER not in line]
        while kept and kept[-1] == "":
            kept.pop()
        if kept:
            ag.write_text("\n".join(kept) + "\n", encoding="utf-8")
        else:
            ag.unlink()

    for rel in data.get("created", []):
        p = project / rel
        if p.exists():
            p.unlink()
            _remove_empty_dirs(p.parent)

    for name in data.get("gitHooks", []):
        p = project / ".git" / "hooks" / name
        if p.exists():
            p.unlink()

    shutil.rmtree(project / ".gov", ignore_errors=True)
    print(f"uninstall: removed governance from {project}")
    return 0


_COMMANDS = {
    "init": "inject the plane into a project (--hooks/--ci add runners; --hooks "
            "--pre-commit adds the opt-in commit-stage gates; --adopt-new "
            "merges new shipped gates; --upgrade shows template drift)",
    "uninstall": "reverse init",
    "run": "run the project's gate DAG (args forwarded to gates.py; "
           "--receipt records a tamper-evident run receipt, #124; "
           "--merge preflights the union of parallel branches in a "
           "scratch worktree before landing)",
    "self-test": "run governance rejection cases",
    "receipt": "verifiable run receipts: verify a cited receipt against a "
               "commit (issue #124/D42)",
    "verify-notes": "check note format",
    "verify-pairing": "check bilingual pairing (--write re-confirms; --staged "
                     "checks the index; --explain prints the schema)",
    "verify-note-presence": "warn when a non-trivial diff carries no note (e.g. --base <ref>, --strict)",
    "verify-rubric": "check the review rubric's structure (ids, fields, parity)",
    "verify-archive": "verify the archived-notes seal (pinned sha256 per file)",
    "verify-decisions": "verify the decisions table (numbering, alternatives, orphans; --base checks branch collisions)",
    "decision": "decision-row tooling (next free D-number; atomic validated add)",
    "verify-doc-sync": "CHANGELOG ↔ HIGHLIGHTS pairing (every version has a "
                "section; --write drafts the missing ones from CHANGELOG)",
    "verify-conflict-markers": "fail when changed files carry git conflict markers (e.g. --base <ref>, --staged)",
    "review": "assemble the review dossier for a diff (scope, notes, recall, rubric)",
    "trend": "gate duration trends from .gov/history/ (p50 per window; --by-tag splits per caller, --cost rolls up caller-reported cost)",
    "doctor": "environment self-check (PATH, python, hooks, gates schema)",
    "note": "note scaffold and pre-commit check (new/check)",
    "whatsnew": "usage-oriented highlights since a version",
    "recall": "retrieve notes, decisions, and postmortems (all terms, ranked)",
    "audit-notes": "report mechanical staleness signals in implemented notes",
    "change-scope": "report touched surfaces (e.g. --base <ref>)",
    "archive-notes": "seal the archived-notes manifest",
    "task": "task cards for subagent briefs (new/check/close/claim/release/"
            "list; rules@hash pin + checklist + green-run receipt; claim/"
            "release lease a card so two workers cannot take one)",
    "preset": "typed adoption bundles (list/show/apply): a project type's "
              "gates, skills, and manifest hints — additive, never "
              "overwriting (D53)",
    "acquire": "take a lease lock on a resource (cross-process, "
               "cross-duration; busy exits 3; --wait S polls, --ttl S "
               "bounds the lease)",
    "release": "release a lease you hold (--agent must match the holder)",
    "locks": "list current lease locks in the git common dir (diagnostic "
             "only, never an admission decision)",
}


_CD_FLAGS = ("-C", "--path")


def _resolved_target() -> str:
    """The directory gov is acting on: the git work-tree root when inside
    one (exactly what cd + root anchoring would resolve to), else cwd."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",  # git speaks UTF-8, not the locale codec (#168)
        )
    except OSError:
        proc = None
    if proc is not None and proc.returncode == 0 and proc.stdout.strip():
        return proc.stdout.strip()
    return os.getcwd()


def _apply_cd_flags(argv: list[str]) -> list[str] | None:
    """Consume leading ``-C <path>`` / ``--path <path>`` flags (#121).

    A supervisor orchestrating several worktrees chdirs by value instead
    of bookkeeping: each path resolves against the previous one (git
    ``-C`` semantics, chainable), the chdir lands before the subcommand
    dispatches, and — because a wrong-tree invocation must be visible,
    not just valid — the resolved root is announced in the output header
    of every command run this way. A nonexistent path fails loud.
    """
    moved: list[str] = []
    while argv and argv[0] in _CD_FLAGS:
        if len(argv) < 2:
            print(f"gov: {argv[0]} requires a directory path", file=sys.stderr)
            return None
        target = Path(argv[1])
        if not target.is_dir():
            print(f"gov: {argv[0]} {argv[1]}: no such directory", file=sys.stderr)
            return None
        os.chdir(target)
        moved.append(argv[1])
        argv = argv[2:]
    if moved:
        print(f"gov: targeting {_resolved_target()} "
              f"(via -C {' -C '.join(moved)})", file=sys.stderr)
    return argv


def _usage() -> None:
    print("usage: gov [-C <path>] <command> [args]", file=sys.stderr)
    print("  -C, --path DIR   run <command> against DIR's repository "
          "(before the command;", file=sys.stderr)
    print("                   resolves the work-tree root and announces it)",
          file=sys.stderr)
    print("commands:", file=sys.stderr)
    for name, help_text in _COMMANDS.items():
        print(f"  {name:<16} {help_text}", file=sys.stderr)


_HELP_FLAGS = ("-h", "--help", "help")
_VERSION_FLAGS = ("-v", "--version", "version")
# Commands whose args are NOT forwarded to an argparse parser: they must
# intercept help/version themselves so a trailing flag never runs the action.
_NO_FORWARD = ("init", "uninstall", "verify-notes")

# The hand-parsed commands have no argparse to print their options, so the
# surface is declared here as data: `gov <cmd> --help` shows it, and
# audit-notes' flag registry is pinned to it (tests/test_flag_registry.py,
# issue #101 — the terse one-line summary above is a description, never
# the machine-checked surface).
COMMAND_FLAGS: dict[str, tuple[tuple[str, str], ...]] = {
    "init": (
        ("--project DIR", "target project root (default: current directory)"),
        ("--hooks", "add the git hooks runner (needs a git repository)"),
        ("--pre-commit", "with --hooks: also install the optional pre-commit "
                         "hook — cheap content gates (pairing sidecar freshness, "
                         "conflict markers) on the staged files (#110)"),
        ("--ci", "add the CI runner (.github/workflows/gov.yml)"),
        ("--upgrade", "report template drift; reads, never writes"),
        ("--json", "with --upgrade: exactly one machine-readable report"),
        ("--adopt [FILE...]", "land MISSING template files, never overwrite "
                              "a customized one ('all' = every missing file)"),
        ("--adopt-new FILE", "merge only the NEW shipped entries of a "
                             "customized gates.json into yours (additive by "
                             "gate id; non-additive drift is refused)"),
        ("--preset NAME", "with init (fresh or already-initialized): apply "
                          "the preset right after — typed gates, skills, "
                          "and manifest hints, additive (see `gov preset "
                          "list`; D53)"),
        ("--preview", "with --adopt: show what would land, write nothing"),
    ),
    "uninstall": (
        ("--project DIR", "target project root (default: current directory)"),
        ("--force", "also delete customized files that differ from the "
                    "shipped template (without it, nothing is deleted)"),
    ),
    "verify-notes": (),
}


def _command_help(cmd: str) -> None:
    """Per-command help for the hand-parsed trio (same shape as argparse's)."""
    flags = COMMAND_FLAGS[cmd]
    print(f"usage: gov {cmd} [options]")
    print(_COMMANDS[cmd])
    print()
    print("options:")
    names = [name for name, _ in flags] + ["-h, --help"]
    width = max(len(n) for n in names)
    for name, desc in flags:
        print(f"  {name:<{width}}  {desc}")
    print(f"  {'-h, --help':<{width}}  show this help and exit")


def _init_uninstall_args(
    args: list[str], what: str
) -> tuple[Path, bool, bool, bool, bool] | None:
    """Parse --project (+ init's --hooks/--ci/--upgrade/--preset, uninstall's --force)."""
    project = "."
    hooks = ci = force = upgrade = adopt = report_json = preview = pre_commit = False
    adopt_targets: list[str] = []
    adopt_new: str | None = None
    preset: str | None = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--project":
            if i + 1 >= len(args):
                print(f"gov {what}: --project requires a directory", file=sys.stderr)
                return None
            project = args[i + 1]
            i += 2
        elif what == "init" and a == "--hooks":
            hooks = True
            i += 1
        elif what == "init" and a == "--pre-commit":
            pre_commit = True
            i += 1
        elif what == "init" and a == "--ci":
            ci = True
            i += 1
        elif what == "init" and a == "--upgrade":
            upgrade = True
            i += 1
        elif what == "init" and a == "--json":
            report_json = True
            i += 1
        elif what == "init" and a == "--preview":
            preview = True
            i += 1
        elif what == "init" and a == "--preset":
            if i + 1 >= len(args) or args[i + 1].startswith("--"):
                print("gov init: --preset requires a preset name "
                      "(see `gov preset list`)", file=sys.stderr)
                return None
            preset = args[i + 1]
            i += 2
        elif what == "init" and a == "--adopt":
            adopt = True
            i += 1
            while i < len(args) and not args[i].startswith("--"):
                adopt_targets.append(args[i])
                i += 1
        elif what == "init" and a == "--adopt-new":
            if i + 1 >= len(args) or args[i + 1].startswith("--"):
                print("gov init: --adopt-new requires a file "
                      "(currently: gates.json)", file=sys.stderr)
                return None
            adopt_new = args[i + 1]
            i += 2
        elif what == "uninstall" and a == "--force":
            force = True
            i += 1
        else:
            print(f"gov {what}: unexpected argument '{a}'", file=sys.stderr)
            _usage()
            return None
    return (Path(project), hooks, ci, force, upgrade,
            (adopt_targets if adopt else None), report_json, preview,
            adopt_new, pre_commit, preset)


def main(argv: list[str] | None = None) -> int:
    from .root import force_utf8_stdio
    force_utf8_stdio()  # every report leaves as UTF-8, on every OS (#168)
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        _usage()
        return 2
    argv = _apply_cd_flags(argv)
    if argv is None:
        return 2
    if not argv:
        _usage()
        return 2
    cmd, rest = argv[0], argv[1:]

    if cmd in _HELP_FLAGS:
        _usage()
        return 0
    if cmd in _VERSION_FLAGS:
        print(f"gov {__version__}")
        return 0
    # Subcommand-level help/version: never execute the action as a side effect.
    if cmd in _NO_FORWARD:
        if any(a in _HELP_FLAGS for a in rest):
            _command_help(cmd)  # the real surface, not the terse global usage
            return 0
        if any(a in _VERSION_FLAGS for a in rest):
            print(f"gov {__version__}")
            return 0
    if cmd == "init":
        parsed = _init_uninstall_args(rest, "init")
        return 2 if parsed is None else init(parsed[0], hooks=parsed[1], ci=parsed[2],
                                            upgrade=parsed[4], adopt=parsed[5],
                                            report_json=parsed[6],
                                            preview=parsed[7],
                                            adopt_new=parsed[8],
                                            pre_commit=parsed[9],
                                            preset=parsed[10])
    if cmd == "uninstall":
        parsed = _init_uninstall_args(rest, "uninstall")
        return 2 if parsed is None else uninstall(parsed[0], force=parsed[3])
    if cmd == "preset":
        return presets.main(rest)
    if cmd == "run":
        return gates.main(rest)
    if cmd == "receipt":
        return receipt.main(rest)
    if cmd == "self-test":
        return self_test.main(rest)
    if cmd == "verify-notes":
        return verify_notes.main()
    if cmd == "verify-pairing":
        return verify_translation_pairing.main(rest)
    if cmd == "verify-note-presence":
        return verify_note_presence.main(rest)
    if cmd == "verify-rubric":
        return verify_rubric.main(rest)
    if cmd == "verify-archive":
        return verify_archive.main(rest)
    if cmd == "verify-decisions":
        return verify_decisions.main(rest)
    if cmd == "decision":
        return decision.main(rest)
    if cmd == "verify-doc-sync":
        return verify_doc_sync.main(rest)
    if cmd == "verify-conflict-markers":
        return verify_conflict_markers.main(rest)
    if cmd == "review":
        return review.main(rest)
    if cmd == "trend":
        return trend.main(rest)
    if cmd == "doctor":
        return doctor.main(rest)
    if cmd == "note":
        return note.main(rest)
    if cmd == "whatsnew":
        return whatsnew.main(rest)
    if cmd == "recall":
        return recall.main(rest)
    if cmd == "audit-notes":
        return audit_notes.main(rest)
    if cmd == "change-scope":
        return change_scope.main(rest)
    if cmd == "archive-notes":
        return archive_notes.main(rest)
    if cmd == "task":
        return task.main(rest)
    if cmd in ("acquire", "release", "locks"):
        return locks.main([cmd, *rest])
    print(f"gov: unknown command '{cmd}'", file=sys.stderr)
    _usage()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
