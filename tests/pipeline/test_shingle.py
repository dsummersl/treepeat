from ..conftest import parsed_fixture, fixture_path1, fixture_path2
from tssim.pipeline.region_extraction import extract_all_regions
from tssim.pipeline.shingle import shingle_regions


def test_shingle_regions_basic():
    """Test shingling regions from dataclass1.py fixture."""
    parsed_dataclass1 = parsed_fixture(fixture_path1)
    shingled_regions = shingle_regions(
        extracted_regions=extract_all_regions([parsed_dataclass1]),
        parsed_files=[parsed_dataclass1],
        normalizers=[],
    )

    assert len(shingled_regions) == 4
    assert [r.region.region_name for r in shingled_regions] == [
        "lines_1_1",
        "Model1",
        "Model2",
        "my_adapted_one",
    ]
    assert {r.region.path for r in shingled_regions} == {fixture_path1}
    assert {r.region.language for r in shingled_regions} == {"python"}
    assert shingled_regions[0].shingles.shingles == [
        "expression_statement→assignment→identifier(CONSTANT_VALUE_42)",
        "expression_statement→assignment→=(=)",
        "expression_statement→assignment→integer(42)",
    ]


def test_identical_functions():
    parsed_dataclass2 = parsed_fixture(fixture_path2)
    shingled_regions = shingle_regions(
        extracted_regions=extract_all_regions([parsed_dataclass2]),
        parsed_files=[parsed_dataclass2],
        normalizers=[],
    )
    assert len(shingled_regions) == 2
    assert [r.region.region_name for r in shingled_regions] == ["one", "one_prime"]
    assert {r.region.path for r in shingled_regions} == {fixture_path2}
    assert {r.region.language for r in shingled_regions} == {"python"}
    # The first shingle starts at depth 3 in the tree traversal
    # function_definition → parameters → (
    assert shingled_regions[0].shingles.shingles[0] == "function_definition→parameters→((()"
