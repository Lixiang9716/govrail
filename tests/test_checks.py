"""gov check — the check engine (D57).

Verdicts live here, so rule 6 applies at full strength: every mechanism
is pinned by a known-answer fixture — the shipped syntax rule must go
RED on a broken file and name file:line; the query difference must find
the candidate WITHOUT the absent thing and discharge the one that has
it; a suppression must discharge exactly its rule on exactly its line
and be COUNTED; severity must gate the exit code. The project-rule
surface is additive by contract, and a duplicate id is refused, not
silently overridden (rule 5).
"""
import json

import pytest

from gov import checks


@pytest.fixture()
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _write_rules(tmp_path, lang, rules):
    d = tmp_path / ".gov" / "checks"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{lang}.json").write_text(
        json.dumps({"rules": rules}), encoding="utf-8")


QUERY_RULE = {
    "id": "test/bare-eval",
    "kind": "query",
    "severity": "warning",
    "message": "bare eval() call",
    # A bare-name call. The capture designates the FINDING node — the
    # absent query and the suppression window are evaluated against IT,
    # so the rule captures the CALL, not just the callee identifier.
    "query": "((call function: (identifier)) @gov-node)",
    # ...WITHOUT any argument inside it (the difference half); (_ ) is
    # the wildcard — an argument may be a string, a call, anything.
    "absent_query": "(argument_list (_))",
}


class TestShippedSyntaxRule:
    def test_broken_file_is_red_and_named(self, project):
        (project / "broken.go").write_text("func {\n", encoding="utf-8")
        (project / "fine.go").write_text("package main\n", encoding="utf-8")
        rules = checks.load_rules("go")
        reports = checks.run_lang(project, "go", rules)
        findings = [f for r in reports for f in r.findings
                    if not f.suppressed]
        assert findings, "a broken file must go red"
        by_path = {}
        for f in findings:
            by_path.setdefault(f.path, []).append(f)
        assert "broken.go" in by_path
        assert "fine.go" not in by_path, "the clean file must stay clean"
        assert all(f.severity == "error" for f in findings)
        assert all(f.line() >= 1 for f in findings)

    def test_exit_code_and_json_shape(self, project, capsys):
        (project / "broken.go").write_text("func {", encoding="utf-8")
        assert checks.main(["--lang", "go", "--json"]) == 1
        value = json.loads(capsys.readouterr().out)
        assert value["summary"]["blocking"] >= 1
        assert value["languages"] == ["go"]

    def test_json_report_lands_on_stderr_not_stdout(self, project, capsys):
        # --json's help promises "the human report moves to stderr";
        # stdout must stay exactly one JSON value for machine callers.
        (project / "broken.go").write_text("func {", encoding="utf-8")
        assert checks.main(["--lang", "go", "--json"]) == 1
        cap = capsys.readouterr()
        json.loads(cap.out)  # stdout stays exactly one JSON value
        assert "gov check:" not in cap.out
        assert "broken.go" in cap.err and "gov check:" in cap.err

    def test_clean_tree_prints_clean_and_exits_zero(self, project, capsys):
        (project / "fine.go").write_text("package main\n", encoding="utf-8")
        assert checks.main(["--lang", "go"]) == 0
        assert "gov check: clean" in capsys.readouterr().out


class TestQueryDifference:
    """Negation as two queries: presence minus an inner match."""

    def _project(self, project):
        _write_rules(project, "python", [QUERY_RULE])
        (project / "code.py").write_text(
            "eval('a')\n"        # bare-name call, args present -> discharged
            "eval()\n"           # bare-name call, NO args -> FINDING
            "print(eval())\n"    # nested: still a bare eval() -> FINDING
            "x = 1\n",
            encoding="utf-8",
        )
        return project

    def test_difference_finds_only_the_without_shape(self, project):
        self._project(project)
        rules = checks.load_rules("python")
        reports = checks.run_lang(project, "python", rules)
        rows = [f.line() for r in reports for f in r.findings
                if f.rule_id == "test/bare-eval" and not f.suppressed]
        assert rows == [2, 3], "only the argument-less eval() calls"

    def test_query_without_absent_finds_presence_only(self, project):
        _write_rules(project, "python", [{
            "id": "test/any-bare-call",
            "kind": "query", "severity": "warning",
            "message": "bare call",
            "query": "((call function: (identifier)) @gov-node)",
        }])
        (project / "code.py").write_text("a()\nb(1)\n", encoding="utf-8")
        reports = checks.run_lang(project, "python",
                                  checks.load_rules("python"))
        rows = [f.line() for r in reports for f in r.findings]
        assert rows == [1, 2]


class TestSuppression:
    def test_marker_discharges_its_line_and_is_counted(self, project, capsys):
        _write_rules(project, "python", [QUERY_RULE])
        (project / "code.py").write_text(
            "eval()  # gov:ignore-check test/bare-eval\n"
            "eval()\n",
            encoding="utf-8",
        )
        assert checks.main(["--lang", "python", "--json",
                            "--record"]) == 0
        value = json.loads(capsys.readouterr().out)
        assert value["summary"]["findings"] == 1, "only the unmarked line"
        assert value["summary"]["suppressed"] == 1
        # The ledger records BOTH: a growing exemption must be visible.
        ledger = project / ".gov" / "history" / "stats.jsonl"
        record = json.loads(ledger.read_text(encoding="utf-8")
                            .strip().splitlines()[-1])
        assert record["kind"] == "check"
        assert record["checks"]["test/bare-eval"] == {
            "findings": 1, "suppressed": 1}

    def test_a_marker_for_another_rule_does_not_discharge(self, project):
        _write_rules(project, "python", [QUERY_RULE])
        (project / "code.py").write_text(
            "eval()  # gov:ignore-check some/other-rule\n",
            encoding="utf-8",
        )
        reports = checks.run_lang(project, "python",
                                  checks.load_rules("python"))
        active = [f for r in reports for f in r.findings if not f.suppressed]
        assert len(active) == 1

    def test_marker_inside_a_multiline_node_span_discharges(self, project):
        # No absent_query: every bare-name call is a finding, so the
        # multiline call is one too — and the marker on its INNER line
        # must discharge it via the node's row span. (A comment is an
        # extra node in the tree: with QUERY_RULE's wildcard-absence a
        # comment-only argument list discharges the call outright, which
        # is the difference mechanism working, not suppression.)
        _write_rules(project, "python", [{
            "id": "test/any-bare-call",
            "kind": "query", "severity": "warning",
            "message": "bare call",
            "query": "((call function: (identifier)) @gov-node)",
        }])
        (project / "code.py").write_text(
            "eval(\n"
            "    # gov:ignore-check test/any-bare-call\n"
            "    'x')\n"
            "eval()\n",
            encoding="utf-8",
        )
        reports = checks.run_lang(project, "python",
                                  checks.load_rules("python"))
        active = [f for r in reports for f in r.findings if not f.suppressed]
        suppressed = [f for r in reports for f in r.findings if f.suppressed]
        assert [f.line() for f in active] == [4]
        assert len(suppressed) == 1 and suppressed[0].line() == 1


class TestSeverityAndStrict:
    def test_warning_exits_zero_strict_makes_it_block(self, project):
        _write_rules(project, "python", [QUERY_RULE])
        (project / "code.py").write_text("eval()\n", encoding="utf-8")
        assert checks.main(["--lang", "python"]) == 0
        assert checks.main(["--lang", "python", "--strict"]) == 1


class TestRuleFive:
    def test_duplicate_project_id_is_refused(self, project):
        _write_rules(project, "python", [{
            "id": "python/syntax", "kind": "parse-errors",
            "severity": "error", "message": "override attempt",
        }])
        with pytest.raises(checks.CheckError) as e:
            checks.load_rules("python")
        assert "duplicates a shipped rule" in str(e.value)
        assert "rule 5" in str(e.value)

    def test_unknown_rule_key_is_refused(self, project):
        _write_rules(project, "python", [{
            "id": "x/y", "kind": "parse-errors", "severity": "error",
            "message": "m", "queryz": "nope",
        }])
        with pytest.raises(checks.CheckError) as e:
            checks.load_rules("python")
        assert "unknown key" in str(e.value)

    def test_unknown_node_kind_is_refused_not_silent(self, project, capsys):
        """The query compiler ACCEPTS unknown node kinds (they match
        nothing silently) — the engine must refuse them itself, named
        (D54's wrong-kind lesson at the rule layer)."""
        _write_rules(project, "python", [{
            "id": "x/ghost", "kind": "query", "severity": "error",
            "message": "m", "query": "(call function: (nope))",
        }])
        assert checks.main(["--lang", "python"]) == 2
        err = capsys.readouterr().err
        # Loud either way: this binding's Query compiler rejects unknown
        # kinds itself; the engine's own kind table check is the backstop.
        assert "x/ghost" in err
        assert ("does not compile" in err or "'nope'" in err)

    def test_noncompiling_query_fails_loud_exit_2(self, project, capsys):
        _write_rules(project, "python", [{
            "id": "x/broken", "kind": "query", "severity": "error",
            "message": "m", "query": "(call function:",
        }])
        assert checks.main(["--lang", "python"]) == 2
        assert "does not compile" in capsys.readouterr().err
