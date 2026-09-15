"""The one glob grammar: ``**`` spans zero or more directories.

M3's trap: ``**/x.py`` silently skipped a root-level ``x.py`` and
``a/**/b.py`` skipped ``a/b.py`` — users write gitignore conventions,
the old translator demanded a full directory between slashes.
"""
from __future__ import annotations

from gov.pathmatch import glob_to_regex, match_any


def test_double_star_leading_spans_zero_dirs():
    rx = glob_to_regex("**/x.py")
    assert rx.match("x.py")
    assert rx.match("a/x.py")
    assert rx.match("a/b/x.py")
    assert not rx.match("x.py.bak")


def test_double_star_middle_spans_zero_dirs():
    rx = glob_to_regex("a/**/b.py")
    assert rx.match("a/b.py")
    assert rx.match("a/x/b.py")
    assert rx.match("a/x/y/b.py")
    assert not rx.match("b.py")


def test_single_star_never_spans_separator():
    rx = glob_to_regex("docs/*.md")
    assert rx.match("docs/x.md")
    assert not rx.match("docs/sub/x.md")


def test_trailing_double_star_requires_something_beneath():
    rx = glob_to_regex("a/**")
    assert rx.match("a/x.py")
    assert rx.match("a/x/y.py")
    assert not rx.match("a")


def test_bare_double_star_matches_everything():
    assert glob_to_regex("**").match("a/b/c.py")
    assert glob_to_regex("**").match("x")


def test_question_mark_is_single_char():
    rx = glob_to_regex("?.py")
    assert rx.match("x.py")
    assert not rx.match("xy.py")
    assert not rx.match("/x.py")


def test_match_any_empty_patterns_matches_nothing():
    assert not match_any("anything", [])
    assert match_any("docs/x.md", ["docs/*.md", "other/**"])
