from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Union

from tree_sitter import Node


class RuleAction(Enum):
    REMOVE = "remove"
    REPLACE_NODE_TYPE = "replace_node_type"
    REPLACE_VALUE = "replace_value"
    ANONYMIZE = "anonymize"
    EXTRACT_REGION = "extract_region"


TargetLanguage = Union[str, Callable[[Node, bytes], str], None]


@dataclass
class Rule:
    name: str
    languages: list[str]
    query: str
    action: RuleAction | None = None
    target: str | None = None
    params: dict[str, str] = field(default_factory=dict)

    injection_language: TargetLanguage = field(default=None, compare=False, hash=False)

    injection_content_query: str | None = None

    def matches_language(self, language: str) -> bool:

        return "*" in self.languages or language in self.languages

    def resolve_injection_language(self, node: Node, source: bytes) -> str | None:

        if self.injection_language is None:
            return None
        if callable(self.injection_language):
            return self.injection_language(node, source)
        return self.injection_language


class SkipNodeException(Exception):
    pass
