# Agent Note: new preset bundle files must ride the wheel's package-data (D66 follow-through)

Status: implemented
Related: D65, D66

## Problem

#310 added `note-presence.json` to the python-lib preset bundle, and
every non-editable install lost the presets: `gov preset list`,
`gov init --preset python-lib`, and `gov preset apply` exited 2 because
pyproject's `[tool.setuptools.package-data]` enumerated preset bundle
files by name (`presets/*/preset.json`, `presets/*/README.md`) and the
new file matched no glob. Editable/dev layouts read the source tree, so
the whole dev suite stayed green — the docker e2e shadow-install cells
were the only surface that caught it, on the accumulating release PR.

## Decision

The gov.templates package-data row broadens to `presets/*/*` (every
file directly in a preset bundle directory ships; the skills glob keeps
covering the nested SKILL.md tree), verified by building a wheel and
running `gov preset list` + `gov init --preset python-lib` from a
non-editable install. A new tests/test_packaging_data.py pins the
class structurally: every data file under gov/templates, gov/langs, and
gov/checks must be matched by at least one declared glob (modules and
__pycache__ excluded), with a negative control proving the pin bites on
the old enumeration.

## Alternatives considered

Fixing only the one glob (`presets/*/*.json`) — rejected: the next
bundle file with a different extension reintroduces the bug verbatim;
`presets/*/*` makes "drop a file in the bundle dir" packaging-safe by
construction. Runtime fallback that reads bundle files from the source
tree when missing — rejected: papering over a broken install with a
checkout dependency; the wheel is the distribution. Packaging checks in
the docker e2e only — rejected: the structural pin runs in seconds on
every push; the docker cells remain the runtime double-check.

## Addendum (same session)

The pin itself broke the 3.10 matrix cell: `tomllib` is stdlib from
3.11, and the support floor is 3.10 (D54). It now imports `tomli` under
3.10, declared as a version-gated dev dependency.
