"""gov stats — the parse layer and its metrics (D56).

The metrics here are FACTS, not verdicts, so the rule-6 shape is adapted:
what must be proven is that the NUMBERS mean what they claim. The
known-answer fixtures are hand-countable by design — the Go fixture's
depths were computed by a human reading the file (for→switch→if→for→if =
5; a lone if = 1) — because the worst failure mode of a metrics tool is a
plausible number that means nothing. The prototype's first depth walk
recorded the function's ENTRY depth instead of its subtree maximum and
reported a flat, believable 0 — the fixtures exist so that class of bug
cannot ship.
"""
import json
from pathlib import Path

import pytest

from gov import parse, stats


@pytest.fixture()
def go_project(tmp_path):
    """The hand-countable fixture. Depths are asserted against values a
    human counted from the source, not against the implementation."""
    (tmp_path / "svc.go").write_text(
        "package svc\n"
        "\n"
        'import "fmt"\n'
        "\n"
        "func Route(mode string, depth int) error {\n"
        "\tfor i := 0; i < depth; i++ {\n"          # 1
        "\t\tswitch mode {\n"                        # 2
        '\t\tcase "a":\n'                            # (case is not a level)
        "\t\t\tif i%2 == 0 {\n"                      # 3
        "\t\t\t\tfor j := 0; j < 3; j++ {\n"         # 4
        "\t\t\t\t\tif j == 2 {\n"                    # 5
        '\t\t\t\t\t\tfmt.Println("deep")\n'
        "\t\t\t\t\t}\n"
        "\t\t\t\t}\n"
        "\t\t\t}\n"
        '\t\tcase "b":\n'
        '\t\t\tfmt.Println("shallow")\n'
        "\t\t}\n"
        "\t}\n"
        "\treturn nil\n"
        "}\n"
        "\n"
        "func Handle(x int) int {\n"
        "\tif x > 0 { // trailing comment, still a code line\n"  # 1
        "\t\treturn x\n"
        "\t}\n"
        "\treturn -x\n"
        "}\n",
        encoding="utf-8",
    )
    return tmp_path


def _lang(agg, name):
    return agg[name]


class TestKnownAnswer:
    def test_go_depths_match_a_human_count(self, go_project):
        pack = parse.load_pack("go")
        agg = stats.compute(go_project, [pack])
        depth = _lang(agg, "go")["depth"]
        by_name = {o["name"]: o["depth"] for o in depth["outliers"]}
        assert by_name["Route"] == 5, "for→switch→if→for→if, case is not a level"
        assert by_name["Handle"] == 1, "a lone if"
        assert depth["max"] == 5

    def test_go_trailing_comment_line_is_code(self, go_project):
        pack = parse.load_pack("go")
        agg = stats.compute(go_project, [pack])
        lines = _lang(agg, "go")["lines"]
        # 28 lines: 3 blank, 0 full-line comments, and the trailing-comment
        # line is CODE (it carries a non-comment token).
        assert lines["total"] == 28
        assert lines["blank"] == 3
        assert lines["comment"] == 0
        assert lines["code"] == 25

    def test_python_docstrings_are_code_not_comment(self, tmp_path):
        """The counting rule the output echoes: a multi-line string is CODE.
        A docstring-only file therefore has code > 0 and comment == 0."""
        (tmp_path / "mod.py").write_text(
            '"""Module docstring.\n\nThree lines of prose in a string.\n"""\n'
            "\n"
            "def f():\n"
            '    """Function docstring."""\n'
            "    return 1\n",
            encoding="utf-8",
        )
        pack = parse.load_pack("python")
        agg = stats.compute(tmp_path, [pack])
        lines = _lang(agg, "python")["lines"]
        assert lines["comment"] == 0
        assert lines["code"] == 6  # total 8, minus the two blank lines
        assert lines["blank"] == 2

    def test_python_nesting_and_public_symbols(self, tmp_path):
        (tmp_path / "m.py").write_text(
            "class Thing:\n"
            "    def run(self):\n"
            "        for _ in range(3):\n"       # 1
            "            if _:\n"                # 2
            "                with open('x'):\n"  # 3
            "                    pass\n"
            "\n"
            "    def _helper(self):\n"
            "        return 0\n",
            encoding="utf-8",
        )
        pack = parse.load_pack("python")
        agg = stats.compute(tmp_path, [pack])
        a = _lang(agg, "python")
        assert a["symbols"]["functions"] == 2
        assert a["symbols"]["classes"] == 1
        assert a["symbols"]["public"] == 2  # Thing, run — _helper is private
        by_name = {o["name"]: o["depth"] for o in a["depth"]["outliers"]}
        assert by_name["run"] == 3
        assert by_name["_helper"] == 0


class TestFailLoud:
    def test_bad_node_kind_refuses_to_load(self):
        """A typo'd node kind would silently zero its metric — the pack
        must refuse to load, naming the kind (rule 5)."""
        good = parse.load_pack("python")
        raw = {
            "globs": ["*.py"],
            "exclude": [],
            "grammar": good.grammar,
            "nesting": ["if_statment"],  # typo, caught by CI for years in C
            "functions": sorted(good.functions),
            "classes": sorted(good.classes),
            "comment": sorted(good.comment),
            "string": sorted(good.string),
        }
        import gov.langs as langs_pkg
        from importlib.resources import files
        target = files("gov").joinpath("langs/_bad.json")
        import json as _json
        target.write_text(_json.dumps(raw), encoding="utf-8")
        try:
            with pytest.raises(parse.ParseUnavailable) as e:
                parse.load_pack("_bad")
            assert "if_statment" in str(e.value)
            assert "rule 5" in str(e.value)
        finally:
            Path(str(target)).unlink(missing_ok=True)

    def test_parse_errors_are_counted_and_named(self, tmp_path):
        """tree-sitter never raises; an ERROR node is the only signal.
        stats must surface it (counted, file named in --json), never
        silently treat a broken file as checked."""
        (tmp_path / "ok.py").write_text("def f():\n    return 1\n",
                                        encoding="utf-8")
        (tmp_path / "broken.py").write_text(
            "def f(:\n    ??? return\n", encoding="utf-8")
        pack = parse.load_pack("python")
        agg = stats.compute(tmp_path, [pack])
        a = _lang(agg, "python")
        assert a["parse_errors"] > 0, "a broken file must not read as clean"
        assert a["files"] == 2
        detail = {f["path"]: f for f in a["files_detail"]}
        assert detail["broken.py"]["errors"] > 0
        assert detail["ok.py"]["errors"] == 0


class TestSurface:
    def test_main_json_is_one_value(self, go_project, capsys,
                                    monkeypatch):
        monkeypatch.chdir(go_project)
        assert stats.main(["--json", "--lang", "go"]) == 0
        out = capsys.readouterr().out
        value = json.loads(out)  # exactly one JSON value, no trailing prose
        assert value["v"] == stats.STATS_VERSION
        assert "go" in value["languages"]

    def test_main_record_appends_ledger(self, go_project, capsys,
                                        monkeypatch):
        monkeypatch.chdir(go_project)
        assert stats.main(["--record", "--lang", "go"]) == 0
        ledger = go_project / ".gov" / "history" / "stats.jsonl"
        lines = ledger.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["languages"]["go"]["files"] == 1
        assert record["languages"]["go"]["depth"]["max"] == 5

    def test_unknown_lang_fails_loud(self, capsys):
        assert stats.main(["--lang", "no-such-lang"]) == 2
        assert "no language pack named" in capsys.readouterr().err
