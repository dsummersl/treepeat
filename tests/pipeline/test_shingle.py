from ..conftest import parsed_fixture, fixture_path1, fixture_path2, default_rule_engine
from treepeat.pipeline.region_extraction import extract_all_regions
from treepeat.pipeline.rules.engine import RuleEngine
from treepeat.pipeline.shingle import shingle_regions


def test_shingle_regions_basic():
    """Test shingling regions from dataclass1.py fixture."""
    parsed_dataclass1 = parsed_fixture(fixture_path1)
    engine = default_rule_engine()
    shingled_regions = shingle_regions(
        extracted_regions=extract_all_regions([parsed_dataclass1], engine),
        parsed_files=[parsed_dataclass1],
        rule_engine=RuleEngine([]),
    )

    assert len(shingled_regions) == 3
    assert [r.region.region_name for r in shingled_regions] == [
        "Model1",
        "Model2",
        "my_adapted_one",
    ]
    assert {r.region.path for r in shingled_regions} == {fixture_path1}
    assert {r.region.language for r in shingled_regions} == {"python"}


def test_identical_functions():
    parsed_dataclass2 = parsed_fixture(fixture_path2)
    engine = default_rule_engine()
    shingled_regions = shingle_regions(
        extracted_regions=extract_all_regions([parsed_dataclass2], engine),
        parsed_files=[parsed_dataclass2],
        rule_engine=RuleEngine([]),
    )

    # With hybrid mode, filter to explicit regions (function types)
    explicit_shingled = [r for r in shingled_regions if r.region.region_type == "function_definition"]

    # With recursive extraction, we get 2 explicit regions (no section regions)
    assert len(explicit_shingled) == 2
    assert [r.region.region_name for r in explicit_shingled] == ["one", "one_prime"]
    assert {r.region.path for r in explicit_shingled} == {fixture_path2}
    assert {r.region.language for r in explicit_shingled} == {"python"}
    # The first function's first shingle starts at depth 3 in the tree traversal
    # function_definition → parameters → (
    assert explicit_shingled[0].shingles.get_contents()[0] == "function_definition→parameters→((()"
