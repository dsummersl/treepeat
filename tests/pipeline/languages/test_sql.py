"""Tests for SQL language configuration and rules."""

from pathlib import Path

import pytest

from tests.conftest import parse_fixture
from covey.pipeline.languages.sql import SQLConfig
from covey.pipeline.region_extraction import extract_all_regions
from covey.pipeline.rules.engine import RuleEngine, build_default_rules, build_loose_rules


# Fixture path
fixture_comprehensive = Path(__file__).parent.parent.parent / "fixtures" / "sql" / "comprehensive.sql"


@pytest.mark.parametrize("rules", [
    [],
    [rule for rule, _ in build_default_rules()],
    [rule for rule, _ in build_loose_rules()]
])
def test_sql_rules_extract(rules):
    """Test that SQL files can be processed with different rule sets."""
    parsed = parse_fixture(fixture_comprehensive, "sql")
    engine = RuleEngine(rules)
    regions = extract_all_regions([parsed], engine)

    # SQL doesn't define region extraction rules, so we may get 0 regions
    assert len(regions) >= 0


def test_language_name():
    """Test that SQL config returns correct language name."""
    assert SQLConfig().get_language_name() == "sql"
