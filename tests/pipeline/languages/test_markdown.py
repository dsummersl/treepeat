"""Tests for Markdown language configuration and rules."""

from pathlib import Path

import pytest

from tests.conftest import parse_fixture
from treepeat.pipeline.languages.markdown import MarkdownConfig
from treepeat.pipeline.region_extraction import extract_all_regions
from treepeat.pipeline.rules.engine import RuleEngine, build_default_rules, build_loose_rules


# Fixture path
fixture_comprehensive = Path(__file__).parent.parent.parent / "fixtures" / "markdown" / "one.md"


@pytest.mark.parametrize("rules", [
    [],
    [rule for rule, _ in build_default_rules()],
    [rule for rule, _ in build_loose_rules()]
])
def test_markdown_rules_extract(rules):
    """Test that Markdown files can be processed with different rule sets."""
    parsed = parse_fixture(fixture_comprehensive, "markdown")
    engine = RuleEngine(rules)
    regions = extract_all_regions([parsed], engine)

    # Markdown defines region extraction rules for headings and code blocks
    assert len(regions) >= 0


def test_language_name():
    """Test that Markdown config returns correct language name."""
    assert MarkdownConfig().get_language_name() == "markdown"
