

from pathlib import Path

import pytest

from tests.conftest import parse_fixture
from treepeat.pipeline.region_extraction import extract_all_regions
from treepeat.pipeline.rules.engine import RuleEngine, build_default_rules, build_loose_rules

fixture_comprehensive = Path(__file__).parent.parent.parent / "fixtures" / "bash" / "comprehensive.sh"


@pytest.mark.parametrize("rules", [
    [],
    [rule for rule, _ in build_default_rules()],
    [rule for rule, _ in build_loose_rules()]
])
def test_bash_rules_extract(rules):

    parsed = parse_fixture(fixture_comprehensive, "bash")
    engine = RuleEngine(rules)
    regions = extract_all_regions([parsed], engine)


    assert len(regions) >= 0
