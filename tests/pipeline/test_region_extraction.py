from ..conftest import parsed_fixture, fixture_path1, fixture_path2
from tssim.pipeline.region_extraction import extract_all_regions


def test_extract_regions_dataclass1():
    parsed = parsed_fixture(fixture_path1)
    regions = extract_all_regions([parsed])

    # Should have regions for the python classes
    assert [r.region.region_name for r in regions] == [
        "lines_1_1",
        "Model1",
        "Model2",
        "my_adapted_one",
    ]

    assert [r.region.region_type for r in regions] == ["lines", "class", "class", "function"]

    assert [r.node.type for r in regions] == [
        "expression_statement",
        "class_definition",
        "class_definition",
        "function_definition",
    ]

    # Check that nodes are included
    # First region should be the assignment statement
    assert regions[0].node.type == "expression_statement"

    # Second region should be the class definition node
    assert regions[1].node.type == "class_definition"
    # Verify the node includes the entire class definition
    class_text = parsed.source[regions[1].node.start_byte : regions[1].node.end_byte].decode(
        "utf-8"
    )
    assert class_text.startswith("class Model1")
    assert "region: Region" in class_text

    # Third region should be the class definition node
    assert regions[2].node.type == "class_definition"
    class_text = parsed.source[regions[2].node.start_byte : regions[2].node.end_byte].decode(
        "utf-8"
    )
    assert class_text.startswith("class Model2")
    assert "minhash: MinHash" in class_text


def test_extract_regions_dataclass2():
    parsed = parsed_fixture(fixture_path2)
    regions = extract_all_regions([parsed])

    # Should have 2 regions (two functions)
    assert len(regions) == 2

    # Check region names
    region_names = [r.region.region_name for r in regions]
    assert region_names == ["one", "one_prime"]

    # Check region types
    region_types = [r.region.region_type for r in regions]
    assert region_types == ["function", "function"]

    # Check line ranges
    assert regions[0].region.start_line == 1
    assert regions[0].region.end_line == 6
    assert regions[1].region.start_line == 8
    assert regions[1].region.end_line == 13

    # Verify nodes are function_definition and include the entire function
    assert regions[0].node.type == "function_definition"
    func_text = parsed.source[regions[0].node.start_byte : regions[0].node.end_byte].decode("utf-8")
    assert func_text.startswith("def one()")
    assert "return total" in func_text

    assert regions[1].node.type == "function_definition"
    func_text = parsed.source[regions[1].node.start_byte : regions[1].node.end_byte].decode("utf-8")
    assert func_text.startswith("def one_prime()")
    assert "return sum" in func_text


def test_region_nodes_include_all_children():
    parsed = parsed_fixture(fixture_path2)
    regions = extract_all_regions([parsed])

    # For each function region, verify it includes the identifier child
    for region in regions:
        assert region.node.type == "function_definition"

        # Check that the node has children including identifier
        child_types = [child.type for child in region.node.children]
        assert "identifier" in child_types

        # Find the identifier child and verify it matches the region name
        for child in region.node.children:
            if child.type == "identifier":
                name = parsed.source[child.start_byte : child.end_byte].decode("utf-8")
                assert name == region.region.region_name
                break
