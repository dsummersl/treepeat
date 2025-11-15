"""Data models for the rules system."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class RuleAction(Enum):
    """Actions for tree-sitter query-based rules."""

    REMOVE = "remove"  # Skip/remove matched nodes
    RENAME = "rename"  # Rename matched nodes
    REPLACE_VALUE = "replace_value"  # Replace node values
    ANONYMIZE = "anonymize"  # Anonymize identifiers
    CANONICALIZE = "canonicalize"  # Canonicalize types
    EXTRACT_REGION = "extract_region"  # Mark regions for extraction


@dataclass
class Rule:
    """Represents a tree-sitter query-based rule."""

    name: str
    languages: list[str]
    query: str  # Tree-sitter query pattern (required)
    action: Optional[RuleAction] = None  # Action to perform on matched nodes
    target: Optional[str] = None  # Capture name to target
    params: dict[str, str] = field(default_factory=dict)

    def matches_language(self, language: str) -> bool:
        """Check if this rule applies to the given language."""
        return "*" in self.languages or language in self.languages


@dataclass
class RuleResult:
    """Result of applying a rule to a node."""

    name: Optional[str] = None  # New name for the node
    value: Optional[str] = None  # New value for the node


class SkipNodeException(Exception):
    """Exception raised when a rule indicates a node should be skipped."""

    pass
