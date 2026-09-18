#!/usr/bin/env python3
"""Package layering gate: leaves stay leaves, the dispatcher stays on top.

The gov package is a modular monolith with three mechanical commitments
(see docs/architecture.md, "Code design contracts"):

1. **Leaf modules** (pure utilities and the registries) import no other
   gov module — they are the floor everyone stands on;
2. **The dispatcher** (gov/cli.py) is imported only by declared
   entrypoints — nothing in the package reaches back up;
3. **No import cycles** — a cycle is the first step back to the junk
   drawer cli.py used to be.

The tier map lives in ``scripts/import-layers.json`` (limits declared,
not hardcoded, like every other gate input). Adding a module needs no
config: unlisted modules are core, free to import anything but the
dispatcher and the leaves. Exit codes follow D2: 0 ok, 1 violation
(every offender named), 2 config/usage error.

This checker imports nothing from the package it judges — it is plain
AST over the source, so it can judge a fixture tree via ``--root`` too
(that is how the rejection case proves it can go red). Declared scope:
static ``import``/``from`` statements in both spellings;
``importlib.import_module`` and other dynamic imports are invisible to
an AST walk and out of this gate's contract.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parent / "import-layers.json"


def load_config(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"import-layers: unreadable config {path}: {e}", file=sys.stderr)
        raise SystemExit(2)
    if not isinstance(raw, dict):
        print(f"import-layers: {path} must be a JSON object", file=sys.stderr)
        raise SystemExit(2)
    for key in ("package", "leaves", "top", "cli_importers_allowed"):
        if key not in raw:
            print(f"import-layers: {path} lacks key '{key}'", file=sys.stderr)
            raise SystemExit(2)
    if not isinstance(raw["leaves"], list) or not isinstance(raw["top"], list) \
            or not isinstance(raw["cli_importers_allowed"], list):
        print(f"import-layers: {path}: 'leaves', 'top', 'cli_importers_allowed' "
              "must be arrays", file=sys.stderr)
        raise SystemExit(2)
    unknown = set(raw) - {"package", "leaves", "top", "cli_importers_allowed"}
    if unknown:
        # rule 5: a misspelled key would silently stop meaning anything.
        print(f"import-layers: {path}: unknown key(s) "
              f"{', '.join(sorted(unknown))}", file=sys.stderr)
        raise SystemExit(2)
    return raw


def _edge_targets(node: ast.AST, package: str) -> set[str]:
    """Internal edges of one import statement, in BOTH spellings — the
    relative form (`from . import x`, `from .x import y`) and the
    absolute form (`from gov import x`, `from gov.x import y`,
    `import gov.x`). Missing the absolute form once shipped a false
    green: a declared leaf reached gates through `from gov.gates
    import parse_cost` and the gate reported 54 modules ok (found by
    the round's independent review)."""
    found: set[str] = set()
    prefix = package.split(".")[-1]
    if isinstance(node, ast.ImportFrom):
        if node.level >= 1:
            if node.module:
                # from .mod import name — the dependency is mod, never the
                # imported symbol (a symbol may share a module's name).
                found.add(node.module.split(".")[0])
            else:
                # from . import mod1, mod2 — the names ARE the modules.
                for alias in node.names:
                    if alias.name != "*":
                        found.add(alias.name.split(".")[0])
        elif node.module == package:
            # from gov import mod1, mod2 — same as the relative bare form.
            for alias in node.names:
                if alias.name != "*":
                    found.add(alias.name.split(".")[0])
        elif node.module and node.module.startswith(package + "."):
            # from gov.mod import name — the dependency is mod.
            found.add(node.module[len(package) + 1:].split(".")[0])
    elif isinstance(node, ast.Import):
        for alias in node.names:
            parts = alias.name.split(".")
            if parts[0] == prefix:
                if len(parts) > 1:
                    found.add(parts[1])
                else:
                    # bare `import gov` — the package __init__ edge
                    found.add("__init__")
    return found


def _static_import_nodes(tree: ast.AST) -> list[ast.AST]:
    """Import statements that EXECUTE at module import time: module body,
    including ones nested in module-level if/try/with (the try/except
    direct-script fallback idiom is an import-time edge)."""
    static: list[ast.AST] = []
    def walk(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.Import, ast.ImportFrom)):
                static.append(child)
            elif isinstance(child, (ast.If, ast.Try, ast.With, ast.AsyncWith,
                                    ast.For, ast.While)):
                walk(child)
    walk(tree)
    return static


def internal_imports(path: Path, package: str) -> tuple[set[str], set[str]]:
    """(static, lazy) internal imports of this file. Static = executed at
    import time and so part of the graph that must initialize cleanly;
    lazy = function-level deferrals, the codebase's deliberate
    decoupling device — direction rules still apply, cycle rules do not
    (a deferred edge cannot tangle initialization)."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    static_ids = {id(n) for n in _static_import_nodes(tree)}
    static: set[str] = set()
    lazy: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            targets = _edge_targets(node, package)
            if id(node) in static_ids:
                static |= targets
            else:
                lazy |= targets
    return static, lazy


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check_import_layers")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parent.parent),
                        help="repository root containing the package (default: this checkout)")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args(argv)

    root = Path(args.root)
    cfg = load_config(Path(args.config))
    pkg_dir = root / cfg["package"].replace(".", "/")
    if not pkg_dir.is_dir():
        print(f"import-layers: no package directory {pkg_dir}", file=sys.stderr)
        return 2

    modules: dict[str, Path] = {}
    for f in pkg_dir.rglob("*.py"):
        rel = f.relative_to(pkg_dir)
        name = ".".join(rel.with_suffix("").parts)
        if name.endswith(".__init__"):
            name = name[: -len(".__init__")] or "__init__"
        if name == "__main__":
            continue  # entrypoint shims are judged as importers, not modules
        modules[name] = f

    problems: list[str] = []
    deps: dict[str, set[str]] = {}
    leaves = set(cfg["leaves"])
    tops = set(cfg["top"])
    allowed_importers = set(cfg["cli_importers_allowed"])
    for name in [*cfg["leaves"], *cfg["top"], *cfg["cli_importers_allowed"]]:
        if name != "__main__" and name not in modules:
            problems.append(f"config names module '{name}' which does not exist "
                            f"under {cfg['package']}/")
    lazy_edges = 0
    for name, path in sorted(modules.items()):
        static, lazy = internal_imports(path, cfg["package"])
        lazy = {d for d in lazy if d in modules}
        static = {d for d in static if d in modules}
        deps[name] = static
        lazy_edges += len(lazy - static)
        for dep in sorted(static | lazy):
            if name in leaves:
                problems.append(f"leaf '{cfg['package']}/{name}.py' imports "
                                f"'{cfg['package']}/{dep}.py' — leaves import no gov module")
            if name not in allowed_importers and dep in tops:
                problems.append(f"'{cfg['package']}/{name}.py' imports the dispatcher "
                                f"'{cfg['package']}/{dep}.py' — only "
                                f"{', '.join(sorted(allowed_importers))} may")

    # cycle check (DFS, three colors)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {m: WHITE for m in modules}
    cycles: list[list[str]] = []

    def dfs(m: str, stack: list[str]) -> None:
        color[m] = GRAY
        for n in sorted(deps.get(m, ())):
            if color[n] == GRAY:
                cycles.append(stack[stack.index(n):] + [n])
            elif color[n] == WHITE:
                dfs(n, stack + [n])
        color[m] = BLACK

    for m in sorted(modules):
        if color[m] == WHITE:
            dfs(m, [m])
    for cyc in cycles:
        problems.append("import cycle: " + " -> ".join(
            f"{cfg['package']}/{c}.py" for c in cyc))

    if problems:
        for p in problems:
            print(f"import-layers: {p}", file=sys.stderr)
        print(f"import-layers: {len(problems)} violation(s)", file=sys.stderr)
        return 1
    print(f"import-layers: {len(modules)} modules ok "
          f"({len(leaves)} leaves, dispatcher importers: "
          f"{', '.join(sorted(allowed_importers))}, "
          f"{lazy_edges} lazy edge(s) — direction-checked, cycle-exempt)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
