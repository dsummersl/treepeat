from dataclasses import dataclass, field
from enum import Enum


class RuleAction(Enum):
    REMOVE = "remove"
    REPLACE_NODE_TYPE = (
        "replace_node_type"  # Replaces the structural node type (e.g., 'binary_operator' -> '<OP>')
    )
    REPLACE_VALUE = "replace_value"  # Replaces the leaf node value (e.g., 'foo' -> 'FUNC')
    ANONYMIZE = "anonymize"
    EXTRACT_REGION = "extract_region"


@dataclass
class Rule:
    name: str
    languages: list[str]
    query: str  # Tree-sitter query pattern (required)
    action: RuleAction | None = None  # Action to perform on matched nodes
    target: str | None = None  # Capture name to target
    params: dict[str, str] = field(default_factory=dict)

    def matches_language(self, language: str) -> bool:
        """Check if this rule applies to the given language."""
        return "*" in self.languages or language in self.languages


@dataclass
class RuleResult:
    name: str | None = None
    value: str | None = None


class SkipNodeException(Exception):
    pass
