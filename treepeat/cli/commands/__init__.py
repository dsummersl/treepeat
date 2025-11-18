"""CLI subcommands."""

from .detect import detect
from .list_ruleset import list_ruleset
from .treesitter import treesitter

__all__ = ["detect", "list_ruleset", "treesitter"]
