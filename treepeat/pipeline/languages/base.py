import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from treepeat.pipeline.rules.models import Rule, RuleAction, TargetLanguage

_FUNCTION_NODES = (
    "function_declaration",
    "function_definition",
    "function_expression",
    "arrow_function",
    "method_definition",
    "method_declaration",
)
_CLASS_NODES = ("class_declaration", "class_definition")


_IDENTIFIER_NODES = frozenset(
    {"identifier", "property_identifier", "type_identifier", "field_identifier", "name"}
)





_NODE_TYPE_RE = re.compile(r"\(\s*([a-z_][a-z0-9_]*)")


def _query_node_types(query: str) -> set[str]:

    return set(_NODE_TYPE_RE.findall(query))

_REGION_CATEGORIES: dict[str, tuple[str, ...]] = {
    "function": _FUNCTION_NODES,
    "method": _FUNCTION_NODES,
    "class": _CLASS_NODES,
}


def _region_name_nodes(region_type: str) -> tuple[str, ...]:

    if region_type in _REGION_CATEGORIES:
        return _REGION_CATEGORIES[region_type]
    if region_type in _FUNCTION_NODES:
        return _FUNCTION_NODES
    if region_type in _CLASS_NODES:
        return _CLASS_NODES
    return ()


@dataclass
class RegionExtractionRule:


    label: str
    query: str




    target_language: TargetLanguage = None



    content_query: str | None = None

    @classmethod
    def from_node_type(cls, node_type: str) -> "RegionExtractionRule":
        return cls(
            label=node_type,
            query=f"({node_type}) @region",
        )


class LanguageConfig(ABC):


    @abstractmethod
    def get_default_rules(self) -> list[Rule]:

        pass

    @abstractmethod
    def get_loose_rules(self) -> list[Rule]:

        pass

    @abstractmethod
    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:

        pass


def _rule_anonymizes_name(rule: Rule, language: str, node_types: tuple[str, ...]) -> bool:

    if rule.action is not RuleAction.REPLACE_VALUE or not rule.matches_language(language):
        return False
    query_nodes = _query_node_types(rule.query)
    return not query_nodes.isdisjoint(_IDENTIFIER_NODES) and not query_nodes.isdisjoint(
        node_types
    )


def rules_anonymize_region_name(
    rules: list[Rule], language: str, region_type: str
) -> bool:

    node_types = _region_name_nodes(region_type)
    if not node_types:
        return False
    return any(_rule_anonymizes_name(rule, language, node_types) for rule in rules)
