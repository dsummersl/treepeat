import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from treepeat.pipeline.rules.models import Rule, RuleAction, TargetLanguage

# Tree-sitter node types, grouped by category, whose name a rule may anonymize.
# A region_type is matched to a category either by name ("function", "class",
# "method") or because it *is* one of these node types (languages label some
# regions with the raw node type, e.g. Python's "function_definition").
_FUNCTION_NODES = (
    "function_declaration",
    "function_definition",
    "function_expression",
    "arrow_function",
    "method_definition",
)
_CLASS_NODES = ("class_declaration", "class_definition")

# Identifier node types that carry a declaration's name across grammars.
_IDENTIFIER_NODES = frozenset(
    {"identifier", "property_identifier", "type_identifier", "field_identifier"}
)

# In a tree-sitter query a named node type is a lowercase word directly after an
# opening paren, e.g. "(function_declaration". Extracting these as whole tokens
# (rather than substring-scanning the query) avoids matching predicate strings
# like (#match? @x "identifier") or partial names like async_function.
_NODE_TYPE_RE = re.compile(r"\(\s*([a-z_][a-z0-9_]*)")


def _query_node_types(query: str) -> set[str]:
    """Return the set of tree-sitter node types referenced by a query pattern."""
    return set(_NODE_TYPE_RE.findall(query))

_REGION_CATEGORIES: dict[str, tuple[str, ...]] = {
    "function": _FUNCTION_NODES,
    "method": _FUNCTION_NODES,
    "class": _CLASS_NODES,
}


def _region_name_nodes(region_type: str) -> tuple[str, ...]:
    """Return the node types whose name identifies this region_type, or ()."""
    if region_type in _REGION_CATEGORIES:
        return _REGION_CATEGORIES[region_type]
    if region_type in _FUNCTION_NODES:
        return _FUNCTION_NODES
    if region_type in _CLASS_NODES:
        return _CLASS_NODES
    return ()


@dataclass
class RegionExtractionRule:
    """Configuration for extracting a specific type of region from a language."""

    label: str
    query: str
    # When set, the matched node's content is re-parsed as this language so the
    # shingler produces target-language-quality shingles (language injection).
    # May be a static string ("typescript") or a callable that resolves the
    # language dynamically from the matched node (e.g. Markdown code blocks).
    target_language: TargetLanguage = None
    # Optional tree-sitter query (compiled against the *primary* language
    # grammar) that selects the child node whose raw bytes are injected.
    # When None, the entire matched node's bytes are used.
    content_query: str | None = None

    @classmethod
    def from_node_type(cls, node_type: str) -> "RegionExtractionRule":
        return cls(
            label=node_type,
            query=f"({node_type}) @region",
        )


class LanguageConfig(ABC):
    """Base class for language-specific configuration."""

    @abstractmethod
    def get_default_rules(self) -> list[Rule]:
        """Return list of Rule objects for default normalization mode."""
        pass

    @abstractmethod
    def get_loose_rules(self) -> list[Rule]:
        """Return list of Rule objects for loose normalization mode (including default rules)."""
        pass

    @abstractmethod
    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        """Return list of regions to perform similarity comparisons for this language."""
        pass


def _rule_anonymizes_name(rule: Rule, language: str, node_types: tuple[str, ...]) -> bool:
    """True if this rule replaces an identifier on one of the given declaration nodes.

    Matches on the query's node types rather than the capture name (which is
    arbitrary: JS uses @name, Python uses @func). The query must reference both
    an identifier node and one of the declaration nodes, so a rule that targets
    a non-name child of a declaration (e.g. a string literal) does not count.
    """
    if rule.action is not RuleAction.REPLACE_VALUE or not rule.matches_language(language):
        return False
    query_nodes = _query_node_types(rule.query)
    return not query_nodes.isdisjoint(_IDENTIFIER_NODES) and not query_nodes.isdisjoint(
        node_types
    )


def rules_anonymize_region_name(
    rules: list[Rule], language: str, region_type: str
) -> bool:
    """Return True if the ACTIVE rules replace this region type's name.

    When the active ruleset anonymizes function/class/method names (so shingles
    ignore identifiers), a name-only signature difference is intentional and
    must not be penalized during verification. Consulting the active rules —
    not a language's default rules — means the ``none`` ruleset (which strips
    the anonymization rules) correctly leaves name differences penalized.
    """
    node_types = _region_name_nodes(region_type)
    if not node_types:
        return False
    return any(_rule_anonymizes_name(rule, language, node_types) for rule in rules)
