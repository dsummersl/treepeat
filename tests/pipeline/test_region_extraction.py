from ..conftest import (
    parsed_fixture,
    fixture_path1,
    fixture_path2,
    fixture_nested,
    fixture_class_methods,
    default_rule_engine,
)
from tssim.pipeline.region_extraction import extract_all_regions, get_matched_line_ranges


def test_extract_regions_dataclass1():
    parsed = parsed_fixture(fixture_path1)
    engine = default_rule_engine()
    regions = extract_all_regions([parsed], engine)

    # Should have regions for the python classes
    # Note: lines_1_3 includes comment and CONSTANT_VALUE_42
    assert [r.region.region_name for r in regions] == [
        "lines_1_3",
        "Model1",
        "Model2",
        "my_adapted_one",
    ]

    assert [r.region.region_type for r in regions] == ["lines", "class", "class", "function"]

    # Note: lines_1_3 node type is comment (the first node in that range)
    assert [r.node.type for r in regions] == [
        "comment",
        "class_definition",
        "class_definition",
        "function_definition",
    ]

    # Check that nodes are included
    # First region should be a comment
    assert regions[0].node.type == "comment"

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
    engine = default_rule_engine()
    regions = extract_all_regions([parsed], engine)

    # Should have 3 regions (comment + two functions)
    assert len(regions) == 3

    # Check region names
    region_names = [r.region.region_name for r in regions]
    assert region_names == ["lines_1_1", "one", "one_prime"]

    # Check region types
    region_types = [r.region.region_type for r in regions]
    assert region_types == ["lines", "function", "function"]

    # Check line ranges (comment is line 1, functions start at line 2 and 9)
    assert regions[0].region.start_line == 1
    assert regions[0].region.end_line == 1
    assert regions[1].region.start_line == 2
    assert regions[1].region.end_line == 7
    assert regions[2].region.start_line == 9
    assert regions[2].region.end_line == 14

    # Verify function nodes are function_definition and include the entire function
    assert regions[1].node.type == "function_definition"
    func_text = parsed.source[regions[1].node.start_byte : regions[1].node.end_byte].decode("utf-8")
    assert func_text.startswith("def one()")
    assert "return total" in func_text

    assert regions[2].node.type == "function_definition"
    func_text = parsed.source[regions[2].node.start_byte : regions[2].node.end_byte].decode("utf-8")
    assert func_text.startswith("def one_prime()")
    assert "return sum" in func_text


def test_region_nodes_include_all_children():
    parsed = parsed_fixture(fixture_path2)
    engine = default_rule_engine()
    regions = extract_all_regions([parsed], engine)

    # Filter to only function regions (skip the comment region)
    function_regions = [r for r in regions if r.region.region_type == "function"]

    # For each function region, verify it includes the identifier child
    for region in function_regions:
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
    """Test that with include_sections=True, only top-level functions are extracted.

    With include_sections=True (original behavior), nested functions are part of
    the outer function's AST node and included in the shingles for that region.
    """
    parsed = parsed_fixture(fixture_nested)
    engine = default_rule_engine()
    regions = extract_all_regions([parsed], engine, include_sections=True)

    # Extract region names
    region_names = [r.region.region_name for r in regions]

    # Should only have top-level regions:
    # - lines_1_3 (module docstring and blanks)
    # - outer_function (contains inner_function_1 and inner_function_2 in its AST)
    # - another_outer (contains process and transform in its AST)
    # - ClassWithMethods (class with methods)

    # Verify we have top-level functions
    assert "outer_function" in region_names
    assert "another_outer" in region_names
    assert "ClassWithMethods" in region_names

    # Nested functions should NOT be separate regions when include_sections=True
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
    engine = default_rule_engine()
    regions = extract_all_regions([parsed], engine)

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
    engine = default_rule_engine()
    regions = extract_all_regions([parsed], engine)

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


def test_include_sections_false_extracts_all_recursively():
    """Test that include_sections=False recursively extracts ALL functions/methods/classes.

    This is the Level 1 behavior - extract everything that could potentially match,
    including nested functions, methods within classes, etc. This allows detection
    of duplicate methods even when their containing classes differ.
    """
    parsed = parsed_fixture(fixture_nested)
    engine = default_rule_engine()

    # Extract with include_sections=False (level 1 behavior)
    regions = extract_all_regions([parsed], engine, include_sections=False)

    region_names = [r.region.region_name for r in regions]

    # Should have ALL functions (top-level and nested)
    assert "outer_function" in region_names
    assert "inner_function_1" in region_names  # nested in outer_function
    assert "inner_function_2" in region_names  # nested in outer_function
    assert "another_outer" in region_names
    assert "process" in region_names  # nested in another_outer
    assert "transform" in region_names  # nested in another_outer

    # Should have the class
    assert "ClassWithMethods" in region_names

    # Should have ALL methods (including method with nested function)
    assert "method_with_nested" in region_names
    assert "helper" in region_names  # nested in method_with_nested
    assert "simple_method" in region_names

    # Should NOT have any "lines_X_Y" section regions
    for name in region_names:
        assert not name.startswith("lines_"), f"Found unexpected section region: {name}"

    # Should have 10 regions total (all functions/methods + class)
    # outer_function, inner_function_1, inner_function_2, another_outer, process, transform,
    # ClassWithMethods, method_with_nested, helper, simple_method
    assert len(regions) == 10


def test_class_methods_extracted_separately():
    """Test that methods within classes are extracted as separate regions.

    This demonstrates the scenario where ClassA and ClassB have some duplicate
    methods and some different methods. With recursive extraction, individual
    methods can be matched even if the classes overall don't match.
    """
    parsed = parsed_fixture(fixture_class_methods)
    engine = default_rule_engine()

    # Extract with include_sections=False (recursive extraction)
    regions = extract_all_regions([parsed], engine, include_sections=False)

    region_names = [r.region.region_name for r in regions]
    region_types = {r.region.region_name: r.region.region_type for r in regions}

    # Should have all three classes
    assert "ClassA" in region_names
    assert "ClassB" in region_names
    assert "ClassC" in region_names

    # Should have ALL methods from ClassA
    assert "method1" in region_names
    assert "method2" in region_names
    assert "method3" in region_names

    # Should have ALL methods from ClassB (including renamed method1)
    assert "method1_renamed" in region_names
    # method2 and method3 appear twice (once for ClassA, once for ClassB)
    method2_regions = [r for r in regions if r.region.region_name == "method2"]
    method3_regions = [r for r in regions if r.region.region_name == "method3"]
    assert len(method2_regions) == 2  # One in ClassA, one in ClassB
    assert len(method3_regions) == 2  # One in ClassA, one in ClassB

    # Should have methods from ClassC
    assert "different_method" in region_names
    assert "another_different_method" in region_names

    # Verify all methods are typed as "function" (Python treats methods as function_definition)
    for method_name in ["method1", "method2", "method3", "method1_renamed", "different_method", "another_different_method"]:
        assert region_types[method_name] == "function"

    # Total: 3 classes + 3 methods (ClassA) + 3 methods (ClassB) + 2 methods (ClassC) = 11 regions
    assert len(regions) == 11

    # Verify that method2 from ClassA and method2 from ClassB have different line ranges
    # but identical code (they would match at high similarity)
    method2_from_A = next(r for r in method2_regions if r.region.start_line < 30)
    method2_from_B = next(r for r in method2_regions if r.region.start_line > 30)

    # Get source code for both methods
    method2_A_source = parsed.source[
        method2_from_A.node.start_byte : method2_from_A.node.end_byte
    ].decode("utf-8")
    method2_B_source = parsed.source[
        method2_from_B.node.start_byte : method2_from_B.node.end_byte
    ].decode("utf-8")

    # They should have very similar implementation (docstrings differ slightly)
    assert "data = [1, 2, 3, 4, 5]" in method2_A_source
    assert "data = [1, 2, 3, 4, 5]" in method2_B_source
    assert "for item in data:" in method2_A_source
    assert "for item in data:" in method2_B_source
    assert "total += item" in method2_A_source
    assert "total += item" in method2_B_source
    # Docstrings differ, but code is identical - these would match at high similarity
