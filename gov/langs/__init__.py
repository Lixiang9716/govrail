"""Language packs: data, not code (D56).

Each ``<lang>.json`` declares how the parse layer treats one language:
which files belong to it, which tree-sitter grammar provides its syntax,
and which node kinds carry the structural meaning the metrics consume.
The engine (``gov/parse.py``, ``gov/stats.py``) never names a language;
adding one is adding a pack, not touching code.
"""
