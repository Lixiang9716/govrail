#!/usr/bin/env python3
"""The plane's install surface: ``gov init`` and ``gov uninstall``.

This is the adoption domain — template injection, manifest bookkeeping,
hook wiring, drift classification — moved out of ``gov/cli.py`` so the
dispatcher is only a dispatcher. ``gov update`` (D58) consumes
``upgrade_files`` from here: migration orchestrates the same machinery
init uses, it does not re-implement it.

Every install write is atomic and byte-exact (the injected files are
compared BYTE-WISE against their shipped templates by uninstall's
customized check and by --adopt/--upgrade provenance), every refusal
fires before the first mutation (rule 5), and the manifest records what
was created so uninstall reverses exactly that.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from importlib.resources import files
from pathlib import Path
from typing import Any

from . import (atomicio, gates, gitutil, presets,
               verify_plane)
from . import __version__

TEMPLATES = files("gov.templates")
REFERENCE_MARKER = "<!-- gov:rules -->"
REFERENCE_LINE = (
    f"{REFERENCE_MARKER} Read .gov/rules.md and follow it before starting "
    "work. Start from the `govrail` skill — it routes every command to "
    "the right moment (and names the moves that are never OK)."
)
HOOK_MARKER = "# govrail:"
# The agent skills that travel with the plane: injected like rules.md,
# create-if-missing, never overwriting a project's own skill.
SKILLS = ("govrail", "recall-first", "pre-push-checks", "code-review",
          "archive-agent-notes")
# D60: agent platforms `--platforms` can select — one installed hook
# config and one shipped template each, all wiring the same five
# `gov agent-hooks` events in the platform's own protocol. Order is the
# help/report order; `all` means every entry.
PLATFORM_TARGETS: dict[str, tuple[str, str]] = {
    "claude": (".claude/settings.json", "claude-settings.json"),
    "codex": (".codex/hooks.json", "codex-hooks.json"),
    "copilot": (".github/hooks/govrail.json", "copilot-hooks.json"),
    "gemini": (".gemini/settings.json", "gemini-settings.json"),
}


def _atomic_write(dest: Path, data: bytes) -> None:
    """atomicio's one-write policy in bytes mode: save to a temp file in
    the destination directory and ``os.replace`` it into place, so a
    crash can never leave a half-written file behind (H-3 — a truncated
    template used to be adopted as the project's own by a re-run init's
    create-if-missing guard).

    Bytes, not atomicio.write_text: the injected files are compared
    BYTE-WISE against their shipped templates (uninstall's customized
    check, --adopt/--upgrade provenance), and a text-mode write would
    translate newlines on Windows until an untouched install differed
    from its own template (the exact trap _install_ci's comment warns
    about). Modes follow atomicio: keep the existing file's mode, else
    respect the umask.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        mode = dest.stat().st_mode & 0o777
    except OSError:
        umask = os.umask(0)
        os.umask(umask)
        mode = 0o666 & ~umask
    fd, tmp = tempfile.mkstemp(dir=str(dest.parent), prefix=dest.name,
                               suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(tmp, mode)
        os.replace(tmp, dest)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _copy(source, dest: Path) -> None:
    _atomic_write(dest, source.read_bytes())


def _remove_empty_dirs(root: Path) -> None:
    """Remove empty parent dirs, deepest first, stopping at the first non-empty."""
    p = root
    while p != p.parent:
        try:
            p.rmdir()
        except OSError:
            break
        p = p.parent


def _git_in(project: Path, *args: str) -> subprocess.CompletedProcess:
    """One git command pinned to ``project`` — init acts on --project, not cwd."""
    return subprocess.run(
        ["git", "-c", "core.quotepath=off", "-C", str(project), *args],
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )


def _resolve_hooks_dir(project: Path) -> tuple[Path | None, str | None]:
    """(hooks dir, error): where this checkout's hooks actually run from.

    Worktree-aware: a linked worktree's ``.git`` is a FILE, and its hooks
    live in the COMMON dir — the old ``(project / ".git").is_dir()``
    probe refused linked worktrees outright while doctor (worktree-aware
    since #15) claimed everything was fine. ``core.hooksPath`` wins when
    set (husky/lefthook users): a gov hook written to ``.git/hooks``
    there is installed, manifested, and never executed.
    """
    probe = _git_in(project, "rev-parse", "--git-common-dir")
    if probe.returncode != 0:
        return None, "not a git repository (git rev-parse failed)"
    common = probe.stdout.strip()
    common_path = Path(common)
    if not common_path.is_absolute():
        common_path = (project / common_path).resolve()
    configured = _git_in(project, "config", "--get", "core.hooksPath")
    if configured.returncode == 0 and configured.stdout.strip():
        configured_path = Path(configured.stdout.strip())
        if not configured_path.is_absolute():
            configured_path = (project / configured_path).resolve()
        return configured_path, None
    return common_path / "hooks", None


def _hook_conflict(project: Path, name: str = "pre-push",
                   hooks_dir: Path | None = None) -> bool:
    """True when <hooks-dir>/<name> exists and is not a gov hook."""
    git_hook = (hooks_dir or _resolve_hooks_dir(project)[0] or
                project / ".git" / "hooks") / name
    if not git_hook.exists():
        return False
    try:
        existing = git_hook.read_text(encoding="utf-8")
    except OSError:
        return True
    return HOOK_MARKER not in existing


def _install_hook(project: Path, name: str = "pre-push",
                  hooks_dir: Path | None = None) -> None:
    """Write .gov/hooks/<name> and wire it into the checkout's real hooks
    dir (both executable)."""
    data = TEMPLATES.joinpath(name).read_bytes()
    hook_dir = project / ".gov" / "hooks"
    hook_dir.mkdir(parents=True, exist_ok=True)
    dest_dir = hooks_dir or _resolve_hooks_dir(project)[0]
    if dest_dir is None:
        raise RuntimeError("no hooks dir resolved — pre-flight should have refused")
    dest_dir.mkdir(parents=True, exist_ok=True)
    for dest in (hook_dir / name, dest_dir / name):
        atomicio.write_bytes(dest, data)
        dest.chmod(0o755)


def _install_ci(project: Path, created: list[str]) -> None:
    """Generate .github/workflows/gov.yml only when it does not exist."""
    workflow = project / ".github" / "workflows" / "gov.yml"
    if workflow.exists():
        print("init: .github/workflows/gov.yml already exists; leaving it untouched")
        return
    # Pin the version THIS init runs with: an unpinned `pip install
    # govrail` coupled every adopter's CI to the vendor's next release —
    # one bad publish, hundreds of red builds. Upgrade deliberately
    # (bump the pin, run gov init --upgrade for template drift).
    template = TEMPLATES.joinpath("gov.yml").read_text(encoding="utf-8")
    workflow.parent.mkdir(parents=True, exist_ok=True)
    # BYTES, not text mode: newline translation would make the installed
    # file differ from the rendered template on Windows, and uninstall's
    # byte-level customized check would refuse to delete its own install.
    atomicio.write_bytes(
        workflow,
        template.replace("__GOV_VERSION__", __version__).encode("utf-8"))
    created.append(".github/workflows/gov.yml")


def _install_platform(project: Path, name: str, created: list[str]) -> None:
    """Write one platform's agent-hook config, create-if-missing (D60).

    Same contract as every template install: an existing file is the
    adopter's territory — named skip, never merged. Codex additionally
    needs its one-time trust step named at install time: it hash-trusts
    each hook and silently skips untrusted ones, so an install that
    didn't say so would be a silent no-op for that platform.
    """
    rel, tpl_name = PLATFORM_TARGETS[name]
    dest = project / rel
    if dest.exists():
        print(f"init: {rel} already exists; leaving it untouched — merge "
              "the gov agent-hooks events in by hand (gov agent-hooks "
              "--help lists them)")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    atomicio.write_bytes(dest, TEMPLATES.joinpath(tpl_name).read_bytes())
    created.append(rel)
    note = {
        "codex": " — review and trust it in codex via /hooks "
                 "(untrusted hooks are skipped)",
        "gemini": " (Gemini CLI shows a one-time trust confirm for "
                  "project hooks)",
        "copilot": " (GitHub Copilot CLI / VS Code agent hooks)",
    }.get(name, "")
    print(f"init: created {rel} ({name} agent lifecycle hooks: "
          f"session-start/pre-tool-use/post-tool-use/"
          f"user-prompt-submit/stop){note}")


def init(project: Path, hooks: bool = False, ci: bool = False,
         upgrade: bool = False, adopt: list[str] | None = None,
         report_json: bool = False, preview: bool = False,
         adopt_new: str | None = None, pre_commit: bool = False,
         preset: str | None = None,
         platforms: list[str] | None = None) -> int:
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
    if preview and adopt is None:
        # --preview only means something with --adopt: it shows what
        # adoption WOULD land. Everywhere else it was silently dropped —
        # `gov init --preview` on an initialized project answered "already
        # initialized", and `--upgrade --preview` ran the report as if the
        # flag existed. Found by the post-merge review of the round-5 fix
        # (same class: a modifier an init path quietly ignores).
        print("init: --preview rides with --adopt (a bare preview has "
              "nothing to show; the drift report is `gov init --upgrade`)",
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
    gov_dir = project / ".gov"
    if gov_dir.is_symlink():
        # N10: a symlinked .gov re-points every state write — ledgers,
        # seals, receipts — at a path outside the repository. Nothing
        # here follows it; the adoption refuses, naming the link.
        print(f"init: {gov_dir} is a symlink — refusing; the plane's "
              "state must live inside the repository (remove the link "
              "or point it at a path you manage)", file=sys.stderr)
        return 2
    manifest_path = project / ".gov" / "manifest.json"
    if adopt_new is not None and not manifest_path.exists():
        print("init: --adopt-new needs an initialized project", file=sys.stderr)
        return 2
    if not manifest_path.exists() and (upgrade or preview or adopt is not None):
        # All three act ON an initialized project, and the fresh-init path
        # below ignores them while writing the whole plane: `gov init
        # --preview` on a bare directory wrote thirteen files and called it
        # a preview, and `--adopt X` performed a plain init with the target
        # quietly dropped. A flag must refuse rather than do the opposite
        # of its promise (rule 5). (--preview without --adopt never gets
        # this far: the composition check above refuses it first.)
        given = ("--upgrade" if upgrade
                 else "--preview" if preview
                 else "--adopt")
        print(f"init: {given} needs an initialized project (no "
              f"{manifest_path.relative_to(project).as_posix()}); a fresh "
              "init writes the plane — drop the flag for that",
              file=sys.stderr)
        return 2
    if manifest_path.exists():
        if adopt_new is not None:
            return adopt_new_gates(project, manifest_path, adopt_new)
        if adopt is not None:
            return adopt_missing(project, manifest_path, adopt, preview=preview)
        if upgrade:
            return _upgrade_report(project, manifest_path, json_mode=report_json)
        if not (hooks or ci or platforms):
            print(f"init: {project} is already initialized")
            if preset is not None:
                # Retrofitting a preset onto an initialized project: same
                # additive contract, same idempotence.
                return presets.apply(project, preset)
            return 0
        rc = _add_ons(project, manifest_path, hooks, ci,  # F5: retrofit path
                      pre_commit=pre_commit, platforms=platforms)
        if rc == 0 and preset is not None:
            rc = presets.apply(project, preset)
        return rc

    # Pre-flight the add-ons: fail loud before mutating anything, so a
    # conflict never leaves a half-initialized project with no manifest.
    hooks_dir: Path | None = None
    if hooks:
        hooks_dir, err = _resolve_hooks_dir(project)
        if hooks_dir is None:
            print(f"init: --hooks needs a git repository ({err})", file=sys.stderr)
            return 2
    agents_md = project / "AGENTS.md"
    if agents_md.is_symlink():
        # N10's .gitignore shape one file over: the reference line would
        # be written THROUGH the link into whatever the operator's link
        # points at — their dotfiles, not this project.
        print(f"init: {agents_md} is a symlink — refusing; the reference "
              "line would land in the file the link points at",
              file=sys.stderr)
        return 2
    gitignore = project / ".gitignore"
    # Runtime artifacts the plane itself creates inside tracked areas:
    # the run history (D-gitignore) and the task allocator's flock
    # anchor (#325 — dsh-mobile tracked a zero-byte .new.lock with a
    # habitual git add -A; locks are content-free, tracking them is
    # pure noise).
    ignore_lines = (".gov/history/", ".gov/tasks/.new.lock")
    ignore_line = ".gov/history/"
    if gitignore.is_symlink():
        # N13/N10: a user-managed .gitignore link (stow, dotfiles) must
        # neither be read THROUGH (external content would be copied into
        # the tracked file) nor silently replaced by a plain file.
        # Pre-flight, like every other refusal here: fail loud BEFORE
        # any mutation, never leave a half-initialized project.
        print(f"init: {gitignore} is a symlink — refusing; remove the "
              "link, or manage the ignore line yourself "
              f"('{ignore_line}/')", file=sys.stderr)
        return 2
    for name in (("pre-push",) if hooks and not pre_commit
                 else ("pre-push", "pre-commit") if hooks
                 else ()):
        if _hook_conflict(project, name, hooks_dir):
            print(
                f"init: refusing to overwrite {hooks_dir / name} — "
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

    # The memory plane's other two surfaces, seeded so `gov recall` has
    # something to search from day one: an empty decisions log and an
    # absent postmortem dir used to leave recall's indexes pointing at
    # files that did not exist — a new adopter's first weeks taught the
    # agent that recall is useless, and a lost habit never comes back.
    decisions_doc = project / "docs" / "decisions.md"
    if not decisions_doc.exists():
        # The seed is in the loader's DEFAULT format (sections): a fresh
        # install needs no .gov/decisions.json declaration, and hand
        # edits in the same format stay the path of least resistance.
        _copy(TEMPLATES.joinpath("decisions-table.md"), decisions_doc)
        created.append("docs/decisions.md")
    postmortem_readme = project / "docs" / "postmortem" / "README.md"
    if not postmortem_readme.exists():
        _copy(TEMPLATES.joinpath("postmortem-README.md"), postmortem_readme)
        created.append("docs/postmortem/README.md")

    ag = project / "AGENTS.md"
    if ag.exists():
        text = ag.read_text(encoding="utf-8")
        if REFERENCE_MARKER not in text:
            if text and not text.endswith("\n"):
                text += "\n"
            atomicio.write_text(ag, text + REFERENCE_LINE + "\n")
    else:
        atomicio.write_text(ag, REFERENCE_LINE + "\n")

    if hooks:
        _install_hook(project, "pre-push", hooks_dir)
        git_hooks.append("pre-push")
        if pre_commit:
            _install_hook(project, "pre-commit", hooks_dir)
            git_hooks.append("pre-commit")
    if ci:
        _install_ci(project, created)

    # The run ledger is local bookkeeping, not a deliverable: untracked
    # history lines used to ride every diff and trip note-presence's
    # non-trivial listing. init owns the ignore line now (idempotent;
    # an existing .gitignore is appended to, never rewritten).
    if gitignore.exists():
        # H-1: append to the original BYTES. The old code read the lines,
        # then wrote back ONLY the new line — silently destroying the
        # project's existing ignores. Byte-level append keeps CRLF
        # endings, a BOM, and any non-UTF-8 content exactly as they were
        # (and lands atomically, like every other init write).
        raw = gitignore.read_bytes()
        have = raw.decode("utf-8-sig", errors="replace").splitlines()
        missing = [ln for ln in ignore_lines if ln not in have]
        if missing:
            sep = b"" if (not raw or raw.endswith(b"\n")) else b"\n"
            _atomic_write(gitignore,
                          raw + sep
                          + b"\n".join(ln.encode("utf-8") for ln in missing)
                          + b"\n")
    else:
        # N12: same atomicity as every other init write — a torn
        # .gitignore would be frozen as project-owned by re-init's
        # guards, the exact adoption trap H-3 closed for _copy.
        atomicio.write_bytes(
            gitignore,
            b"".join((ln + "\n").encode("utf-8") for ln in ignore_lines))
        created.append(".gitignore")

    # D60: agent platforms compose with a fresh init like --hooks/--ci —
    # explicit opt-in only: a bare init's file set stays what it always
    # was, and an unselected platform never gets files.
    installed_platforms: list[str] = []
    if platforms:
        for name in platforms:
            _install_platform(project, name, created)
            installed_platforms.append(name)

    atomicio.write_text(
        gov_dir / "manifest.json",
        json.dumps(
            {"version": __version__, "created": created, "gitHooks": git_hooks,
             "platforms": installed_platforms,
             "templates": _template_hashes(project, created)},
            indent=2,
        )
        + "\n",
    )

    # Seal the fresh constitution: rules.md + gates.json are tamper-
    # evident from commit one (gov verify-plane checks the seal; a
    # re-baseline is an explicit, printed decision).
    verify_plane.baseline(project)

    print(f"init: initialized {project}")
    print("  .gov/rules.md (rules)")
    if created:
        print("  " + ", ".join(created) + " (created; project had none)")
    print("  AGENTS.md reference line")
    if hooks:
        dest = hooks_dir or Path(".git/hooks")
        print(f"  .gov/hooks/pre-push + {dest}/pre-push (runs gov run before push)")
        if pre_commit:
            print(f"  .gov/hooks/pre-commit + {dest}/pre-commit "
                  "(cheap content gates on staged files — opt-in, #110)")
    if ci and ".github/workflows/gov.yml" in created:
        print(f"  .github/workflows/gov.yml (CI runs gov run; govrail pinned "
              f"to =={__version__})")
        # #273: branch protection needs the JOB id as the required-check
        # name — say it here, where the CI was just created.
        print("  to require this workflow in branch protection, add the "
              "required status check 'gates' (the job id, not the "
              "workflow name)")

    if "gates.json" in created:
        # A read-only existence probe picks the advice (not D13's rejected
        # auto-baselining — nothing is judged or written): with no docs to
        # pair, the baseline step cannot succeed and is not suggested.
        seeded = {"decisions.md"}
        has_docs = (project / "README.md").exists() or any(
            f.name not in seeded for f in (project / "docs").glob("*.md")
        )
        # #315: "has docs" is not "has pairs" — the monolingual project
        # (the most common shape) runs the pairing baseline with nothing
        # to baseline and reads a red failure as its first gov verdict.
        # A potential counterpart anywhere in the tree, or a declared
        # pairing config, is what makes the baseline advice survivable.
        has_pairs = any(project.rglob("*.zh.md")) \
            or (project / ".gov" / "pairing.json").exists() \
            or any(project.glob("*.i18n.yaml"))
        print("next steps:")
        # #309: wiring the first PRODUCT gate is the step that makes the
        # plane worth adopting — it leads, ahead of the governance steps.
        print("  1. wire your first product gate (the shipped gates guard")
        print("     the governance plane, not your code):")
        print("       gov gate add tests --paths 'tests/**' -- pytest -q")
        print("  2. gov run                        # pairing runs advisory until baselined")
        if has_docs and has_pairs:
            print("  3. gov verify pairing --write     # baseline doc pairs (writes .i18n.yaml records)")
            print("  4. remove \"allowFailure\" from the pairing gate in gates.json to enforce")
        elif has_docs:
            print("  3. single-language project — the pairing gate stays advisory")
            print("     (or set \"enabled\": false on it in gates.json); when translated")
            print("     counterparts (e.g. README.zh.md) appear, baseline them:")
            print("     gov verify pairing --write")
        else:
            print("  3. no paired docs detected — leave pairing advisory, or disable it:")
            print("     set \"enabled\": false on the pairing gate in gates.json")
        # #251: every recovery path (git restore, --upgrade diffs, the
        # seal's drift verdicts) assumes the generated files are in git —
        # say so before the operator's first mistake, not after.
        print("  also: commit the generated governance files now — every "
              "recovery path (git restore, gov init --upgrade) assumes "
              "they are in git")
        print("  typed starters: gov preset list (python-lib / docs-bilingual / agent-heavy)")

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
        ("docs/decisions.md", TEMPLATES.joinpath("decisions-table.md")),
        ("docs/postmortem/README.md", TEMPLATES.joinpath("postmortem-README.md")),
    ]
    expected += [
        (f".agents/skills/{name}/SKILL.md", TEMPLATES.joinpath("skills") / name / "SKILL.md")
        for name in SKILLS
    ]
    if "gates.json" in created:
        expected.append(("gates.json", TEMPLATES.joinpath("gates.json")))
    if ".github/workflows/gov.yml" in created:
        expected.append((".github/workflows/gov.yml", TEMPLATES.joinpath("gov.yml")))
    for rel_p, tpl_name in PLATFORM_TARGETS.values():
        if rel_p in created:
            expected.append((rel_p, TEMPLATES.joinpath(tpl_name)))
    return expected


def adopt_missing(project: Path, manifest_path: Path, targets: list[str],
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
    # U-7: dict-MERGE (unknown manifest keys survive), atomic write, and
    # the N10 containment boundary — the pre-#275 rebuild dropped every
    # key it did not name and followed a symlinked manifest out.
    from . import atomicio
    merged_manifest = dict(data)
    merged_manifest.update({
        "version": __version__,
        "created": created,
        "gitHooks": data.get("gitHooks", []),
        "templates": recorded,
    })
    atomicio.write_text(
        manifest_path,
        json.dumps(merged_manifest, indent=2) + "\n",
        root=project,
    )
    if applied or re_adopted:
        # D34: side effects are disclosed, never silent.
        print(f"init: manifest updated — {applied} adopted, {re_adopted} "
              "re-adopted; template hashes recorded")
    return 0


def adopt_new_gates(project: Path, manifest_path: Path, target: str) -> int:
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
    for modes_line in modes_note:
        print(f"  {modes_line}")
    print("  merged gates.json passes schema validation; manifest untouched "
          "(your gates.json stays customized)")
    return 0


def upgrade_files(project: Path, manifest_path: Path):
    """The per-file drift classification the upgrade report renders:
    (files_out, init_version, tpl_paths) — files_out carries
    {path, status, era, adoptable}; tpl_paths maps rel → the template
    file backing it (relocations like .gov/rules.md ← rules.md are
    _inventory's knowledge). ``None`` when the manifest is corrupt (the
    caller names it). gov update consumes the classification to adopt
    exactly the safe files (missing + upstream-moved)."""
    import hashlib

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None, None, None
    created = set(data.get("created", []))
    init_version = data.get("version", "unknown")
    recorded = data.get("templates", {})
    expected = _inventory(created)
    opt_in = {".gov/hooks/pre-push", ".gov/hooks/pre-commit"}
    files_out = []
    tpl_paths: dict[str, Path] = {}
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
        tpl_paths[rel] = tpl
    return files_out, init_version, tpl_paths


def _deprecated_gate_commands(project: Path) -> list[tuple[str, str, list[str]]]:
    """(gate id, alias, replacement) for every gate command still spelled
    the deprecated way (#274): the upgrade report connects what `gov run`
    warns about per invocation with the config that causes it."""
    from .commands import deprecated_in
    gates_path = project / "gates.json"
    if not gates_path.is_file():
        return []
    try:
        doc = json.loads(gates_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    out: list[tuple[str, str, list[str]]] = []
    for g in doc.get("gates", []):
        if not isinstance(g, dict):
            continue
        dep = deprecated_in(g.get("command", []))
        if dep:
            alias, repl = dep
            out.append((g.get("id", "?"), alias, repl))
    return out


def _upgrade_report(project: Path, manifest_path: Path,
                    json_mode: bool = False) -> int:
    """Wish 8/D27: show how the shipped templates and this project drifted.

    Reads, never writes: per-file diff of every injected file against the
    current package template, with the manifest's init version for era
    context. Adopting a change stays a human act (D23's two-step).
    """
    import difflib

    classified, init_version, tpl_paths = upgrade_files(
        project, manifest_path)
    if classified is None:
        print(f"init: corrupt manifest {manifest_path}: cannot classify",
              file=sys.stderr)
        return 2
    current: list[str] = []
    missing: list[str] = []
    differing: list[tuple[str, Path]] = []
    for f in classified:
        rel, local = f["path"], project / f["path"]
        if f["status"] == "absent-add-on":
            continue  # absent add-on is not drift
        if f["status"] == "missing":
            missing.append(rel)
            continue
        try:
            matches = local.read_bytes() == tpl_paths[f["path"]].read_bytes()
        except OSError:
            matches = False
        if matches:
            current.append(rel)
        else:
            differing.append((rel, tpl_paths[f["path"]]))

    if json_mode:
        # Wish 6c/D30: machine-readable drift — an agent decides adoptions
        # programmatically (stdout is exactly one JSON value).
        print(json.dumps({
            "initialized_with": init_version,
            "package": __version__,
            "files": classified,
            "deprecated_commands": [
                {"gate": gid, "alias": f"gov {alias}",
                 "replacement": f"gov {' '.join(repl)}"}
                for gid, alias, repl in _deprecated_gate_commands(project)
            ],
        }, indent=2))
        return 0
    print(f"init: upgrade report for {project} — nothing is changed by this report")
    print(f"  initialized with govrail {init_version} · this package {__version__}")
    if init_version != "unknown" and init_version != __version__:
        print(f"  newer releases exist — gov whatsnew --since {init_version} "
              "shows what arrived and how to use it")
    dep = _deprecated_gate_commands(project)
    if dep:
        print("  deprecated commands in gates.json — the aliases still work,")
        print("  but every run announces them; update to the current names:")
        for gid, alias, repl in dep:
            print(f"    gate '{gid}': 'gov {alias}' → "
                  f"'gov {' '.join(repl)}'")
    for rel in current:
        print(f"  {rel:<40} matches the shipped template")
    for rel in missing:
        print(f"  {rel:<40} MISSING — adoptable: gov init --adopt {rel}")
    # D60 discoverability: a plane initialized before a platform shipped
    # should hear about it here — the drift report is where adopters look.
    # Disk existence, not created[]: an adopter-owned hook config counts
    # as present (init would only name-skip it).
    pending = [p for p, (rel, _) in PLATFORM_TARGETS.items()
               if not (project / rel).exists()]
    if pending:
        print(f"  agent platforms not installed: {', '.join(pending)} — "
              f"add with: gov init --platforms {','.join(pending)}")
    import hashlib
    recorded = json.loads(
        manifest_path.read_text(encoding="utf-8")).get("templates", {})
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
             pre_commit: bool = False,
             platforms: list[str] | None = None) -> int:
    """Install --hooks/--ci/--platforms on an already-initialized project (F5).

    Only the requested add-ons are touched — rules, gates, notes, skills,
    and the AGENTS.md reference line stay exactly as they are, so
    retrofitting a hook never resets customizations. ``platforms=None``
    keeps the pre-D60 shape (the claude config rides along); an explicit
    ``--platforms`` list replaces that default and installs exactly what
    was named.
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

    # Agent hooks (D59/D60): the plane's lifecycle events wired into each
    # selected agent platform's own hook config — presence at every point
    # of the agent's workflow, not just at push time.
    selected = list(platforms) if platforms else ["claude"]
    for name in selected:
        _install_platform(project, name, created)

    # Merge, not rebuild: the manifest's other keys (notably "templates",
    # the adoption-hash record `init --adopt` writes, D34) must survive an
    # add-on retrofit — the old three-key rewrite silently dropped them,
    # so a later `gov init --upgrade/--preview` misread every adopted file
    # as never-recorded.
    manifest = dict(data) if isinstance(data, dict) else {}
    merged_platforms = list(dict.fromkeys(
        list(manifest.get("platforms", [])) + selected))
    manifest.update({
        "version": __version__,
        "created": created,
        "gitHooks": git_hooks,
        "platforms": merged_platforms,
    })
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n",
                             encoding="utf-8")
    return 0


def _template_for(rel: str):
    """The shipped template a created file came from, if any."""
    if rel == "gates.json":
        return TEMPLATES.joinpath("gates.json")
    if rel == ".agents/notes/README.md":
        return TEMPLATES.joinpath("notes-README.md")
    if rel == ".gov/rejections/README.md":
        return TEMPLATES.joinpath("rejections-README.md")
    if rel == "docs/decisions.md":
        return TEMPLATES.joinpath("decisions-table.md")
    if rel == "docs/postmortem/README.md":
        return TEMPLATES.joinpath("postmortem-README.md")
    if rel == ".github/workflows/gov.yml":
        return TEMPLATES.joinpath("gov.yml")
    for rel_p, tpl_name in PLATFORM_TARGETS.values():
        if rel == rel_p:
            return TEMPLATES.joinpath(tpl_name)
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

    def _rendered(rel: Path, t: Path) -> bytes:
        """The template AS INIT WRITES IT: gov.yml gets the version pin
        substituted at install time, so an untouched install must not be
        misread as 'customized' by comparing against the raw template."""
        if Path(rel).name == "gov.yml":
            return t.read_text(encoding="utf-8").replace(
                "__GOV_VERSION__", __version__).encode("utf-8")
        return t.read_bytes()

    import hashlib
    try:
        recorded = json.loads(
            (project / ".gov" / "manifest.json").read_text(
                encoding="utf-8")).get("templates", {})
    except (OSError, json.JSONDecodeError, ValueError):
        recorded = {}
    for rel, t in candidates:
        p = project / rel
        try:
            if not p.is_file():
                continue
            if p.read_bytes() == _rendered(rel, t):
                continue  # pristine vs the current template
            # U-18: pristine AS ADOPTED (the template moved upstream since)
            # is equally not-customized — deletable, never mislabeled.
            local_h = hashlib.sha256(p.read_bytes()).hexdigest()
            if recorded.get(rel) == local_h:
                continue
            customized.append(rel)
        except OSError:
            pass

    # H-4: the memory plane's seeds are the project's record, not the
    # plane's config — a customized decisions log or postmortem README is
    # the adopter's scar tissue and is never deleted, not even by --force
    # (whose mandate covers the plane's own template files). A pristine
    # seed still goes: exact reversal (D10) of what init put there.
    memory = {"docs/decisions.md", "docs/postmortem/README.md"}
    kept_memory = [rel for rel in customized if rel in memory]
    for rel in kept_memory:
        print(f"uninstall: {rel} is customized project memory — "
              "leaving it in place", file=sys.stderr)
    customized = [rel for rel in customized if rel not in memory]
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
        if ag.is_symlink():
            # N10: the reference line lives in the file the link points
            # at — removing it is an edit to a file this plane does not
            # own. Named, and the operator decides.
            print(f"uninstall: {ag} is a symlink — refusing to edit "
                  "through it; remove the reference line by hand",
                  file=sys.stderr)
            return 1
        kept = [line for line in ag.read_text(encoding="utf-8").splitlines()
                if REFERENCE_MARKER not in line]
        while kept and kept[-1] == "":
            kept.pop()
        if kept:
            atomicio.write_text(ag, "\n".join(kept) + "\n",
                                root=gitutil.toplevel(str(project)))
        else:
            ag.unlink()

    for rel in data.get("created", []):
        p = project / rel
        if not p.exists():
            continue
        if rel in kept_memory:
            continue  # customized memory — named above, never deleted
        p.unlink()
        _remove_empty_dirs(p.parent)

    # H-2: remove the hooks where they ACTUALLY run — the same resolution
    # init used to install them (core.hooksPath / the worktree common
    # dir). The old hardcoded .git/hooks probe let the real hook survive
    # uninstall, so pushes kept invoking the now-gone gov and hung. And a
    # manifest-listed name is only unlinked when it still IS a gov hook:
    # the mirror of init's refuse-to-overwrite guard — a foreign script
    # is the project's, never ours to delete.
    hooks_dir, _hooks_err = _resolve_hooks_dir(project)
    for name in data.get("gitHooks", []):
        p = (hooks_dir or project / ".git" / "hooks") / name
        if not p.exists():
            continue
        try:
            is_gov = HOOK_MARKER in p.read_text(encoding="utf-8",
                                                errors="replace")
        except OSError:
            is_gov = False
        if not is_gov:
            print(f"uninstall: {p} is not a gov hook — leaving it",
                  file=sys.stderr)
            continue
        p.unlink()

    shutil.rmtree(project / ".gov", ignore_errors=True)
    print(f"uninstall: removed governance from {project}")
    return 0
