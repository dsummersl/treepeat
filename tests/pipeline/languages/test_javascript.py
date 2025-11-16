"""Tests for JavaScript language configuration and rules."""

from pathlib import Path
from tree_sitter_language_pack import get_parser

from tssim.models.ast import ParsedFile
from tssim.pipeline.region_extraction import extract_all_regions
from tssim.pipeline.rules.engine import RuleEngine, build_default_rules, build_loose_rules


# Fixture path
fixture_comprehensive = Path(__file__).parent.parent.parent / "fixtures" / "javascript" / "comprehensive.js"


def load_fixture(path: Path) -> bytes:
    """Load a fixture file as bytes."""
    with open(path, "rb") as f:
        return f.read()


def parse_javascript_fixture(path: Path) -> ParsedFile:
    """Parse a JavaScript fixture file."""
    parser = get_parser("javascript")
    fixture = load_fixture(path)
    tree = parser.parse(fixture)
    return ParsedFile(
        path=path,
        language="javascript",
        tree=tree,
        source=fixture,
    )


def test_javascript_default_rules():
    """Test that JavaScript files can be processed with default rules.

    Default rules include:
    - Skip import/export statements
    - Skip comments
    - Anonymize identifiers

    Region extraction should find:
    - function_declaration (regularFunction)
    - function_expression (functionExpression)
    - arrow_function (arrowFunction)
    - class_declaration (Calculator)
    - method_definition (constructor, add, subtract, reset)
    """
    parsed = parse_javascript_fixture(fixture_comprehensive)
    rules = [rule for rule, _ in build_default_rules()]
    engine = RuleEngine(rules)

    # Extract regions with include_sections=False to get all functions/methods/classes
    regions = extract_all_regions([parsed], engine, include_sections=False)

    # Should successfully extract regions without errors
    assert len(regions) > 0

    # Get region names and types
    region_names = [r.region.region_name for r in regions]
    region_types = [r.region.region_type for r in regions]

    # Should find the function declaration
    assert "regularFunction" in region_names

    # Should find the function expression (will be named "anonymous" if no name)
    # Note: function expressions assigned to const will have the variable name
    assert any("functionExpression" in name or "anonymous" in name for name in region_names)

    # Should find the arrow function
    assert any("arrowFunction" in name or "anonymous" in name for name in region_names)

    # Should find the class
    assert "Calculator" in region_names

    # Should find the methods
    assert "constructor" in region_names
    assert "add" in region_names
    assert "subtract" in region_names
    assert "reset" in region_names

    # Verify region types
    assert "function" in region_types  # For function declarations and expressions
    assert "class" in region_types  # For class declarations
    assert "method" in region_types  # For method definitions

    # Verify that we can extract source code from regions without errors
    for region in regions:
        source = parsed.source[region.node.start_byte : region.node.end_byte].decode("utf-8")
        assert len(source) > 0


def test_javascript_loose_rules():
    """Test that JavaScript files can be processed with loose rules.

    Loose rules include all default rules plus:
    - Replace literal values (string, number, template_string)
    - Replace collections (array, object)
    - Replace expressions (binary, unary, update, assignment, ternary)

    This test verifies that the additional normalization rules don't break
    the region extraction and processing.
    """
    parsed = parse_javascript_fixture(fixture_comprehensive)
    rules = [rule for rule, _ in build_loose_rules()]
    engine = RuleEngine(rules)

    # Extract regions with include_sections=False to get all functions/methods/classes
    regions = extract_all_regions([parsed], engine, include_sections=False)

    # Should successfully extract regions without errors
    assert len(regions) > 0

    # Get region names and types
    region_names = [r.region.region_name for r in regions]
    region_types = [r.region.region_type for r in regions]

    # Same basic structure should be extracted as with default rules
    assert "regularFunction" in region_names
    assert "Calculator" in region_names
    assert "constructor" in region_names
    assert "add" in region_names
    assert "subtract" in region_names
    assert "reset" in region_names

    # Verify region types
    assert "function" in region_types
    assert "class" in region_types
    assert "method" in region_types

    # Verify that we can extract source code from regions without errors
    for region in regions:
        source = parsed.source[region.node.start_byte : region.node.end_byte].decode("utf-8")
        assert len(source) > 0

    # The loose rules should still extract the same regions, just with more normalization
    # applied during shingling (which happens after region extraction)
