"""Tests for Python language configuration and rules."""

from pathlib import Path

import pytest

from tests.conftest import parse_fixture
from whorl.pipeline.languages.python import PythonConfig
from whorl.pipeline.region_extraction import extract_all_regions
from whorl.pipeline.rules.engine import RuleEngine, build_default_rules, build_loose_rules


# Fixture path
fixture_comprehensive = Path(__file__).parent.parent.parent / "fixtures" / "python" / "class_with_methods.py"


@pytest.mark.parametrize("rules", [
    [],
    [rule for rule, _ in build_default_rules()],
    [rule for rule, _ in build_loose_rules()]
])
def test_python_rules_extract(rules):
    """Test that Python files can be processed with different rule sets."""
    parsed = parse_fixture(fixture_comprehensive, "python")
    engine = RuleEngine(rules)
    regions = extract_all_regions([parsed], engine)

    assert len(regions) > 0


def test_language_name():
    """Test that Python config returns correct language name."""
    assert PythonConfig().get_language_name() == "python"
