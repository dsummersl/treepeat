from pathlib import Path

import pytest

from tests.rule_helper import RuleTester
from treepeat.models.ast import ParsedFile
from treepeat.models.similarity import Region, SimilarityResult, SimilarRegionGroup
from treepeat.pipeline.parse import parse_source_code
from treepeat.pipeline.rules.engine import RuleEngine, build_default_rules

fixture_path1 = Path(__file__).parent / "fixtures" / "python" / "dataclass1.py"
fixture_path2 = Path(__file__).parent / "fixtures" / "python" / "dataclass2.py"
fixture_nested = Path(__file__).parent / "fixtures" / "python" / "nested_functions.py"
fixture_class_methods = Path(__file__).parent / "fixtures" / "python" / "class_with_methods.py"


@pytest.fixture
def rule_tester():

    return RuleTester()


def load_fixture(path: Path) -> bytes:

    with open(path, "rb") as f:
        return f.read()


def parse_fixture(path: Path, language: str) -> ParsedFile:

    fixture = load_fixture(path)
    return parse_source_code(fixture, language, path)


def assert_regions_in_same_group(result: SimilarityResult, region1: Region, region2: Region) -> SimilarRegionGroup:

    for group in result.similar_groups:
        if region1 in group.regions and region2 in group.regions:
            return group
    raise AssertionError(f"Regions ({region1}, {region2}) not found in same group ({result.similar_groups})")


def parsed_fixture(path):

    return parse_fixture(path, "python")


def default_rule_engine():

    rules = [rule for rule, _ in build_default_rules()]
    return RuleEngine(rules)
