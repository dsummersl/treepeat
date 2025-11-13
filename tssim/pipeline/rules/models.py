"""Data models for the rules system."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RuleOperation(Enum):
    """Supported rule operations."""

    SKIP = "skip"
    REPLACE_NAME = "replace_name"
    REPLACE_VALUE = "replace_value"
    ANONYMIZE_IDENTIFIERS = "anonymize_identifiers"
    CANONICALIZE_TYPES = "canonicalize_types"


@dataclass
class Rule:
    """
    Represents a single rule that can be applied to syntax tree nodes.

    Rules follow the format:
    <lang|*> : <op> : nodes=<node1|node2|glob*> [,:k=v ...]

    Examples:
        python:skip:nodes=import_statement|import_from_statement
        python:replace_value:nodes=string|integer|float,value=<LIT>
        *:anonymize_identifiers:nodes=identifier,scheme=flat,prefix=VAR
    """

    language: str  # Language name or "*" for all languages
    operation: RuleOperation
    node_patterns: list[str]  # Node type patterns (can include wildcards)
    params: dict[str, str]  # Additional parameters like value=<LIT>, prefix=VAR, etc.

    def matches_language(self, language: str) -> bool:
        """Check if this rule applies to the given language."""
        return self.language == "*" or self.language == language

    def matches_node_type(self, node_type: str) -> bool:
        """Check if this rule applies to the given node type."""
        for pattern in self.node_patterns:
            if self._matches_pattern(node_type, pattern):
                return True
        return False

    @staticmethod
    def _matches_pattern(node_type: str, pattern: str) -> bool:
        """Check if a node type matches a pattern (supports * wildcard at end)."""
        if pattern == node_type:
            return True
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return node_type.startswith(prefix)
        return False


@dataclass
class RuleResult:
    """
    Result of applying a rule to a node.

    Similar to NormalizationResult but for rules.
    """

    name: Optional[str] = None  # New name for the node
    value: Optional[str] = None  # New value for the node


class SkipNodeException(Exception):
    """
    Exception raised when a rule indicates a node should be skipped.

    Similar to SkipNode from normalizers.
    """

    pass
