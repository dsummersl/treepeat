from typing import Any, Callable, Optional

from tree_sitter import Node, Query, QueryCursor
from tree_sitter_language_pack import get_language

from .models import Rule, RuleAction, SkipNodeException
from ..languages import LANGUAGE_CONFIGS


def _extract_node_text(node: Node, source: bytes) -> str:
    """Extract text content from a node."""
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")


class RuleEngine:
    """Engine for applying tree-sitter query-based rules to syntax tree nodes."""

    def __init__(self, rules: list[Rule]):
        """Initialize the rule engine with a list of rules."""
        self.rules = rules
        self._identifier_counters: dict[str, int] = {}
        self._identifier_mapping: dict[str, str] = {}
        self._action_handlers = self._build_action_handlers()
        self._compiled_queries: dict[tuple[str, str], Query] = {}
        self._query_matches_cache: dict[int, list[dict[str, Any]]] = {}
        self._source: bytes | None = None  # Store source for value extraction

    def _build_action_handlers(
        self,
    ) -> dict[
        RuleAction,
        Callable[
            [Rule, Node, str, str, Optional[str], Optional[str]],
            tuple[Optional[str], Optional[str]],
        ],
    ]:
        """Build mapping of actions to handler functions."""
        return {
            RuleAction.REMOVE: self._handle_remove,
            RuleAction.REPLACE_NODE_TYPE: self._handle_replace_node_type,
            RuleAction.REPLACE_VALUE: self._handle_replace_value,
            RuleAction.ANONYMIZE: self._handle_anonymize,
        }

    def _get_anonymized_identifier(self, prefix: str, original_value: str) -> str:
        """Generate an anonymized identifier, consistent for the same original value."""
        # Create a key combining prefix and original value to maintain consistency
        key = f"{prefix}:{original_value}"
        if key not in self._identifier_mapping:
            # First time seeing this identifier, assign it a new number
            if prefix not in self._identifier_counters:
                self._identifier_counters[prefix] = 0
            self._identifier_counters[prefix] += 1
            self._identifier_mapping[key] = f"{prefix}_{self._identifier_counters[prefix]}"
        return self._identifier_mapping[key]

    def _get_compiled_query(self, language: str, query_str: str) -> Query:
        """Get or compile a query for a language."""
        key = (language, query_str)
        if key not in self._compiled_queries:
            lang = get_language(language)  # type: ignore[arg-type]
            self._compiled_queries[key] = Query(lang, query_str)
        return self._compiled_queries[key]

    def _index_query_captures(
        self,
        all_matches: dict[int, list[dict[str, Any]]],
        query_str: str,
        match_id: int,
        captures_dict: dict[str, list[Node]],
    ) -> None:
        """Index captures from a single query match by node ID."""
        for capture_name, nodes in captures_dict.items():
            for node in nodes:
                if node.id not in all_matches:
                    all_matches[node.id] = []
                all_matches[node.id].append(
                    {
                        "query": query_str,
                        "match_id": match_id,
                        "captures": captures_dict,
                        "capture_name": capture_name,
                    }
                )

    def _get_all_matches(
        self, root_node: Node, query_strings: list[str], language: str
    ) -> dict[int, list[dict[str, Any]]]:
        """Execute multiple queries and collect all matches indexed by node ID."""
        all_matches: dict[int, list[dict[str, Any]]] = {}

        for query_str in query_strings:
            query = self._get_compiled_query(language, query_str)
            cursor = QueryCursor(query)

            for match_id, captures_dict in cursor.matches(root_node):
                self._index_query_captures(all_matches, query_str, match_id, captures_dict)

        return all_matches

    def _get_query_match_result(self, rule: Rule) -> str:
        """Get the result to return for a query match."""
        return rule.target or "match"

    def _check_node_matches_query(
        self, node: Node, rule: Rule, language: str, root_node: Node
    ) -> Optional[str]:
        """Check if a node matches a tree-sitter query.

        Returns the capture name if matched, None otherwise.
        """
        # Look up node in the pre-computed cache
        if node.id in self._query_matches_cache:
            # Check if any of the matches are for this rule's query
            for match_info in self._query_matches_cache[node.id]:
                if match_info["query"] == rule.query:
                    return self._get_query_match_result(rule)

        return None

    def _handle_remove(
        self,
        rule: Rule,
        node: Node,
        node_type: str,
        language: str,
        name: Optional[str],
        value: Optional[str],
    ) -> tuple[Optional[str], Optional[str]]:
        """Handle REMOVE action - skip/remove matched nodes."""
        raise SkipNodeException(
            f"Node type '{node_type}' matched remove rule for language '{language}'"
        )

    def _handle_replace_node_type(
        self,
        rule: Rule,
        node: Node,
        node_type: str,
        language: str,
        name: Optional[str],
        value: Optional[str],
    ) -> tuple[Optional[str], Optional[str]]:
        """Handle REPLACE_NODE_TYPE action - replaces the node type name."""
        return rule.params.get("token", "<NODE>"), value

    def _handle_replace_value(
        self,
        rule: Rule,
        node: Node,
        node_type: str,
        language: str,
        name: Optional[str],
        value: Optional[str],
    ) -> tuple[Optional[str], Optional[str]]:
        """Handle REPLACE_VALUE action - replace node values."""
        return name, rule.params.get("value", "<LIT>")

    def _handle_anonymize(
        self,
        rule: Rule,
        node: Node,
        node_type: str,
        language: str,
        name: Optional[str],
        value: Optional[str],
    ) -> tuple[Optional[str], Optional[str]]:
        """Handle ANONYMIZE action - anonymize identifiers."""
        prefix = rule.params.get("prefix", "VAR")
        # Extract the original node text to ensure consistent anonymization
        if self._source is not None:
            original_value = _extract_node_text(node, self._source)
        else:
            original_value = value or "unknown"
        return name, self._get_anonymized_identifier(prefix, original_value)

    def _apply_action(
        self,
        rule: Rule,
        node: Node,
        node_type: str,
        language: str,
        name: Optional[str],
        value: Optional[str],
    ) -> tuple[Optional[str], Optional[str]]:
        """Apply a rule action."""
        if not rule.action:
            return name, value

        handler = self._action_handlers.get(rule.action)
        if handler:
            return handler(rule, node, node_type, language, name, value)

        return name, value

    def _apply_matching_rule(
        self,
        rule: Rule,
        node: Node,
        node_type: str,
        language: str,
        root_node: Node,
        name: Optional[str],
        value: Optional[str],
    ) -> tuple[Optional[str], Optional[str]]:
        """Apply a rule if it matches the node."""
        capture_name = self._check_node_matches_query(node, rule, language, root_node)
        if capture_name:
            return self._apply_action(rule, node, node_type, language, name, value)
        return name, value

    def apply_rules(
        self,
        node: Node,
        language: str,
        node_name: Optional[str] = None,
        root_node: Optional[Node] = None,
    ) -> tuple[Optional[str], Optional[str]]:
        """Apply all matching rules to a node."""
        node_type = node_name or node.type
        name = None
        value = None
        root_node = root_node or node

        for rule in self.rules:
            if rule.matches_language(language):
                name, value = self._apply_matching_rule(
                    rule, node, node_type, language, root_node, name, value
                )

        return name, value

    def reset_identifiers(self) -> None:
        """Reset the identifier counter, mapping, and query cache."""
        self._identifier_counters.clear()
        self._identifier_mapping.clear()
        self._query_matches_cache.clear()

    def precompute_queries(
        self, root_node: Node, language: str, source: bytes | None = None
    ) -> None:
        """Pre-execute all queries for a root node to populate the cache.

        This executes all queries once and indexes matches by node ID for O(1) lookup.
        Call this once per region after reset_identifiers().
        """
        # Store source for use in anonymization
        self._source = source

        # Collect all query strings for this language
        query_strings = [rule.query for rule in self.rules if rule.matches_language(language)]

        # Execute all queries once and cache results indexed by node.id
        self._query_matches_cache = self._get_all_matches(root_node, query_strings, language)

    def get_region_extraction_rules(self, language: str) -> list[tuple[str, str]]:
        """Get region extraction rules for a language.

        Returns list of tuples: (query, region_type)
        """
        region_rules = []
        for rule in self.rules:
            if rule.action == RuleAction.EXTRACT_REGION and rule.matches_language(language):
                region_type = rule.params.get("region_type")
                if region_type:
                    region_rules.append((rule.query, region_type))
        return region_rules

    def get_nodes_matching_query(
        self, root_node: Node, query_str: str, language: str
    ) -> list[Node]:
        """Execute a query and return all matching nodes."""
        query = self._get_compiled_query(language, query_str)
        cursor = QueryCursor(query)
        matching_nodes = []

        for match_id, captures_dict in cursor.matches(root_node):
            # Collect all captured nodes from this match
            for capture_name, nodes in captures_dict.items():
                matching_nodes.extend(nodes)

        return matching_nodes


def build_region_extraction_rules() -> list[tuple[Rule, str]]:
    """Build region extraction rules from language configurations."""
    rules = []
    for lang_name, lang_config in LANGUAGE_CONFIGS.items():
        for region_rule in lang_config.get_region_extraction_rules():
            # Create a query-based Rule from RegionExtractionRule
            # Use the query directly from the region rule
            rule = Rule(
                name=f"Extract {region_rule.label} regions for {lang_name}",
                languages=[lang_name],
                query=region_rule.query,
                action=RuleAction.EXTRACT_REGION,
                params={
                    "region_type": region_rule.label,
                },
            )
            rules.append((rule, rule.name))
    return rules


def build_default_rules() -> list[tuple[Rule, str]]:
    """Build default rules from language configurations."""
    rules = []
    rules.extend(build_region_extraction_rules())

    for lang_name, lang_config in LANGUAGE_CONFIGS.items():
        for rule in lang_config.get_default_rules():
            rules.append((rule, rule.name))

    return rules


def build_loose_rules() -> list[tuple[Rule, str]]:
    """Build loose rules from language configurations."""
    rules = []
    rules.extend(build_region_extraction_rules())

    for lang_name, lang_config in LANGUAGE_CONFIGS.items():
        # Respect the order defined in the config (loose rules include default)
        for rule in lang_config.get_loose_rules():
            rules.append((rule, rule.name))

    return rules
