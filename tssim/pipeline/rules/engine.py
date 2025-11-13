"""Rule engine for applying rules to syntax tree nodes."""

from typing import Optional

from tree_sitter import Node

from .models import Rule, RuleOperation, RuleResult, SkipNodeException


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

        # Apply rules in order (last wins)
        for rule in self.rules:
            if not rule.matches_language(language):
                continue

            if not rule.matches_node_type(node_type):
                continue

            # Apply the rule operation
            if rule.operation == RuleOperation.SKIP:
                raise SkipNodeException(
                    f"Node type '{node_type}' matched skip rule for language '{language}'"
                )

            elif rule.operation == RuleOperation.REPLACE_NAME:
                token = rule.params.get("token", "<NODE>")
                name = token

            elif rule.operation == RuleOperation.REPLACE_VALUE:
                token = rule.params.get("value", "<LIT>")
                value = token

            elif rule.operation == RuleOperation.ANONYMIZE_IDENTIFIERS:
                scheme = rule.params.get("scheme", "flat")
                prefix = rule.params.get("prefix", "VAR")

                if scheme == "flat":
                    # Simple counter-based anonymization
                    if prefix not in self._identifier_counters:
                        self._identifier_counters[prefix] = 0
                    self._identifier_counters[prefix] += 1
                    value = f"{prefix}_{self._identifier_counters[prefix]}"
                else:
                    # Default to simple prefix if scheme not recognized
                    value = f"{prefix}_X"

            elif rule.operation == RuleOperation.CANONICALIZE_TYPES:
                token = rule.params.get("token", "<TYPE>")
                name = token

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
