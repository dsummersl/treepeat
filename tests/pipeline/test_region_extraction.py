from ..conftest import parsed_fixture, fixture_path1, fixture_path2, fixture_nested
from tssim.pipeline.region_extraction import extract_all_regions, get_matched_line_ranges


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


def test_extract_nested_functions():
    """Test that only top-level functions are extracted as regions.

    Nested functions are part of the outer function's AST node and will be
    included in the shingles for the outer function. This is correct behavior
    because when an outer function matches, we want its nested functions to be
    considered part of that match.
    """
    parsed = parsed_fixture(fixture_nested)
    regions = extract_all_regions([parsed])

    # Extract region names
    region_names = [r.region.region_name for r in regions]
    region_types = [r.region.region_type for r in regions]

    # Should only have top-level regions:
    # - lines_1_1 (module docstring)
    # - outer_function (contains inner_function_1 and inner_function_2 in its AST)
    # - another_outer (contains process and transform in its AST)
    # - ClassWithMethods (class with methods)

    # Verify we have top-level functions
    assert "outer_function" in region_names
    assert "another_outer" in region_names
    assert "ClassWithMethods" in region_names

    # Nested functions should NOT be separate regions
    assert "inner_function_1" not in region_names
    assert "inner_function_2" not in region_names
    assert "process" not in region_names
    assert "transform" not in region_names
    assert "helper" not in region_names

    # Verify types
    function_regions = [r for r in regions if r.region.region_type == "function"]
    class_regions = [r for r in regions if r.region.region_type == "class"]

    assert len(function_regions) == 2  # outer_function and another_outer
    assert len(class_regions) == 1  # ClassWithMethods


def test_nested_function_included_in_outer():
    """Test that outer functions include nested functions in their AST node."""
    parsed = parsed_fixture(fixture_nested)
    regions = extract_all_regions([parsed])

    # Find outer_function region
    outer = next(r for r in regions if r.region.region_name == "outer_function")

    # Get the source code for the outer function
    outer_source = parsed.source[outer.node.start_byte : outer.node.end_byte].decode("utf-8")

    # Verify that nested functions are included in the outer function's source
    assert "def inner_function_1():" in outer_source
    assert "def inner_function_2():" in outer_source
    assert "return x * 2" in outer_source  # from inner_function_1
    assert "return x * 3" in outer_source  # from inner_function_2

    # Verify the outer function has a reasonable line range
    # outer_function should span from line 4 to line 17
    assert outer.region.start_line == 4
    assert outer.region.end_line == 17  # Should include all nested functions


def test_matched_line_ranges_covers_entire_function():
    """Test that matching a function marks all its lines as matched (including nested code)."""
    parsed = parsed_fixture(fixture_nested)
    regions = extract_all_regions([parsed])

    # Find outer_function
    outer = next(r for r in regions if r.region.region_name == "outer_function")

    # Simulate that outer_function was matched at level 1
    matched_regions = [outer.region]
    matched_lines_by_file = get_matched_line_ranges(matched_regions)

    # Get matched lines for this file
    matched_lines = matched_lines_by_file.get(parsed.path, set())

    # Verify that all lines of outer_function are marked as matched
    # This includes the lines where nested functions are defined
    for line in range(outer.region.start_line, outer.region.end_line + 1):
        assert line in matched_lines, f"Line {line} should be marked as matched"

    # The matched lines count should equal the number of lines in the function
    expected_line_count = outer.region.end_line - outer.region.start_line + 1
    assert len(matched_lines) == expected_line_count


def test_include_sections_false_extracts_only_top_level():
    """Test that include_sections=False extracts top-level functions/classes without section regions."""
    parsed = parsed_fixture(fixture_nested)

    # Extract with include_sections=False (level 1 behavior)
    regions = extract_all_regions([parsed], include_sections=False)

    region_names = [r.region.region_name for r in regions]

    # Should have top-level functions and classes
    assert "outer_function" in region_names
    assert "another_outer" in region_names
    assert "ClassWithMethods" in region_names

    # Should NOT have any "lines_X_Y" section regions
    for name in region_names:
        assert not name.startswith("lines_"), f"Found unexpected section region: {name}"

    # Should have exactly 3 regions (2 functions + 1 class)
    assert len(regions) == 3
