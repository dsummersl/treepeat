"""Rule engine for applying rules to syntax tree nodes."""

from typing import Callable, Optional

from tree_sitter import Node, Query, QueryCursor
from tree_sitter_language_pack import get_language

from .models import Rule, RuleAction, RuleOperation, SkipNodeException
from .parser import parse_rule
from ..languages import LANGUAGE_CONFIGS



class RuleEngine:
    """Engine for applying rules to syntax tree nodes."""

    def __init__(self, rules: list[Rule]):
        """Initialize the rule engine with a list of rules."""
        self.rules = rules
        self._identifier_counters: dict[str, int] = {}
        self._operation_handlers = self._build_operation_handlers()
        self._action_handlers = self._build_action_handlers()
        self._compiled_queries: dict[tuple[str, str], Query] = {}  # (language, query_str) -> Query
        # Cache using (start_byte, end_byte) as key instead of Python object id
        self._query_node_cache: dict[tuple[int, int], set[str]] = {}  # (start, end) -> set of matched rules

    def _build_operation_handlers(
        self,
    ) -> dict[
        RuleOperation,
        Callable[
            [Rule, str, str, Optional[str], Optional[str]],
            tuple[Optional[str], Optional[str]],
        ],
    ]:
        """Build mapping of operations to handler functions."""
        return {
            RuleOperation.SKIP: self._handle_skip,
            RuleOperation.REPLACE_NAME: self._handle_replace_name,
            RuleOperation.REPLACE_VALUE: self._handle_replace_value,
            RuleOperation.ANONYMIZE_IDENTIFIERS: self._handle_anonymize,
            RuleOperation.CANONICALIZE_TYPES: self._handle_canonicalize,
            RuleOperation.EXTRACT_REGION: self._handle_extract_region,
        }

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
            RuleAction.REMOVE: self._handle_skip,
            RuleAction.RENAME: self._handle_replace_name,
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

    def _is_node_in_query_cache(
        self, node_key: tuple[int, int], cache_key: str
    ) -> bool:
        """Check if a node is in the query cache."""
        return (
            node_key in self._query_node_cache
            and cache_key in self._query_node_cache[node_key]
        )

    def _cache_query_matches(
        self, cache_key: str, root_node: Node, query_str: str, language: str
    ) -> None:
        """Execute query and cache all matched nodes."""
        query = self._get_compiled_query(language, query_str)
        cursor = QueryCursor(query)
        matches = cursor.matches(root_node)

        for pattern_index, captures_dict in matches:
            for capture_name, nodes in captures_dict.items():
                for matched_node in nodes:
                    matched_key = (matched_node.start_byte, matched_node.end_byte)
                    if matched_key not in self._query_node_cache:
                        self._query_node_cache[matched_key] = set()
                    self._query_node_cache[matched_key].add(cache_key)

    def _get_query_match_result(self, rule: Rule) -> str:
        """Get the result to return for a query match."""
        return rule.target or "match"

    def _check_node_matches_query(
        self, node: Node, rule: Rule, language: str, root_node: Node
    ) -> Optional[str]:
        """Check if a node matches a query-based rule.

        Returns the capture name if matched, None otherwise.
        """
        if not rule.query:
            return None

        node_key = (node.start_byte, node.end_byte)
        cache_key = f"{language}:{rule.query}"

        # Check cache first, or execute query and cache results
        if not self._is_node_in_query_cache(node_key, cache_key):
            self._cache_query_matches(cache_key, root_node, rule.query, language)

        # Return match result if found
        if self._is_node_in_query_cache(node_key, cache_key):
            return self._get_query_match_result(rule)

        return None

    def _handle_skip(
        self, rule: Rule, node_type: str, language: str, name: Optional[str], value: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Handle SKIP operation."""
        raise SkipNodeException(
            f"Node type '{node_type}' matched skip rule for language '{language}'"
        )

    def _handle_replace_name(
        self, rule: Rule, node_type: str, language: str, name: Optional[str], value: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Handle REPLACE_NAME operation."""
        return rule.params.get("token", "<NODE>"), value

    def _handle_replace_value(
        self, rule: Rule, node_type: str, language: str, name: Optional[str], value: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Handle REPLACE_VALUE operation."""
        return name, rule.params.get("value", "<LIT>")

    def _handle_anonymize(
        self, rule: Rule, node_type: str, language: str, name: Optional[str], value: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Handle ANONYMIZE_IDENTIFIERS operation."""
        prefix = rule.params.get("prefix", "VAR")
        return name, self._get_anonymized_identifier(prefix)

    def _handle_canonicalize(
        self, rule: Rule, node_type: str, language: str, name: Optional[str], value: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Handle CANONICALIZE_TYPES operation."""
        return rule.params.get("token", "<TYPE>"), value

    def _handle_extract_region(
        self, rule: Rule, node_type: str, language: str, name: Optional[str], value: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Handle EXTRACT_REGION operation (no-op for normalization, used for region extraction)."""
        return name, value

    def _apply_single_rule(
        self, rule: Rule, node_type: str, language: str, name: Optional[str], value: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Apply a single matching rule and return updated name and value."""
        if rule.operation is None:
            return name, value
        handler = self._operation_handlers[rule.operation]
        return handler(rule, node_type, language, name, value)

    def _apply_query_action(
        self, rule: Rule, node_type: str, language: str, name: Optional[str], value: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Apply a query-based rule action."""
        if not rule.action:
            return name, value

        handler = self._action_handlers.get(rule.action)
        if handler:
            return handler(rule, node_type, language, name, value)

        return name, value

    def _apply_query_rule(
        self,
        rule: Rule,
        node: Node,
        node_type: str,
        language: str,
        root_node: Node,
        name: Optional[str],
        value: Optional[str],
    ) -> tuple[Optional[str], Optional[str]]:
        """Apply a query-based rule if it matches."""
        if not rule.matches_language(language):
            return name, value

        capture_name = self._check_node_matches_query(node, rule, language, root_node)
        if capture_name:
            return self._apply_query_action(rule, node_type, language, name, value)

        return name, value

    def _apply_legacy_rule(
        self,
        rule: Rule,
        node_type: str,
        language: str,
        name: Optional[str],
        value: Optional[str],
    ) -> tuple[Optional[str], Optional[str]]:
        """Apply a legacy rule if it matches."""
        if not (rule.matches_language(language) and rule.matches_node_type(node_type)):
            return name, value

        if rule.operation:
            return self._apply_single_rule(rule, node_type, language, name, value)

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
            root_node: Optional root node for query-based rules

        Returns:
            Tuple of (name, value) - either may be None
        """
        node_type = node_name or node.type
        name = None
        value = None
        root_node = root_node or node

        for rule in self.rules:
            if rule.is_query_based():
                name, value = self._apply_query_rule(
                    rule, node, node_type, language, root_node, name, value
                )
            else:
                name, value = self._apply_legacy_rule(rule, node_type, language, name, value)

        return name, value

    def reset_identifiers(self) -> None:
        """Reset the identifier counter."""
        self._identifier_counters.clear()

    def get_region_extraction_rules(self, language: str) -> list[tuple[list[str], str]]:
        """Get region extraction rules for a language.

        Returns list of tuples: (node_types, region_type)
        """
        region_rules = []
        for rule in self.rules:
            if rule.operation == RuleOperation.EXTRACT_REGION and rule.matches_language(language):
                if rule.node_patterns is None:
                    continue
                region_type = rule.params.get("region_type", "unknown")
                region_rules.append((rule.node_patterns, region_type))
        return region_rules


def build_region_extraction_rules() -> list[tuple[Rule, str]]:
    """Build region extraction rules from language configurations.

    These rules are always included regardless of ruleset selection.
    """
    rules = []
    for lang_name, lang_config in LANGUAGE_CONFIGS.items():
        for region_rule in lang_config.get_region_extraction_rules():
            # Create legacy-style rule for region extraction
            node_types = "|".join(region_rule.node_types)
            rule_str = f"{lang_name}:extract_region:nodes={node_types},region_type={region_rule.region_type}"
            rules.append((parse_rule(rule_str), f"Extract {region_rule.region_type} from {lang_name}"))
    return rules


def build_default_rules() -> list[tuple[Rule, str]]:
    """Build default rules from language configurations."""
    rules = []

    # Always include region extraction rules
    rules.extend(build_region_extraction_rules())

    # Add default normalization rules
    for lang_name, lang_config in LANGUAGE_CONFIGS.items():
        for rule in lang_config.get_default_rules():
            rules.append((rule, rule.name))

    return rules


def build_loose_rules() -> list[tuple[Rule, str]]:
    """Build loose rules (default + loose) from language configurations."""
    rules = list(build_default_rules())

    # Add loose rules for each language
    for lang_name, lang_config in LANGUAGE_CONFIGS.items():
        for rule in lang_config.get_loose_rules():
            # Skip rules already added in default (since loose extends default)
            if any(existing_rule.name == rule.name for existing_rule, _ in rules):
                continue
            rules.append((rule, rule.name))

    return rules


