#!/bin/sh
# gate: import-layers
# Proves the layering gate rejects (rule 6): a leaf that imports a gov
# module, a core module that imports the cli dispatcher, and an import
# cycle each go red naming the offenders — and a clean package passes.
set -u
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT


# A clean two-module package passes.
mkdir -p "$scratch/gov"
printf 'x = 1\n' > "$scratch/gov/atomicio.py"
printf 'from . import atomicio\n' > "$scratch/gov/core_mod.py"
printf 'y = 1\n' > "$scratch/gov/cli.py"
printf '__import__ = None\n' > "$scratch/gov/__init__.py"
cat > "$scratch/cfg.json" <<EOF
{"package": "gov", "leaves": ["atomicio"], "top": ["cli"],
 "cli_importers_allowed": ["__main__"]}
EOF
if python3 scripts/check_import_layers.py --root "$scratch" --config "$scratch/cfg.json" >"$scratch/out.txt" 2>&1; then
  : green
else
  echo "case-import-layers: a clean package went red" >&2
  cat "$scratch/out.txt" >&2
  exit 1
fi

# 1. A leaf importing a gov module is named.
printf 'from . import core_mod\n' > "$scratch/gov/atomicio.py"
if python3 scripts/check_import_layers.py --root "$scratch" --config "$scratch/cfg.json" >"$scratch/out.txt" 2>&1; then
  echo "case-import-layers: a leaf importing a gov module passed the gate" >&2
  exit 1
fi
grep -q "leaf 'gov/atomicio.py'" "$scratch/out.txt" || {
  echo "case-import-layers: the leaf violation is not named" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}

# 2. A core module importing the dispatcher is named.
printf 'x = 1\n' > "$scratch/gov/atomicio.py"
printf 'from . import cli\n' > "$scratch/gov/core_mod.py"
printf 'y = 1\n' > "$scratch/gov/cli.py"
if python3 scripts/check_import_layers.py --root "$scratch" --config "$scratch/cfg.json" >"$scratch/out.txt" 2>&1; then
  echo "case-import-layers: an import of the dispatcher passed the gate" >&2
  exit 1
fi
grep -q "imports the dispatcher 'gov/cli.py'" "$scratch/out.txt" || {
  echo "case-import-layers: the dispatcher violation is not named" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}

# 3. A cycle is named.
printf 'x = 1\n' > "$scratch/gov/cli.py"
printf 'from . import other\n' > "$scratch/gov/core_mod.py"
printf 'from . import core_mod\n' > "$scratch/gov/other.py"
if python3 scripts/check_import_layers.py --root "$scratch" --config "$scratch/cfg.json" >"$scratch/out.txt" 2>&1; then
  echo "case-import-layers: an import cycle passed the gate" >&2
  exit 1
fi
grep -q "import cycle" "$scratch/out.txt" || {
  echo "case-import-layers: the cycle is not named" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}

# 4. A LAZY (function-level) import still violates leaf direction.
printf 'x = 1\n' > "$scratch/gov/atomicio.py"
printf 'y = 1\n' > "$scratch/gov/cli.py"
printf 'from . import atomicio\n' > "$scratch/gov/core_mod.py"
printf 'from .other import side\n' > "$scratch/gov/other.py"
printf 'def later():\n    from . import core_mod\n' > "$scratch/gov/lazyleaf.py"
cat > "$scratch/cfg-lazy.json" <<EOF
{"package": "gov", "leaves": ["atomicio", "lazyleaf"], "top": ["cli"],
 "cli_importers_allowed": ["__main__"]}
EOF
if python3 scripts/check_import_layers.py --root "$scratch" --config "$scratch/cfg-lazy.json" >"$scratch/out.txt" 2>&1; then
  echo "case-import-layers: a lazy leaf violation passed the gate" >&2
  exit 1
fi
grep -q "leaf 'gov/lazyleaf.py'" "$scratch/out.txt" || {
  echo "case-import-layers: the lazy leaf violation is not named" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}

# 5. The ABSOLUTE spelling is judged identically: a leaf reaching a gov
#    module via `from gov import x` (the form the first checker missed,
#    shipping a false green) is named too.
printf 'x = 1\n' > "$scratch/gov/atomicio.py"
printf 'def later():\n    from gov import core_mod\n' > "$scratch/gov/atomicio.py"
printf 'from . import atomicio\n' > "$scratch/gov/core_mod.py"
printf 'q = 1\n' > "$scratch/gov/cli.py"
if python3 scripts/check_import_layers.py --root "$scratch" --config "$scratch/cfg-lazy.json" >"$scratch/out.txt" 2>&1; then
  echo "case-import-layers: an absolute-form leaf violation passed the gate" >&2
  exit 1
fi
grep -q "leaf 'gov/atomicio.py'" "$scratch/out.txt" || {
  echo "case-import-layers: the absolute-form leaf violation is not named" >&2
  cat "$scratch/out.txt" >&2
  exit 1
}

echo "case-import-layers: rejection proof holds"
exit 0
