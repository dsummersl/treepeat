"""Tests for rule parser."""

import pytest

from tssim.pipeline.rules import (
    Rule,
    RuleOperation,
    RuleParseError,
    parse_rule,
    parse_rules,
)


class TestParseRule:
    """Tests for parse_rule function."""

    def test_parse_simple_skip_rule(self):
        """Test parsing a simple skip rule."""
        rule = parse_rule("python:skip:nodes=import_statement")
        assert rule.language == "python"
        assert rule.operation == RuleOperation.SKIP
        assert rule.node_patterns == ["import_statement"]
        assert rule.params == {}

    def test_parse_skip_rule_multiple_nodes(self):
        """Test parsing skip rule with multiple nodes."""
        rule = parse_rule("python:skip:nodes=import_statement|import_from_statement")
        assert rule.language == "python"
        assert rule.operation == RuleOperation.SKIP
        assert rule.node_patterns == ["import_statement", "import_from_statement"]
        assert rule.params == {}

    def test_parse_replace_value_rule(self):
        """Test parsing replace_value rule."""
        rule = parse_rule("python:replace_value:nodes=string|integer|float,value=<LIT>")
        assert rule.language == "python"
        assert rule.operation == RuleOperation.REPLACE_VALUE
        assert rule.node_patterns == ["string", "integer", "float"]
        assert rule.params == {"value": "<LIT>"}

    def test_parse_anonymize_identifiers_rule(self):
        """Test parsing anonymize_identifiers rule."""
        rule = parse_rule("*:anonymize_identifiers:nodes=identifier,scheme=flat,prefix=VAR")
        assert rule.language == "*"
        assert rule.operation == RuleOperation.ANONYMIZE_IDENTIFIERS
        assert rule.node_patterns == ["identifier"]
        assert rule.params == {"scheme": "flat", "prefix": "VAR"}

    def test_parse_canonicalize_types_rule(self):
        """Test parsing canonicalize_types rule."""
        rule = parse_rule("python:canonicalize_types:nodes=type_identifier|qualified_type,token=<TYPE>")
        assert rule.language == "python"
        assert rule.operation == RuleOperation.CANONICALIZE_TYPES
        assert rule.node_patterns == ["type_identifier", "qualified_type"]
        assert rule.params == {"token": "<TYPE>"}

    def test_parse_rule_with_wildcard(self):
        """Test parsing rule with wildcard node pattern."""
        rule = parse_rule("*:skip:nodes=comment*")
        assert rule.language == "*"
        assert rule.operation == RuleOperation.SKIP
        assert rule.node_patterns == ["comment*"]
        assert rule.params == {}

    def test_parse_rule_with_whitespace(self):
        """Test parsing rule with extra whitespace."""
        rule = parse_rule("  python : skip : nodes = import_statement  ")
        assert rule.language == "python"
        assert rule.operation == RuleOperation.SKIP
        assert rule.node_patterns == ["import_statement"]

    def test_parse_empty_rule(self):
        """Test that empty rule raises error."""
        with pytest.raises(RuleParseError, match="Empty rule string"):
            parse_rule("")

    def test_parse_invalid_format(self):
        """Test that invalid format raises error."""
        with pytest.raises(RuleParseError, match="Invalid rule format"):
            parse_rule("python:skip")

    def test_parse_invalid_operation(self):
        """Test that invalid operation raises error."""
        with pytest.raises(RuleParseError, match="Invalid operation"):
            parse_rule("python:invalid_op:nodes=import_statement")

    def test_parse_missing_nodes_parameter(self):
        """Test that missing nodes parameter raises error."""
        with pytest.raises(RuleParseError, match="Missing required 'nodes' parameter"):
            parse_rule("python:skip:value=test")

    def test_parse_invalid_parameter_format(self):
        """Test that invalid parameter format raises error."""
        with pytest.raises(RuleParseError, match="Invalid parameter format"):
            parse_rule("python:skip:nodes=import_statement,invalid")


class TestParseRules:
    """Tests for parse_rules function (comma-separated)."""

    def test_parse_multiple_rules(self):
        """Test parsing multiple comma-separated rules."""
        rules_str = (
            "python:skip:nodes=import_statement,"
            "python:replace_value:nodes=string,value=<LIT>"
        )
        rules = parse_rules(rules_str)
        assert len(rules) == 2
        assert rules[0].operation == RuleOperation.SKIP
        assert rules[1].operation == RuleOperation.REPLACE_VALUE

    def test_parse_empty_string(self):
        """Test that empty string returns empty list."""
        rules = parse_rules("")
        assert rules == []

    def test_parse_single_rule(self):
        """Test parsing a single rule."""
        rules = parse_rules("python:skip:nodes=import_statement")
        assert len(rules) == 1
        assert rules[0].operation == RuleOperation.SKIP


class TestRuleMatching:
    """Tests for rule matching methods."""

    def test_matches_language_exact(self):
        """Test exact language matching."""
        rule = parse_rule("python:skip:nodes=import_statement")
        assert rule.matches_language("python")
        assert not rule.matches_language("javascript")

    def test_matches_language_wildcard(self):
        """Test wildcard language matching."""
        rule = parse_rule("*:skip:nodes=import_statement")
        assert rule.matches_language("python")
        assert rule.matches_language("javascript")
        assert rule.matches_language("any_language")

    def test_matches_node_type_exact(self):
        """Test exact node type matching."""
        rule = parse_rule("python:skip:nodes=import_statement")
        assert rule.matches_node_type("import_statement")
        assert not rule.matches_node_type("function_definition")

    def test_matches_node_type_multiple(self):
        """Test matching multiple node types."""
        rule = parse_rule("python:skip:nodes=import_statement|import_from_statement")
        assert rule.matches_node_type("import_statement")
        assert rule.matches_node_type("import_from_statement")
        assert not rule.matches_node_type("function_definition")

    def test_matches_node_type_wildcard(self):
        """Test wildcard node type matching."""
        rule = parse_rule("*:skip:nodes=comment*")
        assert rule.matches_node_type("comment")
        assert rule.matches_node_type("comment_line")
        assert rule.matches_node_type("comment_block")
        assert not rule.matches_node_type("string")
