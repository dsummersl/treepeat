"""Tests for JavaScript language configuration and rules."""

from pathlib import Path

import pytest

from tests.conftest import parse_fixture
from treepeat.pipeline.languages.javascript import JavaScriptConfig
from treepeat.pipeline.region_extraction import extract_all_regions
from treepeat.pipeline.rules.engine import RuleEngine, build_default_rules, build_loose_rules


# Fixture path
fixture_comprehensive = Path(__file__).parent.parent.parent / "fixtures" / "javascript" / "comprehensive.js"


@pytest.mark.parametrize("rules", [
    [],
    [rule for rule, _ in build_default_rules()],
    [rule for rule, _ in build_loose_rules()]
])
def test_javascript_rules_extract(rules):
    """Test that JavaScript files can be processed with different rule sets."""
    parsed = parse_fixture(fixture_comprehensive, "javascript")
    engine = RuleEngine(rules)
    regions = extract_all_regions([parsed], engine)

    assert len(regions) > 0


def test_language_name():
    """Test that JavaScript config returns correct language name."""
    assert JavaScriptConfig().get_language_name() == "javascript"
