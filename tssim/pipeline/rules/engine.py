"""Rule engine for applying rules to syntax tree nodes."""

from typing import Callable, Optional

from tree_sitter import Node

from .models import Rule, RuleOperation, SkipNodeException


class RuleEngine:
    """
    Engine for applying rules to syntax tree nodes.

    Replaces the normalizer system with a more flexible rule-based approach.
    """

    def __init__(self, rules: list[Rule]):
        """
        Initialize the rule engine with a list of rules.

        Args:
            rules: List of rules to apply (last rule wins for conflicts)
        """
        self.rules = rules
        self._identifier_counters: dict[str, int] = {}
        self._operation_handlers = self._build_operation_handlers()

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
        }

    def _get_anonymized_identifier(self, prefix: str) -> str:
        """Generate an anonymized identifier."""
        if prefix not in self._identifier_counters:
            self._identifier_counters[prefix] = 0
        self._identifier_counters[prefix] += 1
        return f"{prefix}_{self._identifier_counters[prefix]}"

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

    def _apply_single_rule(
        self, rule: Rule, node_type: str, language: str, name: Optional[str], value: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Apply a single matching rule and return updated name and value."""
        handler = self._operation_handlers[rule.operation]
        return handler(rule, node_type, language, name, value)

    def apply_rules(
        self, node: Node, language: str, node_name: Optional[str] = None
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Apply all matching rules to a node.

        Args:
            node: The syntax tree node
            language: The language of the source code
            node_name: Optional override for node type name

        Returns:
            Tuple of (name, value) where either can be None

        Raises:
            SkipNodeException: If a skip rule matches this node
        """
        node_type = node_name or node.type
        name = None
        value = None

        for rule in self.rules:
            if rule.matches_language(language) and rule.matches_node_type(node_type):
                name, value = self._apply_single_rule(rule, node_type, language, name, value)

        return name, value

    def reset_identifiers(self) -> None:
        """Reset the identifier counter (useful between files)."""
        self._identifier_counters.clear()


def build_default_rules() -> list[Rule]:
    """
    Build the default set of rules.

    This replaces the default normalizers (e.g., PythonImportNormalizer).

    Returns:
        List of default Rule objects
    """
    from .parser import parse_rule

    # Convert PythonImportNormalizer to a rule
    default_rules = [
        parse_rule("python:skip:nodes=import_statement|import_from_statement"),
    ]

    return default_rules
