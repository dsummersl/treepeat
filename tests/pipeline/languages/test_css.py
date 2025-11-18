"""Tests for CSS language configuration and rules."""

from pathlib import Path

import pytest

from tests.conftest import parse_fixture
from treepeat.pipeline.languages.css import CSSConfig
from treepeat.pipeline.region_extraction import extract_all_regions
from treepeat.pipeline.rules.engine import RuleEngine, build_default_rules, build_loose_rules


# Fixture path
fixture_comprehensive = Path(__file__).parent.parent.parent / "fixtures" / "css" / "comprehensive.css"


@pytest.mark.parametrize("rules,expected_min_regions", [
    ([], 1),  # No rules, entire file as one region
    ([rule for rule, _ in build_default_rules()], 1),  # CSS no longer has region extraction rules
    ([rule for rule, _ in build_loose_rules()], 1)  # Same behavior with loose rules
])
def test_css_rules_extract(rules, expected_min_regions):
    """Test that CSS files can be processed with different rule sets."""
    parsed = parse_fixture(fixture_comprehensive, "css")
    engine = RuleEngine(rules)
    regions = extract_all_regions([parsed], engine)

    # CSS region extraction rules were removed - entire file is treated as one region
    # Line matching with sliding windows will be used to find similar sections
    assert len(regions) >= expected_min_regions


def test_language_name():
    """Test that CSS config returns correct language name."""
    assert CSSConfig().get_language_name() == "css"
