

from pathlib import Path

import pytest

from tests.conftest import parse_fixture
from treepeat.pipeline.region_extraction import extract_all_regions
from treepeat.pipeline.rules.engine import RuleEngine, build_default_rules, build_loose_rules

fixture_comprehensive = (
    Path(__file__).parent.parent.parent / "fixtures" / "java" / "comprehensive.java"
)


@pytest.mark.parametrize(
    "rules",
    [[rule for rule, _ in build_default_rules()], [rule for rule, _ in build_loose_rules()]],
)
def test_java_rules_extract(rules):

    parsed = parse_fixture(fixture_comprehensive, "java")
    engine = RuleEngine(rules)
    regions = extract_all_regions([parsed], engine)


    assert len(regions) >= 3


def test_java_specific_rules():

    from treepeat.models.similarity import Region
    from treepeat.pipeline.parse import parse_source_code
    from treepeat.pipeline.region_extraction import ExtractedRegion
    from treepeat.pipeline.shingle import ASTShingler

    source = b"""
    package com.example;
    import java.util.List;
    /* Block comment */
    public class Test {
        // Line comment
        public void foo() {
            int x = 1;
        }
    }
    """

    parsed = parse_source_code(source, "java", Path("test.java"))
    rules = [rule for rule, _ in build_default_rules()]
    engine = RuleEngine(rules)

    region = Region(
        path=Path("test.java"),
        language="java",
        region_type="lines",
        region_name="test",
        start_line=1,
        end_line=10,
    )
    extracted_region = ExtractedRegion(region=region, node=parsed.root_node)

    shingler = ASTShingler(rule_engine=engine, k=2)
    shingler.rule_engine.reset_identifiers()
    shingler.rule_engine.precompute_queries(extracted_region.node, "java", source)
    shingled = shingler.shingle_region(extracted_region, source)

    shingle_str = " ".join(shingled.shingles.get_contents())


    assert "import_declaration" not in shingle_str
    assert "line_comment" not in shingle_str
    assert "block_comment" not in shingle_str


    assert "class_declaration" in shingle_str
    assert "method_declaration" in shingle_str
