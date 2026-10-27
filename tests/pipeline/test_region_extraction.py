from treepeat.pipeline.region_extraction import extract_all_regions

from ..conftest import (
    default_rule_engine,
    fixture_class_methods,
    fixture_nested,
    fixture_path1,
    fixture_path2,
    parsed_fixture,
)


def test_extract_regions_dataclass1():
    parsed = parsed_fixture(fixture_path1)
    engine = default_rule_engine()
    regions = extract_all_regions([parsed], engine)

    assert [r.region.region_name for r in regions] == [
        "Model1",
        "Model2",
        "my_adapted_one",
    ]

    assert [r.node.type for r in regions] == [
        "class_definition",
        "class_definition",
        "function_definition",
    ]


    assert regions[0].node.type == "class_definition"

    class_text = parsed.source[
        regions[0].node.start_byte : regions[0].node.end_byte
    ].decode("utf-8")
    assert class_text.startswith("class Model1")
    assert "region: Region" in class_text


    assert regions[1].node.type == "class_definition"
    class_text = parsed.source[
        regions[1].node.start_byte : regions[1].node.end_byte
    ].decode("utf-8")
    assert class_text.startswith("class Model2")
    assert "minhash: MinHash" in class_text


def test_extract_regions_dataclass2():
    parsed = parsed_fixture(fixture_path2)
    engine = default_rule_engine()
    regions = extract_all_regions([parsed], engine)


    regions = [r for r in regions if r.region.region_type == "function_definition"]


    assert len(regions) == 2


    region_names = [r.region.region_name for r in regions]
    assert region_names == ["one", "one_prime"]


    region_types = [r.region.region_type for r in regions]
    assert region_types == [
      "function_definition",
      "function_definition"
    ]


    assert regions[0].region.start_line == 2
    assert regions[0].region.end_line == 7
    assert regions[1].region.start_line == 9
    assert regions[1].region.end_line == 14


    assert regions[0].node.type == "function_definition"
    func_text = parsed.source[
        regions[0].node.start_byte : regions[0].node.end_byte
    ].decode("utf-8")
    assert func_text.startswith("def one()")
    assert "return total" in func_text

    assert regions[1].node.type == "function_definition"
    func_text = parsed.source[
        regions[1].node.start_byte : regions[1].node.end_byte
    ].decode("utf-8")
    assert func_text.startswith("def one_prime()")
    assert "return sum" in func_text


def test_region_nodes_include_all_children():
    parsed = parsed_fixture(fixture_path2)
    engine = default_rule_engine()
    regions = extract_all_regions([parsed], engine)


    function_regions = [r for r in regions if r.region.region_type == "function_definition"]


    for region in function_regions:
        assert region.node.type == "function_definition"


        child_types = [child.type for child in region.node.children]
        assert "identifier" in child_types


        for child in region.node.children:
            if child.type == "identifier":
                name = parsed.source[child.start_byte : child.end_byte].decode("utf-8")
                assert name == region.region.region_name
                break


def test_nested_function_included_in_outer():

    parsed = parsed_fixture(fixture_nested)
    engine = default_rule_engine()
    regions = extract_all_regions([parsed], engine)


    outer = next(r for r in regions if r.region.region_name == "outer_function")


    outer_source = parsed.source[outer.node.start_byte : outer.node.end_byte].decode("utf-8")


    assert "def inner_function_1():" in outer_source
    assert "def inner_function_2():" in outer_source
    assert "return x * 2" in outer_source
    assert "return x * 3" in outer_source



    assert outer.region.start_line == 4
    assert outer.region.end_line == 17


def test_include_sections_false_extracts_all_recursively():

    parsed = parsed_fixture(fixture_nested)
    engine = default_rule_engine()


    regions = extract_all_regions([parsed], engine)


    region_names = [r.region.region_name for r in regions]


    assert "outer_function" in region_names
    assert "inner_function_1" in region_names
    assert "inner_function_2" in region_names
    assert "another_outer" in region_names
    assert "process" in region_names
    assert "transform" in region_names


    assert "ClassWithMethods" in region_names


    assert "method_with_nested" in region_names
    assert "helper" in region_names
    assert "simple_method" in region_names


    for name in region_names:
        assert not name.startswith("lines_"), f"Found unexpected section region: {name}"




    assert len(regions) == 10


def test_class_methods_extracted_separately():

    parsed = parsed_fixture(fixture_class_methods)
    engine = default_rule_engine()


    regions = extract_all_regions([parsed], engine)


    region_names = [r.region.region_name for r in regions]
    region_types = {r.region.region_name: r.region.region_type for r in regions}


    assert "ClassA" in region_names
    assert "ClassB" in region_names
    assert "ClassC" in region_names


    assert "method1" in region_names
    assert "method2" in region_names
    assert "method3" in region_names


    assert "method1_renamed" in region_names

    method2_regions = [r for r in regions if r.region.region_name == "method2"]
    method3_regions = [r for r in regions if r.region.region_name == "method3"]
    assert len(method2_regions) == 2
    assert len(method3_regions) == 2


    assert "different_method" in region_names
    assert "another_different_method" in region_names


    for method_name in [
        "method1",
        "method2",
        "method3",
        "method1_renamed",
        "different_method",
        "another_different_method",
    ]:
        assert region_types[method_name] == "function_definition"


    assert len(regions) == 11



    method2_from_A = next(r for r in method2_regions if r.region.start_line < 30)
    method2_from_B = next(r for r in method2_regions if r.region.start_line > 30)


    method2_A_source = parsed.source[
        method2_from_A.node.start_byte : method2_from_A.node.end_byte
    ].decode("utf-8")
    method2_B_source = parsed.source[
        method2_from_B.node.start_byte : method2_from_B.node.end_byte
    ].decode("utf-8")


    assert "data = [1, 2, 3, 4, 5]" in method2_A_source
    assert "data = [1, 2, 3, 4, 5]" in method2_B_source
    assert "for item in data:" in method2_A_source
    assert "for item in data:" in method2_B_source
    assert "total += item" in method2_A_source
    assert "total += item" in method2_B_source

