"""Tests for HTML language configuration and rules."""

from pathlib import Path

import pytest

from tests.conftest import parse_fixture
from treepeat.pipeline.languages.html import HTMLConfig
from treepeat.pipeline.region_extraction import extract_all_regions
from treepeat.pipeline.rules.engine import RuleEngine, build_default_rules, build_loose_rules


# Fixture path
fixture_comprehensive = Path(__file__).parent.parent.parent / "fixtures" / "html" / "comprehensive.html"


@pytest.mark.parametrize("rules", [
    [],
    [rule for rule, _ in build_default_rules()],
    [rule for rule, _ in build_loose_rules()]
])
def test_html_rules_extract(rules):
    """Test that HTML files can be processed with different rule sets."""
    parsed = parse_fixture(fixture_comprehensive, "html")
    engine = RuleEngine(rules)
    regions = extract_all_regions([parsed], engine)

    assert len(regions) > 0


def test_language_name():
    """Test that HTML config returns correct language name."""
    assert HTMLConfig().get_language_name() == "html"
