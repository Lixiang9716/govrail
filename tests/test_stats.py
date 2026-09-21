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

    def test_crlf_lines_do_not_drift(self, tmp_path):
        """Windows text-mode writes emit CRLF; a line offset that assumes
        one terminator byte drifts every later line into the previous
        comment spans and misclassifies code as comment — the first
        Windows CI run caught exactly this."""
        body = (
            "package main\n"
            "\n"
            "// a full-line comment sits before the code lines\n"
            "func main() {\n"
            "\tif x > 0 { // trailing comment\n"
            "\t\tprintln(1)\n"
            "\t}\n"
            "}\n"
        )
        (tmp_path / "crlf.go").write_bytes(body.replace("\n", "\r\n")
                                           .encode("utf-8"))
        pack = parse.load_pack("go")
        agg = stats.compute(tmp_path, [pack])
        lines = _lang(agg, "go")["lines"]
        assert lines["total"] == 8
        assert lines["comment"] == 1  # only the full-line comment
        assert lines["blank"] == 1
        assert lines["code"] == 6  # the trailing-comment line is code

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


# --- #265: `gov parse` — the parse layer as a first-class primitive ----

def _write_module(tmp_path: Path) -> Path:
    f = tmp_path / "mod.py"
    f.write_text(
        "import subprocess\n"
        "\n"
        "def outer():\n"
        "    def inner():\n"
        "        pass\n"
        "    return inner\n"
        "\n"
        "class Thing:\n"
        "    def method(self):\n"
        "        if True:\n"
        "            return 1\n",
        encoding="utf-8")
    return f


def test_parse_reports_function_spans_and_depth(tmp_path, monkeypatch,
                                                capsys):
    """Known answers by construction: outer spans lines 3-6 at depth 0
    with inner nested; method sits at depth 1 inside the class; the
    counts are per file."""
    from gov import stats
    f = _write_module(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert stats.parse_main([str(f), "--json"]) == 0
    import json as _json
    payload = _json.loads(capsys.readouterr().out)
    assert payload["skipped"] == []
    reports = payload["files"]
    assert len(reports) == 1
    r = reports[0]
    assert r["path"] == "mod.py" and r["language"] == "python"
    assert r["lines"]["total"] == 11
    by_name = {fn["name"]: fn for fn in r["functions"]}
    assert by_name["outer"] == {"name": "outer", "start": 3, "end": 6,
                                "depth": 0}
    # depth counts NESTING-NODE levels inside the function body — a
    # nested def is not a nesting node (pack.nesting); inner's body is
    # just `pass`, method's body holds one if, hence 1.
    assert by_name["inner"]["depth"] == 0
    assert by_name["method"]["depth"] == 1
    assert r["max_depth"] == 1
    assert r["parse_errors"] == 0


def test_parse_skips_unsupported_files_named(tmp_path, monkeypatch,
                                             capsys):
    f = tmp_path / "readme.txt"
    f.write_text("not code\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert stats.parse_main([str(f)]) == 0
    out = capsys.readouterr().out  # the skipped note rides the human report
    assert "no shipped grammar matches" in out


def test_parse_walks_directories_and_names_the_uncovered(tmp_path,
                                                         monkeypatch,
                                                         capsys):
    """#270: the dir walk reports its honest complement — the .txt file
    no grammar claims lands in `skipped` with a per-file reason, in the
    same JSON object as the facts."""
    from gov import stats
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "a.py").write_text("def a():\n    pass\n",
                                  encoding="utf-8")
    (src_dir / "notes.txt").write_text("planned hosts\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert stats.parse_main([str(src_dir), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [f["path"] for f in payload["files"]] == ["src/a.py"]
    assert payload["skipped"] == [
        {"path": "src/notes.txt", "reason": "no grammar for .txt"}]
    assert stats.parse_main([str(src_dir)]) == 0
    out = capsys.readouterr().out
    assert "1 file(s) not parsed" in out and ".txt" in out


def test_parse_missing_path_is_named(tmp_path, monkeypatch, capsys):
    """U-6: an explicit path that does not exist is a caller error
    (named exit 2) — rc 0 with empty facts is reserved for real
    zero-match scopes."""
    monkeypatch.chdir(tmp_path)
    assert stats.parse_main([str(tmp_path / "nope.py")]) == 2
    captured = capsys.readouterr()
    assert "no such file or directory" in captured.err
    assert "gov parse: skipped" not in captured.out


class TestSwiftKnownAnswer:
    """#335: Swift ships a grammar now — the numbers must mean what they
    claim, counted by hand from the source (if→for→while = 3)."""

    def _write(self, tmp_path):
        (tmp_path / "Counter.swift").write_text(
            "import Foundation\n"
            "\n"
            "struct Counter {\n"
            "    var n: Int = 0\n"
            "    func bump(by step: Int) -> Int {\n"
            "        if n > 0 {\n"                    # 1
            "            for i in 0..<step {\n"       # 2
            "                while n > 1 {\n"         # 3
            "                    n -= 1\n"
            "                }\n"
            "            }\n"
            "        }\n"
            "        switch n {\n"
            "        case 0: return 0\n"
            "        default: return n\n"
            "        }\n"
            "        return n\n"
            "    }\n"
            "}\n"
            "\n"
            "func free(x: Int) -> Int {\n"
            "    if x > 0 {\n"                        # 1
            "        return x\n"
            "    }\n"
            "    return -x\n"
            "}\n",
            encoding="utf-8")
        return tmp_path

    def test_swift_depths_match_a_human_count(self, tmp_path):
        self._write(tmp_path)
        pack = parse.load_pack("swift")
        agg = stats.compute(tmp_path, [pack])
        depth = _lang(agg, "swift")["depth"]
        by_name = {o["name"]: o["depth"] for o in depth["outliers"]}
        assert by_name["bump"] == 3, "if→for→while, switch is not nested"
        assert by_name["free"] == 1, "a lone if"
        assert depth["max"] == 3

    def test_swift_function_spans_and_lines(self, tmp_path):
        self._write(tmp_path)
        # the load is the pack-validation proof; parse_report walks packs
        parse.load_pack("swift")
        reports, skipped = stats.parse_report([tmp_path / "Counter.swift"])
        assert not skipped, skipped
        entry = reports[0]
        assert entry["language"] == "swift"
        assert entry["lines"]["total"] == 26
        spans = {f["name"]: (f["start"], f["end"]) for f in entry["functions"]}
        assert spans["bump"] == (5, 18)
        assert spans["free"] == (21, 26), "signature line through its closing brace"
        assert entry["parse_errors"] == 0


class TestKotlinKnownAnswer:
    def _write(self, tmp_path):
        (tmp_path / "Counter.kt").write_text(
            "package demo\n"
            "\n"
            "class Counter(val start: Int) {\n"
            "    fun bump(step: Int): Int {\n"
            "        if (start > 0) {\n"             # 1
            "            for (i in 0..step) {\n"      # 2
            "                while (start > i) {\n"   # 3
            "                    log(i)\n"
            "                }\n"
            "            }\n"
            "        }\n"
            "        when (start) {\n"
            "            0 -> return 0\n"
            "            else -> return start\n"
            "        }\n"
            "        return start\n"
            "    }\n"
            "}\n",
            encoding="utf-8")
        return tmp_path

    def test_kotlin_depths_match_a_human_count(self, tmp_path):
        self._write(tmp_path)
        pack = parse.load_pack("kotlin")
        agg = stats.compute(tmp_path, [pack])
        depth = _lang(agg, "kotlin")["depth"]
        by_name = {o["name"]: o["depth"] for o in depth["outliers"]}
        assert by_name["bump"] == 3, "if→for→while; when is a sibling level"
        assert depth["max"] == 3

    def test_kotlin_function_spans(self, tmp_path):
        self._write(tmp_path)
        parse.load_pack("kotlin")
        reports, skipped = stats.parse_report([tmp_path / "Counter.kt"])
        assert not skipped, skipped
        entry = reports[0]
        assert entry["language"] == "kotlin"
        spans = {f["name"]: (f["start"], f["end"])
                 for f in entry["functions"]}
        assert spans["bump"] == (4, 17)
        assert entry["parse_errors"] == 0


# Packs that describe a language with line facts ONLY: the grammar ships
# no comment or string node at all, so the pack is globs + exclusions and
# `gov stats` reports its files' line counts alone. Named, with the reason,
# rather than silently exempted (rule 5).
LINE_FACTS_ONLY = {"markdown": "the grammar has no comment/string nodes"}


class TestPackIntegrity:
    def test_every_installed_pack_loads_and_declares_its_axes(self):
        """A pack is DATA validated at load; this walks every installed
        one so a shipped pack cannot rot between releases (a wrong node
        kind refuses to load — the check that catches it runs here).

        Markup and data formats carry the axes their language has (a
        stylesheet has nesting and strings but no functions); a pack
        whose axes are ALL empty must be named in LINE_FACTS_ONLY.
        """
        names = parse.available()
        assert names, "no packs installed"
        for name in names:
            pack = parse.load_pack(name)          # validates kinds (rule 5)
            assert pack.globs, name
            assert pack.exclude, name
            axes = (pack.functions, pack.nesting, pack.comment,
                    pack.string, pack.classes)
            if name in LINE_FACTS_ONLY:
                assert not any(axes), (
                    f"{name} is declared line-facts-only but carries axes: "
                    "update the declaration")
            else:
                assert any(axes), (
                    f"{name} declares no axis at all — give it the kinds "
                    "its grammar has, or add it to LINE_FACTS_ONLY with a "
                    "reason")

    def test_parse_covers_a_pack_without_check_rules(self, tmp_path):
        """#335's decoupling: `gov parse` walks every installed PACK
        (`gov stats`' set), not the rules-bearing set the check gate
        judges — Swift and Kotlin ship grammar-first, rules only when
        they can be honest."""
        from gov import checks
        (tmp_path / "x.swift").write_text(
            "func f() { return }\n", encoding="utf-8")
        reports, skipped = stats.parse_report([tmp_path / "x.swift"])
        assert not skipped, skipped
        assert reports[0]["language"] == "swift"
        assert "swift" in parse.available()
        # the two sets are deliberately different axes
        assert "swift" not in checks.available_langs()


# One tiny, VALID snippet per shipped language plus the minimum number of
# function spans it must yield. The point is not the snippet's depth but
# the axis: a pack whose `functions` list names a node ordinary code never
# produces reads as "0 functions" forever — a silently useless pack, the
# exact failure the load-time kind check cannot catch (the kind exists; it
# is just the wrong one). Markup and data packs declare 0 and prove the
# grammar parses them at all.
SNIPPETS: dict[str, tuple[str, str, int]] = {
    "ada": ("hello.adb", "procedure Hello is\nbegin\n   null;\nend Hello;\n", 1),
    "bash": ("greet.sh", "greet() {\n  echo hi\n}\n", 1),
    "c": ("m.c", "int f(void) { if (1) { return 1; } return 0; }\n", 1),
    "c-sharp": ("C.cs", "class C {\n  void M() { if (true) { } }\n}\n", 1),
    "cpp": ("m.cpp", "int f() { if (true) { return 1; } return 0; }\n", 1),
    "css": ("a.css", ".a { color: red; }\n", 0),
    "cuda": ("k.cu", "void k() { if (true) { } }\n", 1),
    "dart": ("m.dart", "void main() { if (true) { } }\n", 1),
    "elixir": ("m.ex", "defmodule M do\n  def go do\n    :ok\n  end\nend\n", 1),
    "embedded-template": ("v.erb", "<% if x %>hi<% end %>\n", 0),
    "fortran": ("m.f90", "subroutine go()\nend subroutine go\n", 1),
    "go": ("m.go", "package m\n\nfunc F() int {\n\tif true {\n\t\treturn 1\n\t}\n\treturn 0\n}\n", 1),
    "groovy": ("G.groovy", "class G {\n  def m() { if (true) { } }\n}\n", 1),
    "haskell": ("M.hs", "f :: Int -> Int\nf x = if x > 0 then x else 0\n", 1),
    "html": ("i.html", "<p>hi</p>\n", 0),
    "java": ("M.java", "class M {\n  int f() { if (true) { return 1; } return 0; }\n}\n", 1),
    "javascript": ("m.js", "function f() { if (true) { return 1; } return 0; }\n", 1),
    "json": ("d.json", '{"a": [1, 2]}\n', 0),
    "julia": ("m.jl", "function go(x)\n  if x > 0\n    return x\n  end\nend\n", 1),
    "kotlin": ("M.kt", "fun go(x: Int): Int {\n    if (x > 0) {\n        return x\n    }\n    return 0\n}\n", 1),
    "lua": ("m.lua", "function go(x)\n  if x then return x end\nend\n", 1),
    "make": ("Makefile", "all:\n\techo hi\n", 0),
    "markdown": ("d.md", "# Title\n\ntext\n", 0),
    "nix": ("m.nix", "let f = x: x; in f 1\n", 1),
    "objc": ("m.m", "@implementation C\n- (void)m { if (1) { } }\n@end\n", 1),
    "ocaml": ("m.ml", "let go x = if x > 0 then x else 0\n", 1),
    "php": ("m.php", "<?php\nfunction go($x) { if ($x) { return 1; } return 0; }\n", 1),
    "powershell": ("m.ps1", "function Get-Thing { if ($true) { return 1 } }\n", 1),
    "python": ("m.py", "def go(x):\n    if x > 0:\n        return x\n    return 0\n", 1),
    "ruby": ("m.rb", "def go(x)\n  if x > 0\n    x\n  end\nend\n", 1),
    "rust": ("m.rs", "fn go(x: i32) -> i32 {\n    if x > 0 {\n        return x;\n    }\n    0\n}\n", 1),
    "scala": ("M.scala", "object M { def go(x: Int): Int = if (x > 0) x else 0 }\n", 1),
    "sql": ("q.sql", "SELECT * FROM t WHERE a IN (SELECT b FROM u);\n", 0),
    "svelte": ("C.svelte", "<script>let a = 1;</script>\n{#if a}<p>x</p>{/if}\n", 0),
    "swift": ("M.swift", "func go(_ x: Int) -> Int {\n    if x > 0 {\n        return x\n    }\n    return 0\n}\n", 1),
    "toml": ("c.toml", "[a]\nb = 1\n", 0),
    "typescript": ("m.ts", "function f(): number { if (true) { return 1; } return 0; }\n", 1),
    "yaml": ("c.yaml", "a:\n  - 1\n  - 2\n", 0),
    "zig": ("m.zig", "fn go(x: i32) i32 { if (x > 0) return x; return 0; }\n", 1),
}


def _count(node, kinds) -> int:
    n = 0
    stack = [node]
    while stack:
        cur = stack.pop()
        if cur.type in kinds:
            n += 1
        stack.extend(cur.children)
    return n


class TestEveryPackParsesItsLanguage:
    def test_the_fixture_table_covers_every_shipped_pack(self):
        """A new pack without a snippet would sail through this class
        silently — the coverage assertion is the test's own teeth."""
        assert set(SNIPPETS) == set(parse.available()), (
            "every shipped pack needs a snippet: "
            f"missing {sorted(set(parse.available()) - set(SNIPPETS))}, "
            f"extra {sorted(set(SNIPPETS) - set(parse.available()))}")

    @pytest.mark.parametrize("lang", sorted(SNIPPETS))
    def test_snippet_parses_and_finds_its_functions(self, lang, tmp_path):
        fname, body, want_funcs = SNIPPETS[lang]
        path = tmp_path / fname
        path.write_text(body, encoding="utf-8")
        pack = parse.load_pack(lang)
        tree = parse.parser_for(pack, path).parse(path.read_bytes())
        assert _count(tree.root_node, {"ERROR"}) == 0, f"{lang}: {body!r}"
        assert not any(n.is_missing for n in _all_nodes(tree.root_node)), lang
        if want_funcs:
            found = _count(tree.root_node, pack.functions)
            assert found >= want_funcs, (
                f"{lang}: the pack's function kinds found nothing in "
                f"ordinary code ({sorted(pack.functions)})")


def _all_nodes(root):
    stack = [root]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(n.children)


class TestUnavailableGrammar:
    """A grammar wheel this interpreter cannot load (the Windows ABI case)
    skips ITS language, loudly and by name — never a dead command, and
    never a silent zero."""

    def _break(self, monkeypatch, lang="ada"):
        from gov import parse as parse_mod
        real = parse_mod.load_pack

        def fake(name):
            if name == lang:
                raise parse_mod.ParseUnavailable(
                    f"language pack {name!r}: grammar boom (OverflowError)")
            return real(name)
        monkeypatch.setattr(parse_mod, "load_pack", fake)
        return parse_mod

    def test_stats_skips_it_by_name_and_keeps_sweeping(self, tmp_path,
                                                       monkeypatch, capsys):
        self._break(monkeypatch)
        monkeypatch.chdir(tmp_path)
        assert stats.main(["--json"]) == 0
        err = capsys.readouterr().err
        assert "SKIP(unavailable grammar: ada)" in err
        assert "OverflowError" in err          # the cause travels with it

    def test_explicit_lang_still_fails_loud(self, tmp_path, monkeypatch,
                                            capsys):
        self._break(monkeypatch)
        monkeypatch.chdir(tmp_path)
        assert stats.main(["--lang", "ada"]) == 2
        assert "language pack 'ada'" in capsys.readouterr().err

    def test_parse_report_names_it_instead_of_no_match(self, tmp_path,
                                                       monkeypatch):
        self._break(monkeypatch)
        (tmp_path / "x.adb").write_text("procedure P is\nbegin\nnull;\nend P;\n",
                                        encoding="utf-8")
        reports, skipped = stats.parse_report([tmp_path / "x.adb"])
        assert not reports
        assert skipped and "language pack 'ada'" in skipped[0]["reason"], skipped


class TestFactoryShape:
    def test_every_pack_factory_returns_a_capsule_not_a_pointer(self):
        """The Windows-ABI class, caught locally instead of in CI.

        A grammar whose factory returns a raw POINTER int works on Linux
        and macOS and dies on Windows: the binding casts the int to
        ``c_ulong``, which is 32-bit there, so a 64-bit pointer overflows
        (``OverflowError: Python int too large to convert to C unsigned
        long``). Every shipped grammar returns a PyCapsule; tlaplus
        returned an int and was dropped from the set rather than shipped
        broken on one platform — the same check that found it runs here.
        """
        import importlib
        for name in parse.available():
            raw = json.loads((Path("gov/langs") / f"{name}.json")
                             .read_text(encoding="utf-8"))
            mod = importlib.import_module(raw["grammar"])
            factory = raw.get("factory") or "language"
            fn = getattr(mod, factory, None) or getattr(mod, "language_typescript")
            assert type(fn()).__name__ == "PyCapsule", (
                f"{name}: {raw['grammar']}.{factory}() returns "
                f"{type(fn()).__name__}, not a PyCapsule — that shape "
                "overflows on Windows (see the docstring)")
