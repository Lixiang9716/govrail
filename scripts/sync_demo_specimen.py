#!/usr/bin/env python3
"""Sync the demo specimen from the plane's own sources — mechanically.

The demo (examples/demo-project) is the LIVING SPECIMEN an adopter
compares against and the docker e2e exercises (demo_specimen). Every
plane-owned file in it is a COPY with no local variation, so syncing is
a mechanical copy — never hand-edited, never agent-judged. The gates
merge is the one structured step: the shipped template is the base,
the demo's own gates (its typed extras) are carried over, and nothing
from a retired era (self-test, the pre-D4 adopter DAG) survives.

tests/test_template_sync.py pins every relation this script maintains;
a red test names this script as the fix.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEMO = REPO / "examples" / "demo-project"

# (source, destination) — byte-for-byte copies, no variation allowed
COPY_MAP = [
    (REPO / ".agents/skills/govrail/SKILL.md",
     DEMO / ".agents/skills/govrail/SKILL.md"),
    (REPO / ".agents/skills/recall-first/SKILL.md",
     DEMO / ".agents/skills/recall-first/SKILL.md"),
    (REPO / ".agents/skills/pre-push-checks/SKILL.md",
     DEMO / ".agents/skills/pre-push-checks/SKILL.md"),
    (REPO / ".agents/skills/code-review/SKILL.md",
     DEMO / ".agents/skills/code-review/SKILL.md"),
    (REPO / ".agents/skills/archive-agent-notes/SKILL.md",
     DEMO / ".agents/skills/archive-agent-notes/SKILL.md"),
    (REPO / ".agents/skills/parallel-workers/SKILL.md",
     REPO / "gov/templates/presets/agent-heavy/skills"
     / "parallel-workers/SKILL.md"),
    (REPO / "gov/templates/rules.md", DEMO / ".gov/rules.md"),
    (REPO / "gov/templates/notes-README.md", DEMO / ".agents/notes/README.md"),
    (REPO / ".gov/rejections/README.md", DEMO / ".gov/rejections/README.md"),
]

# demo's own gates, carried over the template base verbatim
DEMO_EXTRA_GATES = {"rubric", "decisions", "source-limits"}

# Self-hosted cases: they judge the govrail REPO itself (they run the
# scripts/ checkers and need ruff) — the demo has neither, so these
# cases never ship to the specimen and a leaked copy is pruned.
REPO_ONLY_CASES = {"case-import-layers.sh", "case-size-limits.sh",
                   "case-lint.sh"}


def sync_copies() -> int:
    n = 0
    for src, dst in COPY_MAP:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.is_file() or dst.read_bytes() != src.read_bytes():
            shutil.copyfile(src, dst)
            print(f"copied {src.relative_to(REPO)} -> {dst.relative_to(REPO)}")
            n += 1
    for case in sorted((REPO / ".gov/rejections").glob("case-*.sh")):
        if case.name in REPO_ONLY_CASES:
            continue
        dst = DEMO / ".gov/rejections" / case.name
        if not dst.is_file() or dst.read_bytes() != case.read_bytes():
            shutil.copyfile(case, dst)
            dst.chmod(0o755)
            print(f"copied {case.name} -> demo")
            n += 1
    for leaked in sorted((DEMO / ".gov/rejections").glob("case-*.sh")):
        if leaked.name in REPO_ONLY_CASES:
            leaked.unlink()
            print(f"pruned repo-only {leaked.name} from demo")
            n += 1
    return n


def sync_gates() -> int:
    template = json.loads(
        (REPO / "gov/templates/gates.json").read_text(encoding="utf-8"))
    demo_path = DEMO / "gates.json"
    demo = json.loads(demo_path.read_text(encoding="utf-8"))
    demo_own = {g["id"]: g for g in demo["gates"]
                if g["id"] in DEMO_EXTRA_GATES}

    merged_gates = [g for g in template["gates"]] + \
        [demo_own[gid] for gid in sorted(demo_own)]
    merged_modes = {
        "all": [gid for gid in template["modes"]["all"]]
        + sorted(demo_own),
        "quick": demo["modes"].get("quick", template["modes"]["quick"]),
        "governance": template["modes"]["governance"],
    }
    merged = {
        "modes": merged_modes,
        "defaultMode": template.get("defaultMode", "all"),
        "concurrency": demo.get("concurrency", 4),
        "gates": merged_gates,
    }
    if merged != demo:
        demo_path.write_text(
            json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        print("merged gates.json (template base + demo extras, "
              f"{sorted(demo_own)}; retired eras dropped)")
        return 1
    return 0


def main() -> int:
    changed = sync_copies() + sync_gates()
    if changed:
        sys.path.insert(0, str(REPO))
        from gov import verify_plane
        verify_plane.baseline(DEMO, unattended=True)
        print("re-sealed the demo's plane seal over the synced state")
    else:
        print("sync: nothing to do — the specimen is current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
