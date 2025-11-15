"""Rule engine for applying tree-sitter query-based rules to syntax tree nodes."""

from typing import Any, Callable, Optional

from tree_sitter import Node, Query, QueryCursor
from tree_sitter_language_pack import get_language

from .models import Rule, RuleAction, SkipNodeException
from ..languages import LANGUAGE_CONFIGS


class RuleEngine:
    """Engine for applying tree-sitter query-based rules to syntax tree nodes."""

    def __init__(self, rules: list[Rule]):
        """Initialize the rule engine with a list of rules."""
        self.rules = rules
        self._identifier_counters: dict[str, int] = {}
        self._action_handlers = self._build_action_handlers()
        self._compiled_queries: dict[tuple[str, str], Query] = {}
        self._query_matches_cache: dict[int, list[dict[str, Any]]] = {}

    def _build_action_handlers(
        self,
    ) -> dict[
        RuleAction,
        Callable[
            [Rule, str, str, Optional[str], Optional[str]],
            tuple[Optional[str], Optional[str]],
        ],
    ]:
        """Build mapping of actions to handler functions."""
        return {
            RuleAction.REMOVE: self._handle_remove,
            RuleAction.RENAME: self._handle_rename,
            RuleAction.REPLACE_VALUE: self._handle_replace_value,
            RuleAction.ANONYMIZE: self._handle_anonymize,
            RuleAction.CANONICALIZE: self._handle_canonicalize,
            RuleAction.EXTRACT_REGION: self._handle_extract_region,
        }

    def _get_anonymized_identifier(self, prefix: str) -> str:
        """Generate an anonymized identifier."""
        if prefix not in self._identifier_counters:
            self._identifier_counters[prefix] = 0
        self._identifier_counters[prefix] += 1
        return f"{prefix}_{self._identifier_counters[prefix]}"

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
                all_matches[node.id].append({
                    'query': query_str,
                    'match_id': match_id,
                    'captures': captures_dict,
                    'capture_name': capture_name
                })

    def _get_all_matches(
        self, root_node: Node, query_strings: list[str], language: str
    ) -> dict[int, list[dict[str, Any]]]:
        """Execute multiple queries and collect all matches indexed by node ID.

        Args:
            root_node: Root node to query
            query_strings: List of query strings to execute
            language: Language for the queries

        Returns:
            Dictionary mapping node.id to list of match dictionaries
        """
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
                if match_info['query'] == rule.query:
                    return self._get_query_match_result(rule)

        return None

    def _handle_remove(
        self, rule: Rule, node_type: str, language: str, name: Optional[str], value: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Handle REMOVE action - skip/remove matched nodes."""
        raise SkipNodeException(
            f"Node type '{node_type}' matched remove rule for language '{language}'"
        )

    def _handle_rename(
        self, rule: Rule, node_type: str, language: str, name: Optional[str], value: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Handle RENAME action - rename matched nodes."""
        return rule.params.get("token", "<NODE>"), value

    def _handle_replace_value(
        self, rule: Rule, node_type: str, language: str, name: Optional[str], value: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Handle REPLACE_VALUE action - replace node values."""
        return name, rule.params.get("value", "<LIT>")

    def _handle_anonymize(
        self, rule: Rule, node_type: str, language: str, name: Optional[str], value: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Handle ANONYMIZE action - anonymize identifiers."""
        prefix = rule.params.get("prefix", "VAR")
        return name, self._get_anonymized_identifier(prefix)

    def _handle_canonicalize(
        self, rule: Rule, node_type: str, language: str, name: Optional[str], value: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Handle CANONICALIZE action - canonicalize types."""
        return rule.params.get("token", "<TYPE>"), value

    def _handle_extract_region(
        self, rule: Rule, node_type: str, language: str, name: Optional[str], value: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Handle EXTRACT_REGION action - mark regions for extraction (no-op for normalization)."""
        return name, value

    def _apply_action(
        self, rule: Rule, node_type: str, language: str, name: Optional[str], value: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Apply a rule action."""
        if not rule.action:
            return name, value

        handler = self._action_handlers.get(rule.action)
        if handler:
            return handler(rule, node_type, language, name, value)

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
            return self._apply_action(rule, node_type, language, name, value)
        return name, value

    def apply_rules(
        self,
        node: Node,
        language: str,
        node_name: Optional[str] = None,
        root_node: Optional[Node] = None,
    ) -> tuple[Optional[str], Optional[str]]:
        """Apply all matching rules to a node.

        Args:
            node: The node to apply rules to
            language: The language of the source code
            node_name: Optional override for the node type name
            root_node: Optional root node for query execution

        Returns:
            Tuple of (name, value) - either may be None
        """
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
        """Reset the identifier counter and query cache."""
        self._identifier_counters.clear()
        self._query_matches_cache.clear()

    def precompute_queries(self, root_node: Node, language: str) -> None:
        """Pre-execute all queries for a root node to populate the cache.

        This executes all queries once and indexes matches by node ID for O(1) lookup.
        Call this once per region after reset_identifiers().
        """
        # Collect all query strings for this language
        query_strings = [
            rule.query for rule in self.rules if rule.matches_language(language)
        ]

        # Execute all queries once and cache results indexed by node.id
        self._query_matches_cache = self._get_all_matches(
            root_node, query_strings, language
        )

    def _extract_region_rule_params(self, rule: Rule) -> Optional[tuple[list[str], str]]:
        """Extract region params from a rule if it's a region extraction rule."""
        if "node_types" not in rule.params or "region_type" not in rule.params:
            return None
        node_types = rule.params["node_types"].split("|")
        region_type = rule.params["region_type"]
        return (node_types, region_type)

    def get_region_extraction_rules(self, language: str) -> list[tuple[list[str], str]]:
        """Get region extraction rules for a language.

        Returns list of tuples: (node_types, region_type)
        """
        region_rules = []
        for rule in self.rules:
            if rule.action == RuleAction.EXTRACT_REGION and rule.matches_language(language):
                params = self._extract_region_rule_params(rule)
                if params:
                    region_rules.append(params)
        return region_rules


def build_region_extraction_rules() -> list[tuple[Rule, str]]:
    """Build region extraction rules from language configurations."""
    rules = []
    for lang_name, lang_config in LANGUAGE_CONFIGS.items():
        for region_rule in lang_config.get_region_extraction_rules():
            # Create a query-based Rule from RegionExtractionRule
            # Use alternation to match any of the node types
            node_patterns = " ".join(f"({node_type})" for node_type in region_rule.node_types)
            query = f"[{node_patterns}] @region"

            rule = Rule(
                name=f"Extract {region_rule.region_type} regions for {lang_name}",
                languages=[lang_name],
                query=query,
                action=RuleAction.EXTRACT_REGION,
                params={
                    "region_type": region_rule.region_type,
                    "node_types": "|".join(region_rule.node_types),  # Store for extraction
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
    """Build loose rules (default + loose) from language configurations."""
    rules = list(build_default_rules())

    for lang_name, lang_config in LANGUAGE_CONFIGS.items():
        # Get loose rules which include default rules
        loose_rules = lang_config.get_loose_rules()
        # Filter out rules that are already in default
        default_rules = lang_config.get_default_rules()
        for rule in loose_rules:
            if rule not in default_rules:
                rules.append((rule, rule.name))

    return rules
