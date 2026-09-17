"""Template/specimen sync — the mechanical-copy relations, pinned.

The plane owns several files that exist in multiple copies with NO
local variation allowed (live, shipped template, demo specimen). Each
relation below is a copy, not a judgment: a red test names
scripts/sync_demo_specimen.py as the fix. The gates merge is the one
structured relation: the shipped template is the base the demo adopts,
the demo's own typed extras ride on top, and retired eras (self-test
in an adopter DAG, pre-stages, pre-timeout shapes) must not reappear.

Also pinned here: the CI template adopters receive
(gov/templates/gov.yml) carries the structural hygiene this repo's own
CI learned the hard way — single-run triggers, a concurrency group, a
timeout budget.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

REPO = Path(__file__).resolve().parent.parent
DEMO = REPO / "examples" / "demo-project"

SKILLS = ["recall-first", "pre-push-checks", "code-review",
          "archive-agent-notes"]


def _same(a: Path, b: Path) -> bool:
    return a.read_bytes() == b.read_bytes()


def test_live_matches_shipped_template():
    """init injects these create-if-missing; drift between the repo's
    own copy and the shipped one means adopters see a different plane."""
    pairs = [
        (REPO / ".gov/rules.md", REPO / "gov/templates/rules.md"),
        (REPO / ".agents/notes/README.md",
         REPO / "gov/templates/notes-README.md"),
        (REPO / ".gov/rejections/README.md",
         REPO / "gov/templates/rejections-README.md"),
    ] + [
        (REPO / f".agents/skills/{s}/SKILL.md",
         REPO / f"gov/templates/skills/{s}/SKILL.md")
        for s in SKILLS
    ]
    for live, tpl in pairs:
        assert _same(live, tpl), (
            f"{live.relative_to(REPO)} drifted from the shipped template — "
            "copy one onto the other (they are the same file)")


def test_demo_specimen_matches_the_plane():
    """The demo is the living specimen: byte-for-byte current on every
    plane-owned file. Red = run scripts/sync_demo_specimen.py."""
    pairs = [
        (REPO / f".agents/skills/{s}/SKILL.md",
         DEMO / f".agents/skills/{s}/SKILL.md")
        for s in SKILLS
    ] + [
        (REPO / ".gov/rules.md", DEMO / ".gov/rules.md"),
        (REPO / ".agents/notes/README.md", DEMO / ".agents/notes/README.md"),
        (REPO / ".gov/rejections/README.md",
         DEMO / ".gov/rejections/README.md"),
    ]
    for src, dst in pairs:
        assert _same(src, dst), (
            f"{dst.relative_to(REPO)} is stale — run "
            "scripts/sync_demo_specimen.py")
    live_cases = {p.name for p in (REPO / ".gov/rejections").glob("case-*.sh")}
    demo_cases = {p.name for p in (DEMO / ".gov/rejections").glob("case-*.sh")}
    demo_own = {"rubric", "decisions", "source-limits"}
    legal_extras = {f"case-{gid}.sh" for gid in demo_own}
    assert live_cases <= demo_cases, (
        f"demo missing rejection case(s) {sorted(live_cases - demo_cases)} — "
        "run scripts/sync_demo_specimen.py")
    extra = demo_cases - live_cases
    assert extra <= legal_extras, (
        f"demo carries case(s) {sorted(extra - legal_extras)} that belong to "
        "no gate of its own — stray copies drift; remove them")
    for name in live_cases:
        assert _same(REPO / ".gov/rejections" / name,
                     DEMO / ".gov/rejections" / name), (
            f"demo's {name} differs from the live case — run "
            "scripts/sync_demo_specimen.py")


def test_demo_gates_adopt_the_template_base():
    """The demo's gates.json is the shipped template PLUS its typed
    extras (rubric/decisions/source-limits) — never a retired era."""
    template = json.loads(
        (REPO / "gov/templates/gates.json").read_text(encoding="utf-8"))
    demo = json.loads((DEMO / "gates.json").read_text(encoding="utf-8"))
    tpl_ids = {g["id"] for g in template["gates"]}
    demo_ids = {g["id"] for g in demo["gates"]}
    assert tpl_ids <= demo_ids, (
        f"demo gates lack template gate(s) {sorted(tpl_ids - demo_ids)} — "
        "run scripts/sync_demo_specimen.py")
    assert "self-test" not in demo_ids, (
        "self-test in an adopter DAG was retired (D4) — the demo must not "
        "carry it back")
    demo_by_id = {g["id"]: g for g in demo["gates"]}
    for g in template["gates"]:
        assert demo_by_id[g["id"]] == g, (
            f"demo's {g['id']} gate differs from the shipped template — "
            "run scripts/sync_demo_specimen.py")


def test_ci_template_carries_the_hard_won_hygiene():
    """Adopters receive gov/templates/gov.yml via `gov init --ci`; it
    must carry the same structural hygiene this repo's CI learned:
    single-run triggers (no double matrix per change), a concurrency
    group (no interleaving stale runs), a timeout budget (no 6-hour
    hangs), and the stable job name for branch protection."""
    tpl = yaml.safe_load(
        (REPO / "gov/templates/gov.yml").read_text(encoding="utf-8"))
    on = tpl.get(True) or tpl.get("on")
    push = on.get("push")
    assert isinstance(push, dict) and push.get("branches"), (
        "template CI: push must be branch-filtered — an unfiltered push "
        "hook runs the adopter's DAG twice per change (the #194 lesson)")
    assert "pull_request" in on
    conc = tpl.get("concurrency") or {}
    assert conc.get("group") and conc.get("cancel-in-progress") is True, (
        "template CI: needs a concurrency group — superseded runs must "
        "cancel, or their late verdicts masquerade as branch state")
    for name, job in tpl["jobs"].items():
        assert isinstance(job.get("timeout-minutes"), int), (
            f"template CI job {name!r} needs a timeout-minutes budget")
    assert "gates" in tpl["jobs"], (
        "the template's job name is the adopter's stable required-check "
        "name — renaming it makes branch protection unsatisfiable (#193)")
