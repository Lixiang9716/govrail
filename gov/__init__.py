"""govrail — a language-agnostic governance plane for agent-driven development.

The plane ships two mechanisms: gates (mechanical checks) and notes (decision
records), delivered by the ``gov`` CLI. The runtime is Python 3 (>= 3.10) and the tree-sitter parser bindings (D54); nothing else.
"""

from .version import __version__

__all__ = ["__version__"]
