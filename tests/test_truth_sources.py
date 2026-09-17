"""Truth-source pins — the register's own rule: a row without a pin is a
row that can lie (docs/truth-sources.md).

Four relations that lived unpinned until the register's audit found
them: the pairing example in the i18n README vs DEFAULT_CONFIG, the
note taxonomy vs its README enumeration, the shipped-gate full set
across two files, and the agent-heavy preset's skill copy.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from gov import doctor, note, verify_notes
from gov import verify_translation_pairing as vtp

REPO = Path(__file__).resolve().parent.parent


def _example_json(doc: Path) -> dict:
    text = doc.read_text(encoding="utf-8")
    blocks = re.findall(r"```json\n(.*?)```", text, re.S)
    parsed = [json.loads(b) for b in blocks]
    pairing = [p for p in parsed if "counterparts" in p]
    assert pairing, f"{doc} lost its pairing example block"
    return pairing[0]


@pytest.mark.parametrize("doc", [
    REPO / "docs/i18n/README.md",
    REPO / "docs/i18n/README.zh.md",
])
def test_i18n_readme_example_matches_default_config(doc):
    """Row 4 of the register: the example is a COPY of DEFAULT_CONFIG —
    it had already drifted (missing the postmortem exclusion) when it
    had no pin."""
    example = _example_json(doc)
    assert example == vtp.DEFAULT_CONFIG, (
        f"{doc.name}'s pairing example drifted from "
        "verify_translation_pairing.DEFAULT_CONFIG — the example is a "
        "copy, fix it to match")


def test_note_taxonomy_enumerated_in_the_readme():
    """Row 5: CLASSES and LIFECYCLES are closed sets; the notes README
    is where humans read them. Adding a class touches both — a missed
    side goes red here."""
    readme = (REPO / "gov/templates/notes-README.md").read_text(
        encoding="utf-8")
    for cls in note.CLASSES:
        assert re.search(rf"\b{re.escape(cls)}\b", readme), (
            f"note class {cls!r} missing from the notes README — the "
            "closed set and its documentation must move together")
    for lifecycle in verify_notes.LIFECYCLES:
        assert re.search(rf"\b{re.escape(lifecycle)}\b", readme), (
            f"note lifecycle {lifecycle!r} missing from the notes README")


def test_every_verify_tool_is_in_the_shipped_gate_set():
    """Row 6: the shipped-gate full set spans TWO files (the template's
    gates.json and doctor's HAND_SHIPPED_GATES). A new verify-* tool
    that lands in neither is invisible to every adoption check — the
    exact #147 failure mode, now structural."""
    # module stem -> CLI command where the names differ (the CLI
    # shortened one historical module name; everything else is the
    # mechanical underscore-to-dash of the stem)
    command_alias = {"verify_translation_pairing": "verify-pairing"}
    template = json.loads(
        (REPO / "gov/templates/gates.json").read_text(encoding="utf-8"))
    template_cmds = {
        tok for g in template["gates"] for tok in g["command"]
        if tok.startswith("verify-")}
    hand_cmds = {tool for tool, _ in doctor.HAND_SHIPPED_GATES.values()}
    covered_cmds = template_cmds | hand_cmds
    tools = sorted(p.stem for p in (REPO / "gov").glob("verify_*.py"))
    missing = [t for t in tools
               if command_alias.get(t, t.replace("_", "-"))
               not in covered_cmds]
    assert not missing, (
        f"verify tool(s) {missing} ship in neither the template's "
        "gates.json nor doctor.HAND_SHIPPED_GATES — wire one (or exempt "
        "deliberately in this test with a reason)")


def test_preset_skill_copy_matches_the_live_skill():
    """Row 15, the fourth copy: the agent-heavy preset ships
    parallel-workers; its SKILL.md is the live one, byte for byte."""
    live = REPO / ".agents/skills/parallel-workers/SKILL.md"
    preset = (REPO / "gov/templates/presets/agent-heavy/skills"
              / "parallel-workers/SKILL.md")
    assert preset.is_file(), "the agent-heavy preset lost its skill payload"
    assert live.read_bytes() == preset.read_bytes(), (
        "the preset's parallel-workers copy drifted from the live skill — "
        "copy the live one over it (they are the same file)")
