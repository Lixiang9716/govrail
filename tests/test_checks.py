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
from gov import plane
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


# --- the change scope (D55's revision): the gate judges what changed ---

def _git_repo(tmp_path, legacy_violation: bool = True):
    import subprocess as sp
    sp.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)
    sp.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    sp.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    if legacy_violation:
        src = tmp_path / "src"
        src.mkdir()
        (src / "legacy.py").write_text(
            "import subprocess\n"
            'subprocess.run(["ls"], capture_output=True, text=True)\n',
            encoding="utf-8")
    sp.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    sp.run(["git", "-c", "commit.gpgsign=false", "commit", "-qm", "legacy"],
           cwd=tmp_path, check=True)


def test_auto_base_judges_the_change_never_history(tmp_path, monkeypatch,
                                                   capsys):
    """The advisory-first fix, at the CLI level: legacy code committed
    before adoption is NOT judged by the change-scoped default, a
    violating new file IS, and the scope is announced (a vacuous green
    says '0 changed file(s) in scope' out loud)."""
    _git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "clean.py").write_text("value = 1\n", encoding="utf-8")

    assert checks.main([]) == 0  # dirty tree -> HEAD: legacy out of scope
    out = capsys.readouterr().out  # the human report lives on stdout
    assert "base=HEAD" in out and "changed file(s) in scope" in out

    (tmp_path / "newcode.py").write_text(
        "import subprocess\n"
        'subprocess.run(["git", "status"], capture_output=True, text=True)\n',
        encoding="utf-8")
    assert checks.main([]) == 1  # the violation is in scope
    assert "newcode.py" in capsys.readouterr().out


def test_all_sweeps_the_whole_tree(tmp_path, monkeypatch):
    """--all is where legacy code is judged: the sweep reaches history
    the change-scoped default deliberately leaves alone."""
    _git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "clean.py").write_text("value = 1\n", encoding="utf-8")
    assert checks.main(["--all"]) == 1


def test_explicit_base_overrides_the_cascade(tmp_path, monkeypatch,
                                             capsys):
    _git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    # --base HEAD on a clean tree: nothing changed since HEAD
    assert checks.main(["--base", "HEAD"]) == 0
    assert "base=HEAD" in capsys.readouterr().out


def test_all_and_base_are_a_pick_one(tmp_path, monkeypatch, capsys):
    """--all and --base judge different scopes; accepting both silently
    would make the scope depend on flag order (rule 5)."""
    _git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert checks.main(["--all", "--base", "HEAD"]) == 2
    assert "pick one" in capsys.readouterr().err


def test_first_run_after_adoption_stays_green(tmp_path, monkeypatch):
    """The blocker, end to end: a repository whose product code carried
    a #172-class violation before `gov init` must pass its FIRST full
    DAG run (P0-3), and the same violation edited NOW must go red."""
    from gov import cli
    _git_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert plane.init(tmp_path) == 0
    assert cli.main(["run"]) == 0, "advisory-first broken"

    legacy = tmp_path / "src" / "legacy.py"
    legacy.write_text(
        "import subprocess\n"
        'subprocess.run(["git", "status"], capture_output=True, text=True)\n',
        encoding="utf-8")
    assert cli.main(["run"]) == 1, "an in-scope violation must be judged"


class TestPathExclusions:
    """#348: a project-declared path exclusion keeps verbatim vendored
    trees out of the judged set — counted, never invisible."""

    def _exclude(self, project, payload):
        d = project / ".gov" / "checks"
        d.mkdir(parents=True, exist_ok=True)
        (d / "exclude.json").write_text(json.dumps(payload),
                                        encoding="utf-8")

    def test_excluded_file_is_not_judged_but_is_counted(self, project,
                                                        capsys):
        (project / "vendor").mkdir()
        (project / "vendor" / "broken.js").write_text(
            "export { _instanceof as instanceof };\n", encoding="utf-8")
        self._exclude(project, {"exclude": [
            {"path": "vendor/**",
             "reason": "vendored upstream pin, verbatim by project rule"}]})
        assert checks.main(["--lang", "javascript"]) == 0
        out = capsys.readouterr().out
        # the skip is loud: pattern, count, reason — never a silent green
        assert "SKIP(excluded: vendor/** — 1 file(s) — vendored upstream " \
               "pin, verbatim by project rule)" in out
        assert "vendor/broken.js" not in out  # not judged, so not quoted

    def test_json_carries_the_exclusion_ledger(self, project, capsys):
        (project / "vendor").mkdir()
        (project / "vendor" / "x.js").write_text("var a;\n",
                                                 encoding="utf-8")
        self._exclude(project, {"exclude": [
            {"path": "vendor/**", "reason": "vendored"}]})
        assert checks.main(["--lang", "javascript", "--json"]) == 0
        value = json.loads(capsys.readouterr().out)
        assert value["excluded"] == [{"pattern": "vendor/**",
                                      "reason": "vendored", "files": 1}]

    def test_declared_but_zero_matching_pattern_still_surfaces(self, project,
                                                               capsys):
        (project / "fine.js").write_text("var a;\n", encoding="utf-8")
        self._exclude(project, {"exclude": [
            {"path": "nope/**", "reason": "stale pattern nags"}]})
        assert checks.main(["--lang", "javascript"]) == 0
        assert "SKIP(excluded: nope/** — 0 file(s) — stale pattern nags)" \
            in capsys.readouterr().out

    def test_basename_glob_matches_any_directory(self, project):
        (project / "a").mkdir()
        (project / "b").mkdir()
        (project / "a" / "zod.js").write_text("var a;\n", encoding="utf-8")
        (project / "b" / "zod.js").write_text("var a;\n", encoding="utf-8")
        self._exclude(project, {"exclude": [
            {"path": "zod.js", "reason": "basename glob, pack convention"}]})
        skips: dict = {}
        checks.run_lang(project, "javascript", checks.load_rules(
            "javascript", include_project=False), excludes=checks.load_excludes(),
            skips=skips)
        assert skips["zod.js"]["count"] == 2

    def test_malformed_config_aborts_named(self, project, capsys, caplog):
        (project / "fine.js").write_text("var a;\n", encoding="utf-8")
        self._exclude(project, {"exclude": [{"path": ""}]})
        assert checks.main(["--lang", "javascript"]) == 2
        assert "exclude[0]" in capsys.readouterr().err

    def test_duplicate_pattern_refused(self, project):
        self._exclude(project, {"exclude": [
            {"path": "v/**", "reason": "one"},
            {"path": "v/**", "reason": "two"}]})
        with pytest.raises(checks.CheckError, match="duplicate pattern"):
            checks.load_excludes()


class TestMachineSurfaceTruth:
    """#349: the JSON surface describes the same run the human report
    does — the verdict the exit code carries is stated in the payload,
    and the judged scope is enumerable, not just counted."""

    def test_json_ok_field_matches_the_exit_code(self, project, capsys):
        (project / "broken.go").write_text("func {", encoding="utf-8")
        assert checks.main(["--lang", "go", "--json"]) == 1
        assert json.loads(capsys.readouterr().out)["ok"] is False
        capsys.readouterr()
        (project / "fine.go").write_text("package main\n", encoding="utf-8")
        (project / "broken.go").unlink()
        assert checks.main(["--lang", "go", "--json"]) == 0
        assert json.loads(capsys.readouterr().out)["ok"] is True

    def _git(self, project):
        import subprocess
        for argv in (["git", "init", "-q", "."],
                     ["git", "config", "user.email", "t@t"],
                     ["git", "config", "user.name", "t"]):
            subprocess.run(argv, cwd=project, check=True,
                           capture_output=True)

    def test_scope_files_enumerates_the_judged_set(self, project, capsys):
        # scope_files names the CHANGE scope (auto cascade); a whole-tree
        # --all sweep has no scope to enumerate and stays null.
        self._git(project)
        (project / "fine.go").write_text("package main\n", encoding="utf-8")
        assert checks.main(["--lang", "go", "--json"]) == 0
        value = json.loads(capsys.readouterr().out)
        assert value["scope_files"] == ["fine.go"]
        assert value["scope_files_truncated"] is False

    def test_base_why_carries_the_cascade_reason(self, project, capsys):
        self._git(project)
        (project / "fine.go").write_text("package main\n", encoding="utf-8")
        assert checks.main(["--lang", "go", "--json"]) == 0
        value = json.loads(capsys.readouterr().out)
        assert value["base"] == "HEAD"
        assert value["base_why"] == "dirty worktree — reviewing the working tree"

    def test_text_and_json_describe_the_same_run(self, project, capsys):
        """#349's contract: one process, one set of findings — the two
        surfaces can never contradict. The text finding lines and the
        JSON files array must agree exactly."""
        (project / "broken.go").write_text("func {\n", encoding="utf-8")
        cap = capsys.readouterr()
        assert checks.main(["--lang", "go", "--json"]) == 1
        cap = capsys.readouterr()
        text_report = cap.err
        value = json.loads(cap.out)
        json_files = {f["path"] for f in value["files"] if f["findings"]}
        for path in json_files:
            assert path in text_report
        assert value["summary"]["blocking"] == text_report.count(
            "[go/syntax]") + sum(text_report.count(f"[{r}]") for r in
                                 ("go/syntax",)) or \
            value["summary"]["blocking"] >= 1


def test_help_documents_the_suppression_mechanism(capsys):
    """#333: 'counted, never invisible' named a mechanism the help never
    explained — the marker syntax, its placement, and where the count
    surfaces."""
    import pytest as _pytest
    with _pytest.raises(SystemExit):
        checks.main(["--help"])
    # argparse hard-wraps the epilog: compare against the reflowed text
    flat = " ".join(capsys.readouterr().out.split())
    assert "gov:ignore-check <rule-id>" in flat
    assert "row span" in flat
    assert "counted" in flat and "stats.jsonl" in flat
    assert ".gov/checks/exclude.json" in flat


class TestShippedPythonEncodingRule:
    """#366's push surfaced a FALSE POSITIVE in this shipped rule: the
    plane's own `atomicio.write_text` always encodes UTF-8 (its signature
    takes no `encoding=`), yet every adopter using the helper was nagged.
    Both directions are pinned here — the exemption must not become a
    hole that lets locale-dependent writes through."""

    def _run(self, tmp_path, source):
        (tmp_path / "m.py").write_text(source, encoding="utf-8")
        rules = checks.load_rules("python", include_project=False)
        reports = checks.run_lang(tmp_path, "python", rules)
        return [f for r in reports for f in r.findings
                if f.rule_id == "python/pathlib-text-encoding"
                and not f.suppressed]

    def test_plane_utf8_writer_is_exempt(self, tmp_path):
        hits = self._run(tmp_path,
                         "from gov import atomicio\n"
                         "atomicio.write_text(p, text)\n")
        assert hits == [], "the plane's UTF-8-explicit writer is not the bug class"

    def test_locale_dependent_writes_are_still_flagged(self, tmp_path):
        hits = self._run(tmp_path,
                         "path.write_text(text)\n"
                         "self.helper.write_text(text)\n")
        assert len(hits) == 2, [f.line() for f in hits]

    def test_explicit_encoding_stays_discharged(self, tmp_path):
        hits = self._run(tmp_path,
                         "path.write_text(text, encoding='utf-8')\n")
        assert hits == []
