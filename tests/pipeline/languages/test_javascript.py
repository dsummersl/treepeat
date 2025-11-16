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
    """
    parsed = parse_javascript_fixture(fixture_comprehensive)
    rules = [rule for rule, _ in build_default_rules()]
    engine = RuleEngine(rules)

    # Extract regions with include_sections=False to get all functions/methods/classes
    regions = extract_all_regions([parsed], engine, include_sections=False)

    # Should successfully extract regions without errors
    assert len(regions) > 0


def test_javascript_loose_rules():
    """Test that JavaScript files can be processed with loose rules.

    Loose rules include all default rules plus:
    - Replace literal values (string, number, template_string)
    - Replace collections (array, object)
    - Replace expressions (binary, unary, update, assignment, ternary)
    """
    parsed = parse_javascript_fixture(fixture_comprehensive)
    rules = [rule for rule, _ in build_loose_rules()]
    engine = RuleEngine(rules)

    # Extract regions with include_sections=False to get all functions/methods/classes
    regions = extract_all_regions([parsed], engine, include_sections=False)

    # Should successfully extract regions without errors
    assert len(regions) > 0
