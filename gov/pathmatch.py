#!/usr/bin/env python3
"""One path-glob grammar for the whole plane.

Three grammars used to coexist — the gate engine's translator, parse's
``fnmatch``, and the hook shell's matching — and they disagreed on what
``*`` spans and what ``**`` means (a ``paths`` filter written by
convention silently selected a different file set per consumer). One
translator now serves everyone:

- ``*``/``?`` never span ``/``;
- a ``**`` segment spans directories *including zero* — ``**/x.py``
  matches ``x.py`` and ``a/b/x.py``; ``a/**/b.py`` matches ``a/b.py``
  and ``a/x/b.py`` (gitignore and shell globstar conventions);
- a trailing ``**`` spans everything beneath (``a/**`` matches ``a/x.py``
  but not ``a`` itself).
"""
from __future__ import annotations

import re

_RX_CACHE: dict[str, re.Pattern[str]] = {}


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Compile a path glob under the plane's single grammar."""
    rx = _RX_CACHE.get(pattern)
    if rx is not None:
        return rx
    out: list[str] = ["^"]
    i, n = 0, len(pattern)
    while i < n:
        c = pattern[i]
        if c == "*":
            if pattern[i : i + 3] == "**/":
                # A leading/middle "**/" may span zero directories.
                out.append("(?:[^/]+/)*")
                i += 3
            elif pattern[i : i + 2] == "**":
                # A trailing (or bare) "**" spans everything beneath.
                out.append(".*")
                i += 2
            else:
                out.append("[^/]*")
                i += 1
        elif c == "/" and pattern[i : i + 4] == "/**/":
            # "a/**/b" == "a/" + zero-or-more dirs + "b" — "a/b" included.
            out.append("/(?:[^/]+/)*")
            i += 4
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    out.append("$")
    rx = re.compile("".join(out))
    _RX_CACHE[pattern] = rx
    return rx


def match_any(path: str, patterns: list[str]) -> bool:
    """True when ``path`` matches any pattern; empty pattern list matches nothing."""
    return any(glob_to_regex(p).match(path) for p in patterns)
