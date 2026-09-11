"""The differential proof for the encoding= checks (D54's last clause).

The #172-era scanner (``gov/self_test.py:_unpinned_text_spawns`` until
this PR) was a regex + balanced-paren hand-roll. This module keeps it,
VERBATIM, as the reference implementation, and proves the tree-sitter
rule against it on a synthetic corpus whose answer is known by
construction:

- on every case where the old scanner was RIGHT, the new rule must agree
  exactly (same file:line set);
- on the two classes where the old scanner was WRONG BY CONSTRUCTION —
  calls inside string literals or comments (a regex cannot see the
  token layer), and ``universal_newlines`` with a non-true value (the
  old substring test ignored the value) — the new rule must be quiet.
  The new rule is never allowed to find MORE than the reference: that
  would be a regression dressed as strictness.

Plus real-world parity: over this repository's ``gov/`` package both
implementations must agree (today: both clean — the #168/#173 wall
pinned everything).
"""
import sys
from pathlib import Path

import pytest

from gov import checks, parse

HERE = Path(__file__).resolve().parent.parent
GOV_DIR = HERE / "gov"


def reference_unpinned_text_spawns(src: str, where: str) -> list[str]:
    """VERBATIM copy of the pre-D54 regex scanner (gov/self_test.py).

    The original docstring: "``file:line`` of every text-mode subprocess
    call missing an encoding. ... Call bodies are captured by
    balanced-paren scan so multiline invocations read whole."
    Kept as the differential reference — deleting it would make the new
    rule's correctness self-certified.
    """
    import re
    bad: list[str] = []
    for m in re.finditer(r"subprocess\.(?:run|Popen|check_output)\s*\(", src):
        start = m.end() - 1
        depth = 0
        i = start
        while i < len(src):
            if src[i] == "(":
                depth += 1
            elif src[i] == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        call = src[start:i + 1]
        is_text = "text=True" in call or "universal_newlines" in call
        if is_text and "encoding=" not in call:
            bad.append(f"{where}:{src[:m.start()].count(chr(10)) + 1}")
    return bad


def _engine_lines(source: str, name: str) -> set[str]:
    """The shipped rule's findings for one in-memory source."""
    rules = [r for r in checks.load_rules("python", include_project=False)
             if r.id == "python/subprocess-text-encoding"]
    pack = parse.load_pack("python")
    checks._pack_cache["python"] = pack
    parser = parse.load_parser(pack)
    tree = parser.parse(source.encode("utf-8"))
    comments = checks._collect_comments(tree.root_node, pack.comment)
    findings = checks.check_tree(source.encode("utf-8"), tree, comments,
                                 "python", rules)
    return {f"{name}:{f.line()}" for f in findings
            if not f.suppressed and f.severity == "error"}


# (name, source, old_falls_in) — old_falls_in marks the fixtures built to
# expose a documented old-scanner false-positive class: there the new rule
# MUST be strictly quieter; everywhere else it must match exactly.
CORPUS = [
    ("pinned", 'subprocess.run(cmd, capture_output=True, text=True, '
               'encoding="utf-8")\n', False),
    ("unpinned", 'subprocess.run(cmd, capture_output=True, text=True)\n',
     False),
    ("multiline", 'subprocess.run(\n    cmd,\n    text=True,\n)\n', False),
    ("universal_newlines_true",
     'subprocess.Popen(cmd, universal_newlines=True)\n', False),
    ("check_output", 'subprocess.check_output(cmd, text=True)\n', False),
    ("binary", 'subprocess.run(cmd, capture_output=True)\n', False),
    ("nested_args", 'subprocess.run(make(cmd), text=True)\n', False),
    ("encoding_multiline",
     'subprocess.run(\n    cmd,\n    text=True,\n    encoding="utf-8")\n',
     False),
    # --- the old scanner's documented false-positive classes ---
    ("in_string",
     'CODE = "subprocess.run(cmd, text=True)"\n', True),
    ("in_comment", '# subprocess.run(cmd, text=True)\n', True),
    ("universal_newlines_false",
     'subprocess.run(cmd, universal_newlines=False)\n', True),
    # --- a blind spot shared by both (kwargs) — parity, not a delta ---
    ("kwargs_shaped", 'subprocess.run(cmd, **opts)\n', False),
]


@pytest.mark.parametrize("name,source,old_falls_in", CORPUS,
                         ids=[c[0] for c in CORPUS])
def test_engine_matches_reference(name, source, old_falls_in, tmp_path):
    f = tmp_path / "case.py"
    f.write_text(source, encoding="utf-8")
    old = set(reference_unpinned_text_spawns(source, "case.py"))
    new = _engine_lines(source, "case.py")
    if old_falls_in:
        assert new < old or (not new and old), (
            f"{name}: the new rule must be strictly quieter here "
            f"(old={old}, new={new})")
    else:
        assert new == old, f"{name}: parity required (old={old}, new={new})"


def test_real_package_parity_both_clean():
    """Over gov/ as it stands, both implementations agree — and agree on
    clean: the #168/#173 wall pinned every spawn."""
    old: set[str] = set()
    for p in sorted(GOV_DIR.rglob("*.py")):
        old.update(reference_unpinned_text_spawns(
            p.read_text(encoding="utf-8"), p.relative_to(GOV_DIR).as_posix()))
    rules = [r for r in checks.load_rules("python", include_project=False)
             if r.id == "python/subprocess-text-encoding"]
    reports = checks.run_lang(GOV_DIR, "python", rules)
    new = {f"{f.path}:{f.line()}" for r in reports
           for f in r.findings if not f.suppressed}
    assert old == new == set()


def test_supersession_note():
    """The reference must stay byte-honest with what shipped before:
    this pins the known-answer shapes the old pytest suite pinned, now
    against the preserved reference itself."""
    bad = 'subprocess.run(cmd, capture_output=True, text=True)'
    good = ('subprocess.run(cmd, capture_output=True, text=True, '
            'encoding="utf-8")')
    multiline = 'subprocess.run(\n    cmd,\n    text=True,\n)'
    assert reference_unpinned_text_spawns(bad, "x.py") == ["x.py:1"]
    assert reference_unpinned_text_spawns(multiline, "x.py") == ["x.py:1"]
    assert reference_unpinned_text_spawns(good, "x.py") == []
    assert reference_unpinned_text_spawns(
        'subprocess.run(cmd, capture_output=True)', "x.py") == []
