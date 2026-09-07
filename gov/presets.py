#!/usr/bin/env python3
"""Presets: typed adoption bundles shipped with the plane (D53).

``gov init`` injects one set of generic gates — typed content varies by
project and stays out of the default template (D28). A preset is the
answer for "my project type needs a coherent starting set": a declarative
patch bundle — gate fragments, agent skills, manifest hints — that lands
through the plane's EXISTING adoption machinery, never overwriting local
customizations:

- gates merge additively by id (D39's semantics, the same machine as
  ``init --adopt-new``; a same-id local gate is kept — it is the adopted
  state, and a difference is named);
- mode declarations converge: created when absent, an existing mode
  gains every declared id it lacks — adopted this round or already
  local — with local membership and its order untouched, so apply lands
  the project on the declared state even when the gates arrived in an
  earlier round; an id no gate in the project carries is skipped and
  named;
- skills copy byte-for-byte, create-if-missing (D29's contract; an
  existing skill is skipped and named);
- hints write only manifest keys that are absent (D49's contract: the
  local value always wins, and the notice says so).

Apply is idempotent: on an already-adopted repository every item reports
"already adopted", exit 0, zero writes. Adopting into a project that was
never initialized refuses loud (run ``gov init`` first, or start with
``gov init --preset <name>``) — a preset never improvises half a project.

The bundle schema is strict (rule 5): unknown keys, bad types, a gate
object that fails the real gates.json schema, or a mode naming a gate
outside the bundle's gates plus the shipped template exit 2 naming the
preset and the key. Presets are declarative data, not code: they define
WHAT lands; the adoption machinery defines HOW — the one gates-merge
machine (``gates.merge_gates_by_id``) with two documented mode rulings
(D39's added-only for ``--adopt-new``, membership-converging for
presets).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from importlib.resources import files
from pathlib import Path

try:  # package context (`gov preset ...`)
    from . import gates as gates_mod
except ImportError:  # direct script execution (self-test scratch dirs)
    import gates as gates_mod

TEMPLATES = files("gov.templates")
PRESETS = "presets"
PRESET_FILE = "preset.json"
GATES_JSON = "gates.json"
MANIFEST = ".gov/manifest.json"
SKILL_FILE = "SKILL.md"
SKILL_DEST = ".agents/skills"
# Closed key set: name/description required; the rest optional.
TOP_KEYS = {"name", "description", "gates", "modes", "skills", "hints"}
# The manifest keys a preset may declare. Closed on purpose: a preset may
# only write manifest keys the plane has a declared reader for (D49's
# note_presence_exempt is the precedent) — anything else would be a
# write-into-nowhere.
HINT_KEYS = {"note_presence_exempt"}


class PresetError(Exception):
    """A preset bundle is unknown or malformed; name the preset and key."""


def presets_root(root: Path | None = None):
    """The preset directory: ``root`` (tests' fake bundle tree) or shipped."""
    return root if root is not None else TEMPLATES.joinpath(PRESETS)


def available(root: Path | None = None) -> list[str]:
    """Shipped preset names (a directory holding a ``preset.json``)."""
    base = presets_root(root)
    try:
        return sorted(
            p.name for p in base.iterdir()
            if p.is_dir() and p.joinpath(PRESET_FILE).is_file()
        )
    except (OSError, FileNotFoundError, NotADirectoryError):
        return []


def _template_gate_ids() -> set[str]:
    """Gate ids the shipped gates.json template carries (D39's other half
    of the mode-reference check: a preset mode may point at a template
    gate too, e.g. appending to the template's own ``governance`` mode)."""
    try:
        doc = json.loads(TEMPLATES.joinpath(GATES_JSON).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise PresetError(f"cannot read the shipped {GATES_JSON} template: {e}")
    return {
        g["id"] for g in doc.get("gates", [])
        if isinstance(g, dict) and isinstance(g.get("id"), str)
    }


def load(name: str, root: Path | None = None) -> dict:
    """Parse and validate one preset bundle; raise PresetError when bad.

    ``root`` overrides the shipped bundle tree (tests exercise rejection
    cases against temporary bundles without writing into the package).
    """
    known = available(root)
    if name not in known:
        raise PresetError(
            f"unknown preset '{name}' "
            f"(available: {', '.join(known) if known else 'none'})")
    bundle_dir = presets_root(root) / name
    path = bundle_dir / PRESET_FILE
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as e:
        raise PresetError(f"cannot read {name}/{PRESET_FILE}: {e}")
    except json.JSONDecodeError as e:
        raise PresetError(f"{name}/{PRESET_FILE} is not valid JSON: {e}")
    if not isinstance(raw, dict):
        raise PresetError(f"{name}/{PRESET_FILE} must be a JSON object")
    unknown = sorted(set(raw) - TOP_KEYS)
    if unknown:
        raise PresetError(
            f"preset '{name}': unknown key(s): {', '.join(unknown)} "
            f"(known: {', '.join(sorted(TOP_KEYS))})")
    for key in ("name", "description"):
        value = raw.get(key)
        if not isinstance(value, str) or not value:
            raise PresetError(
                f"preset '{name}': '{key}' is required and must be a "
                "non-empty string")
    if raw["name"] != name:
        raise PresetError(
            f"preset '{name}': 'name' is {raw['name']!r} — it must match "
            "the bundle directory")
    gates_raw = raw.get("gates", [])
    if not isinstance(gates_raw, list) \
            or any(not isinstance(g, dict) for g in gates_raw):
        raise PresetError(
            f"preset '{name}': 'gates' must be an array of gate objects")
    modes_raw = raw.get("modes", {})
    if not isinstance(modes_raw, dict) or any(
            not isinstance(ids, list) or not all(isinstance(x, str) for x in ids)
            for ids in modes_raw.values()):
        raise PresetError(
            f"preset '{name}': 'modes' must map mode names to arrays of gate ids")
    skills_raw = raw.get("skills", [])
    if not isinstance(skills_raw, list) \
            or any(not isinstance(s, str) or not s for s in skills_raw):
        raise PresetError(
            f"preset '{name}': 'skills' must be an array of non-empty skill names")
    hints_raw = raw.get("hints", {})
    if not isinstance(hints_raw, dict):
        raise PresetError(f"preset '{name}': 'hints' must be an object")
    unknown_hints = sorted(set(hints_raw) - HINT_KEYS)
    if unknown_hints:
        raise PresetError(
            f"preset '{name}': unknown hint key(s): {', '.join(unknown_hints)} "
            f"(known: {', '.join(sorted(HINT_KEYS))})")
    for key, value in hints_raw.items():
        if not isinstance(value, list) \
                or any(not isinstance(x, str) or not x.strip() for x in value):
            raise PresetError(
                f"preset '{name}': hint '{key}' must be an array of "
                "non-empty strings")
    # Gate objects must pass the real gates.json schema (D39's shape rule):
    # duplicate ids, malformed commands, unknown needs, cycles — judged by
    # the same loader the runner uses, never a parallel validator.
    if gates_raw:
        fd, tmp = tempfile.mkstemp(suffix=".gates.json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"gates": gates_raw}, f)
            gates_mod.load_config(tmp)
        except gates_mod.ConfigError as e:
            raise PresetError(
                f"preset '{name}': gates fragment fails the gates.json "
                f"schema: {e}")
        finally:
            os.unlink(tmp)
    known_ids = {g["id"] for g in gates_raw} | _template_gate_ids()
    for mode, ids in modes_raw.items():
        ghosts = [g for g in ids if g not in known_ids]
        if ghosts:
            raise PresetError(
                f"preset '{name}': mode '{mode}' references gate(s) outside "
                f"the preset and the shipped template: {', '.join(ghosts)}")
    for skill in skills_raw:
        if not (bundle_dir / "skills" / skill / SKILL_FILE).is_file():
            raise PresetError(
                f"preset '{name}': skill '{skill}' has no "
                f"{PRESETS}/{name}/skills/{skill}/{SKILL_FILE}")
    return raw


def list_presets(root: Path | None = None) -> int:
    """`gov preset list` — names and descriptions, read-only."""
    known = available(root)
    if not known:
        print("gov preset: no presets shipped in this package")
        return 0
    broken = False
    for name in known:
        try:
            bundle = load(name, root)
            print(f"{name:<16} {bundle['description']}")
        except PresetError as e:
            broken = True
            print(f"{name:<16} BROKEN BUNDLE — {e}", file=sys.stderr)
    if broken:
        # A shipped bundle that cannot load is a package defect: say so
        # loudly (rule 5), after listing everything that did load.
        print("gov preset: broken bundle(s) above — preset is a defect in "
              "this package, please report it", file=sys.stderr)
        return 2
    return 0


def show(name: str, root: Path | None = None) -> int:
    """`gov preset show <name>` — exactly what applying would land, read-only."""
    try:
        bundle = load(name, root)
    except PresetError as e:
        print(f"gov preset: {e}", file=sys.stderr)
        return 2
    print(f"preset '{bundle['name']}' — {bundle['description']}")
    print("applying lands, additively (a local file or value is never overwritten):")
    for g in bundle.get("gates", []):
        line = f"  gate {g['id']}"
        if g.get("label"):
            line += f" — {g['label']}"
        print(line + "   (merged into gates.json by id, D39)")
        print(f"    command: {' '.join(g['command'])}")
        if g.get("paths"):
            print(f"    paths: {', '.join(g['paths'])}")
    for mode, ids in (bundle.get("modes") or {}).items():
        print(f"  mode '{mode}' += {', '.join(ids)} (created when absent; "
              "an existing mode gains the ids it lacks, order preserved)")
    for skill in bundle.get("skills", []):
        print(f"  skill {SKILL_DEST}/{skill}/{SKILL_FILE} "
              "(copied byte-for-byte when missing, D29)")
    for key, value in (bundle.get("hints") or {}).items():
        print(f"  manifest hint {key} = {json.dumps(value)} "
              "(written only when the key is absent, D49)")
    print("show is read-only — `gov preset apply "
          f"{bundle['name']}` lands the above")
    return 0


def _read_json(path: Path, what: str) -> tuple[dict | None, str]:
    """``(data, "")`` or ``(None, error)`` — the caller fails loud named."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        return None, f"gov preset: cannot read {what} {path}: {e}"
    if not isinstance(data, dict):
        return None, f"gov preset: {what} {path} must be a JSON object"
    return data, ""


def _gates_doc(doc: dict, what: str) -> list[dict] | None:
    """Structural check shared with --adopt-new: a 'gates' array of
    objects carrying string ids, else None for the caller to fail loud."""
    gates = doc.get("gates")
    if not isinstance(gates, list) or any(
            not isinstance(g, dict) or not isinstance(g.get("id"), str)
            or not g["id"] for g in gates):
        print(f"gov preset: {what} is structurally invalid (needs a "
              "'gates' array of objects carrying string ids)", file=sys.stderr)
        return None
    return gates


def apply(project: Path, name: str, root: Path | None = None) -> int:
    """`gov preset apply <name>` — land the bundle, additively, idempotent.

    The contract, hard-coded: presets adopt into an INITIALIZED project
    (the gates fragment merges into gates.json; hints land in the
    manifest the plane already keeps). A bare apply without init refuses
    loud instead of creating a half-project; ``gov init --preset <name>``
    composes the two for a new project.
    """
    try:
        bundle = load(name, root)
    except PresetError as e:
        print(f"gov preset: {e}", file=sys.stderr)
        return 2
    project = project.resolve()
    gates_path = project / GATES_JSON
    manifest_path = project / MANIFEST
    missing = GATES_JSON if not gates_path.exists() else (
        MANIFEST if not manifest_path.exists() else None)
    if missing is not None:
        print(f"gov preset: {missing} not found in {project} — presets adopt "
              "into an initialized project; run `gov init` first (or start "
              f"with `gov init --preset {name}`)", file=sys.stderr)
        return 2

    wrote = False
    print(f"preset: applying '{name}' to {project}")

    # a. gates fragment: D39's additive merge (same machine as --adopt-new,
    #    with the preset ruling: a same-id local gate is kept, not refused).
    local_doc, err = _read_json(gates_path, GATES_JSON)
    if local_doc is None:
        print(err, file=sys.stderr)
        return 2
    if _gates_doc(local_doc, GATES_JSON) is None:
        return 2
    merged, added, notices = gates_mod.merge_gates_by_id(
        local_doc,
        {"gates": bundle.get("gates", []), "modes": bundle.get("modes", {})},
        what=f"preset '{name}'",
        on_drift="keep",
        mode_membership="converge",
    )
    # Convergence: membership may move even when every gate is already
    # adopted (a drifted or hand-wired project must land on the declared
    # state; a fully converged one reports zero writes below).
    modes_changed = merged.get("modes") != local_doc.get("modes")
    if added or modes_changed:
        text = json.dumps(merged, indent=2) + "\n"
        # Validate before landing — never write a gates.json the runner
        # itself would reject (rule 6 in spirit, D39's own order).
        fd, tmp = tempfile.mkstemp(dir=project, suffix=".gates.json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            gates_mod.load_config(tmp)
        except Exception as e:  # noqa: BLE001 — any validation failure is fatal
            os.unlink(tmp)
            print(f"gov preset: apply refused — merged gates.json fails "
                  f"schema validation: {e}", file=sys.stderr)
            return 2
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        gates_path.write_text(text, encoding="utf-8")
        wrote = True
        if added:
            print(f"  gates: added {len(added)} (in preset order): "
                  + ", ".join(g["id"] for g in added))
        else:
            print("  gates: nothing to add")
    else:
        print("  gates: nothing to add")
    for notice in notices:
        print(f"    {notice}")

    # b. skills: byte-for-byte, create-if-missing (D29).
    for skill in bundle.get("skills", []):
        src = presets_root(root) / name / "skills" / skill / SKILL_FILE
        dest = project / SKILL_DEST / skill / SKILL_FILE
        if dest.exists():
            print(f"  skill: {SKILL_DEST}/{skill}/{SKILL_FILE} already "
                  "present — untouched (a project's own skill is never "
                  "overwritten)")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        wrote = True
        print(f"  skill: created {SKILL_DEST}/{skill}/{SKILL_FILE}")

    # c. hints: only manifest keys that are absent (D49 — the local value
    #    always wins, and the notice says so).
    hints = bundle.get("hints") or {}
    if hints:
        manifest, err = _read_json(manifest_path, "manifest")
        if manifest is None:
            print(err, file=sys.stderr)
            return 2
        changed = False
        for key, value in hints.items():
            if key in manifest:
                print(f"  hint: '{key}' already in the manifest — local "
                      f"value kept ({json.dumps(manifest[key])})")
                continue
            manifest[key] = value
            changed = True
            print(f"  hint: wrote manifest '{key}' = {json.dumps(value)}")
        if changed:
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            wrote = True

    if not wrote:
        print(f"preset: '{name}' already adopted — nothing written")
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        from .root import force_utf8_stdio
    except ImportError:  # direct-script execution (self-test scratch dirs)
        from root import force_utf8_stdio
    force_utf8_stdio()  # reports leave as UTF-8 on every OS (#168)
    parser = argparse.ArgumentParser(
        prog="gov preset",
        description="Typed adoption bundles: gates, skills, and manifest "
                    "hints for a project type — additive, never overwriting "
                    "(D53).")
    sub = parser.add_subparsers(dest="subcommand")
    sub.add_parser("list", help="list the shipped presets and descriptions")
    p_show = sub.add_parser(
        "show", help="print everything a preset would land (read-only)")
    p_show.add_argument("name", metavar="NAME")
    p_apply = sub.add_parser(
        "apply", help="land a preset into an initialized project, "
                      "additively and idempotently")
    p_apply.add_argument("name", metavar="NAME")
    p_apply.add_argument("--project", default=".", metavar="DIR",
                         help="target project root (default: current directory)")
    args = parser.parse_args(argv)
    if args.subcommand is None:
        parser.error("a subcommand is required (list|show|apply)")
    if args.subcommand == "list":
        return list_presets()
    if args.subcommand == "show":
        return show(args.name)
    return apply(Path(args.project), args.name)


if __name__ == "__main__":
    raise SystemExit(main())
