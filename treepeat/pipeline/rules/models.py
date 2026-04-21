from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Union

from tree_sitter import Node


class RuleAction(Enum):
    REMOVE = "remove"
    REPLACE_NODE_TYPE = (
        "replace_node_type"  # Replaces the structural node type (e.g., 'binary_operator' -> '<OP>')
    )
    REPLACE_VALUE = "replace_value"  # Replaces the leaf node value (e.g., 'foo' -> 'FUNC')
    ANONYMIZE = "anonymize"
    EXTRACT_REGION = "extract_region"


# A target language is either a static string (e.g. "typescript") or a callable
# that inspects the matched AST node and returns the language name dynamically
# (e.g. reading the info-string of a Markdown fenced code block).
TargetLanguage = Union[str, Callable[[Node, bytes], str], None]


@dataclass
class Rule:
    name: str
    languages: list[str]
    query: str  # Tree-sitter query pattern (required)
    action: RuleAction | None = None  # Action to perform on matched nodes
    target: str | None = None  # Capture name to target
    params: dict[str, str] = field(default_factory=dict)
    # For EXTRACT_REGION rules: re-parse the matched node's content as this
    # language so the shingler produces target-language-quality shingles.
    injection_language: TargetLanguage = field(default=None, compare=False, hash=False)
    # Optional tree-sitter query (run against the *primary* grammar) that
    # identifies the child node whose bytes should be injected.  When None the
    # full matched-node bytes are used.
    injection_content_query: str | None = None

    def matches_language(self, language: str) -> bool:
        """Check if this rule applies to the given language."""
        return "*" in self.languages or language in self.languages

    def resolve_injection_language(self, node: Node, source: bytes) -> str | None:
        """Return the target language for injection, or None if not applicable."""
        if self.injection_language is None:
            return None
        if callable(self.injection_language):
            return self.injection_language(node, source)
        return self.injection_language


class SkipNodeException(Exception):
    pass
