"""Tests for rule engine."""

import pytest
from tree_sitter import Node
from tree_sitter_language_pack import get_parser

from tssim.pipeline.rules import (
    RuleEngine,
    SkipNodeException,
    build_default_rules,
    parse_rule,
)


@pytest.fixture
def parser():
    """Get a Python parser."""
    return get_parser("python")


def parse_source(source: str, parser) -> tuple[Node, bytes]:
    """Helper to parse source code."""
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    return tree.root_node, source_bytes


def find_node_by_type(node: Node, node_type: str) -> Node | None:
    """Find first node of given type in tree."""
    if node.type == node_type:
        return node
    for child in node.children:
        result = find_node_by_type(child, node_type)
        if result:
            return result
    return None


class TestRuleEngine:
    """Tests for RuleEngine."""

    def test_skip_rule(self, parser):
        """Test that skip rule raises SkipNodeException."""
        rule = parse_rule("python:skip:nodes=import_statement")
        engine = RuleEngine([rule])

        root, source = parse_source("import os\n", parser)
        import_node = find_node_by_type(root, "import_statement")

        assert import_node is not None
        with pytest.raises(SkipNodeException):
            engine.apply_rules(import_node, "python")

    def test_skip_rule_multiple_nodes(self, parser):
        """Test skip rule with multiple node types."""
        rule = parse_rule("python:skip:nodes=import_statement|import_from_statement")
        engine = RuleEngine([rule])

        root, source = parse_source("from os import path\n", parser)
        import_node = find_node_by_type(root, "import_from_statement")

        assert import_node is not None
        with pytest.raises(SkipNodeException):
            engine.apply_rules(import_node, "python")

    def test_no_skip_for_non_matching_node(self, parser):
        """Test that non-matching nodes are not skipped."""
        rule = parse_rule("python:skip:nodes=import_statement")
        engine = RuleEngine([rule])

        root, source = parse_source("def foo(): pass\n", parser)
        func_node = find_node_by_type(root, "function_definition")

        assert func_node is not None
        name, value = engine.apply_rules(func_node, "python")
        assert name is None
        assert value is None

    def test_no_skip_for_non_matching_language(self, parser):
        """Test that rules don't apply to non-matching languages."""
        rule = parse_rule("python:skip:nodes=import_statement")
        engine = RuleEngine([rule])

        root, source = parse_source("import os\n", parser)
        import_node = find_node_by_type(root, "import_statement")

        assert import_node is not None
        name, value = engine.apply_rules(import_node, "javascript")
        assert name is None
        assert value is None

    def test_replace_value_rule(self, parser):
        """Test replace_value rule."""
        rule = parse_rule("python:replace_value:nodes=string,value=<LIT>")
        engine = RuleEngine([rule])

        root, source = parse_source("x = 'hello'\n", parser)
        string_node = find_node_by_type(root, "string")

        assert string_node is not None
        name, value = engine.apply_rules(string_node, "python")
        assert name is None
        assert value == "<LIT>"

    def test_replace_name_rule(self, parser):
        """Test replace_name rule."""
        rule = parse_rule("python:replace_name:nodes=function_definition,token=<FUNC>")
        engine = RuleEngine([rule])

        root, source = parse_source("def foo(): pass\n", parser)
        func_node = find_node_by_type(root, "function_definition")

        assert func_node is not None
        name, value = engine.apply_rules(func_node, "python")
        assert name == "<FUNC>"
        assert value is None

    def test_anonymize_identifiers_rule(self, parser):
        """Test anonymize_identifiers rule."""
        rule = parse_rule("*:anonymize_identifiers:nodes=identifier,scheme=flat,prefix=VAR")
        engine = RuleEngine([rule])

        root, source = parse_source("x = 5\ny = 10\n", parser)

        # Find all identifier nodes
        identifiers = []

        def find_identifiers(node):
            if node.type == "identifier":
                identifiers.append(node)
            for child in node.children:
                find_identifiers(child)

        find_identifiers(root)

        # Apply rules to each identifier
        results = [engine.apply_rules(node, "python") for node in identifiers]

        # Check that identifiers are anonymized with incrementing counters
        assert results[0][1] == "VAR_1"
        assert results[1][1] == "VAR_2"

    def test_canonicalize_types_rule(self, parser):
        """Test canonicalize_types rule."""
        rule = parse_rule("python:canonicalize_types:nodes=type,token=<TYPE>")
        engine = RuleEngine([rule])

        root, source = parse_source("x: int = 5\n", parser)
        type_node = find_node_by_type(root, "type")

        if type_node is not None:  # Type annotations might not be present in all Python versions
            name, value = engine.apply_rules(type_node, "python")
            assert name == "<TYPE>"

    def test_wildcard_language_matching(self, parser):
        """Test that * matches all languages."""
        rule = parse_rule("*:skip:nodes=import_statement")
        engine = RuleEngine([rule])

        root, source = parse_source("import os\n", parser)
        import_node = find_node_by_type(root, "import_statement")

        assert import_node is not None
        with pytest.raises(SkipNodeException):
            engine.apply_rules(import_node, "python")
        with pytest.raises(SkipNodeException):
            engine.apply_rules(import_node, "javascript")

    def test_last_rule_wins(self, parser):
        """Test that last matching rule wins."""
        rule1 = parse_rule("python:replace_value:nodes=string,value=<LIT1>")
        rule2 = parse_rule("python:replace_value:nodes=string,value=<LIT2>")
        engine = RuleEngine([rule1, rule2])

        root, source = parse_source("x = 'hello'\n", parser)
        string_node = find_node_by_type(root, "string")

        assert string_node is not None
        name, value = engine.apply_rules(string_node, "python")
        assert value == "<LIT2>"  # Last rule wins

    def test_reset_identifiers(self, parser):
        """Test that reset_identifiers clears counters."""
        rule = parse_rule("*:anonymize_identifiers:nodes=identifier,scheme=flat,prefix=VAR")
        engine = RuleEngine([rule])

        root, source = parse_source("x = 5\n", parser)
        identifier_node = find_node_by_type(root, "identifier")

        assert identifier_node is not None
        _, value1 = engine.apply_rules(identifier_node, "python")
        assert value1 == "VAR_1"

        engine.reset_identifiers()

        _, value2 = engine.apply_rules(identifier_node, "python")
        assert value2 == "VAR_1"  # Counter resets


class TestBuildDefaultRules:
    """Tests for build_default_rules function."""

    def test_default_rules_exist(self):
        """Test that default rules are created."""
        rules = build_default_rules()
        assert len(rules) > 0

    def test_default_python_import_skip(self, parser):
        """Test that default rules skip Python imports."""
        rules = build_default_rules()
        engine = RuleEngine(rules)

        root, source = parse_source("import os\n", parser)
        import_node = find_node_by_type(root, "import_statement")

        assert import_node is not None
        with pytest.raises(SkipNodeException):
            engine.apply_rules(import_node, "python")
