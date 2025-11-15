"""Data models for the rules system."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RuleOperation(Enum):
    """Supported rule operations."""

    SKIP = "skip"
    REPLACE_NAME = "replace_name"
    REPLACE_VALUE = "replace_value"
    ANONYMIZE_IDENTIFIERS = "anonymize_identifiers"
    CANONICALIZE_TYPES = "canonicalize_types"
    EXTRACT_REGION = "extract_region"


class RuleAction(Enum):
    """Actions for query-based rules."""

    REMOVE = "remove"  # Skip/remove matched nodes
    RENAME = "rename"  # Rename matched nodes
    REPLACE_VALUE = "replace_value"  # Replace node values
    ANONYMIZE = "anonymize"  # Anonymize identifiers
    CANONICALIZE = "canonicalize"  # Canonicalize types
    EXTRACT_REGION = "extract_region"  # Mark regions for extraction


@dataclass
class Rule:
    """Represents a single rule that can be applied to syntax tree nodes.

    Supports both legacy node-pattern matching and new treesitter query syntax.
    """

    # Common fields
    name: str
    languages: list[str]
    params: dict[str, str] = field(default_factory=dict)

    # New query-based fields
    query: Optional[str] = None
    action: Optional[RuleAction] = None
    target: Optional[str] = None  # Capture name to target

    # Legacy fields (for backward compatibility)
    operation: Optional[RuleOperation] = None
    node_patterns: Optional[list[str]] = None

    @property
    def language(self) -> str:
        """Get the first language (for backward compatibility with legacy code)."""
        return self.languages[0] if self.languages else "*"

    def is_query_based(self) -> bool:
        """Check if this is a query-based rule."""
        return self.query is not None

    def matches_language(self, language: str) -> bool:
        """Check if this rule applies to the given language."""
        return "*" in self.languages or language in self.languages

    def matches_node_type(self, node_type: str) -> bool:
        """Check if this rule applies to the given node type (legacy only)."""
        if self.node_patterns is None:
            return False
        for pattern in self.node_patterns:
            if self._matches_pattern(node_type, pattern):
                return True
        return False

    @staticmethod
    def _matches_pattern(node_type: str, pattern: str) -> bool:
        """Check if a node type matches a pattern with wildcard support."""
        if pattern == node_type:
            return True
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return node_type.startswith(prefix)
        return False


@dataclass
class RuleResult:
    """Result of applying a rule to a node."""

    name: Optional[str] = None  # New name for the node
    value: Optional[str] = None  # New value for the node


class SkipNodeException(Exception):
    """Exception raised when a rule indicates a node should be skipped."""

    pass
