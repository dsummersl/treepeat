"""Tests for JavaScript language configuration and rules."""

from pathlib import Path

import pytest
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


@pytest.mark.parametrize("rules", [
    [],
    [rule for rule, _ in build_default_rules()],
    [rule for rule, _ in build_loose_rules()]
])
def test_javascript_rules_extract(rules):
    """Test that JavaScript files can be processed with different rule sets."""
    parsed = parse_javascript_fixture(fixture_comprehensive)
    engine = RuleEngine(rules)
    regions = extract_all_regions([parsed], engine, include_sections=False)

    assert len(regions) > 0
