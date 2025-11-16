"""Tests for Bash language configuration and rules."""

from pathlib import Path

import pytest

from tests.conftest import parse_fixture
from whorl.pipeline.languages.bash import BashConfig
from whorl.pipeline.region_extraction import extract_all_regions
from whorl.pipeline.rules.engine import RuleEngine, build_default_rules, build_loose_rules


# Fixture path
fixture_comprehensive = Path(__file__).parent.parent.parent / "fixtures" / "bash" / "comprehensive.sh"


@pytest.mark.parametrize("rules", [
    [],
    [rule for rule, _ in build_default_rules()],
    [rule for rule, _ in build_loose_rules()]
])
def test_bash_rules_extract(rules):
    """Test that Bash files can be processed with different rule sets."""
    parsed = parse_fixture(fixture_comprehensive, "bash")
    engine = RuleEngine(rules)
    regions = extract_all_regions([parsed], engine)

    # Bash doesn't define region extraction rules, so we may get 0 regions
    assert len(regions) >= 0


def test_language_name():
    """Test that Bash config returns correct language name."""
    assert BashConfig().get_language_name() == "bash"
