"""Tests for JSX language configuration and rules."""

from pathlib import Path

import pytest

from tests.conftest import parse_fixture
from treepeat.pipeline.region_extraction import extract_all_regions
from treepeat.pipeline.rules.engine import RuleEngine, build_default_rules, build_loose_rules

fixture_comprehensive = Path(__file__).parent.parent.parent / "fixtures" / "jsx" / "comprehensive.jsx"


@pytest.mark.parametrize("rules", [
    [rule for rule, _ in build_default_rules()],
    [rule for rule, _ in build_loose_rules()]
])
def test_jsx_rules_extract(rules):
    """Test that JSX files can be processed with different rule sets."""
    parsed = parse_fixture(fixture_comprehensive, "jsx")
    engine = RuleEngine(rules)
    regions = extract_all_regions([parsed], engine)

    assert len(regions) > 0
    region_types = {r.region.region_type for r in regions}
    assert "jsx_expression" in region_types
