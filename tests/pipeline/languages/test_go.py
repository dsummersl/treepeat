from pathlib import Path

import pytest

from tests.conftest import parse_fixture
from treepeat.pipeline.languages.go import GoConfig
from treepeat.pipeline.region_extraction import extract_all_regions
from treepeat.pipeline.rules.engine import RuleEngine, build_default_rules, build_loose_rules


# Fixture path
fixture_comprehensive = Path(__file__).parent.parent.parent / "fixtures" / "go" / "comprehensive.go"


@pytest.mark.parametrize("rules,expected_min_regions", [
    ([], 0),
    ([rule for rule, _ in build_default_rules()], 1),
    ([rule for rule, _ in build_loose_rules()], 1)
])
def test_go_rules_extract(rules, expected_min_regions):
    parsed = parse_fixture(fixture_comprehensive, "go")
    engine = RuleEngine(rules)
    regions = extract_all_regions([parsed], engine)

    assert len(regions) >= expected_min_regions


def test_language_name():
    assert GoConfig().get_language_name() == "go"
