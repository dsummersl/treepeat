"""Tests for Kotlin language configuration and rules."""

from pathlib import Path

import pytest

from tests.conftest import parse_fixture
from treepeat.pipeline.languages.kotlin import KotlinConfig
from treepeat.pipeline.region_extraction import extract_all_regions
from treepeat.pipeline.rules.engine import RuleEngine, build_default_rules, build_loose_rules


# Fixture path
fixture_comprehensive = (
    Path(__file__).parent.parent.parent / "fixtures" / "kotlin" / "comprehensive.kt"
)


@pytest.mark.parametrize(
    "rules",
    [[rule for rule, _ in build_default_rules()], [rule for rule, _ in build_loose_rules()]],
)
def test_kotlin_rules_extract(rules):
    """Test that Kotlin files can be processed with different rule sets."""
    parsed = parse_fixture(fixture_comprehensive, "kotlin")
    engine = RuleEngine(rules)
    regions = extract_all_regions([parsed], engine)

    # Should find at least Comprehensive class and two function declarations
    assert len(regions) >= 3


def test_language_name():
    """Test that Kotlin config returns correct language name."""
    assert KotlinConfig().get_language_name() == "kotlin"


def test_kotlin_specific_rules():
    """Test that Kotlin specific rules (imports, comments) work."""
    from treepeat.pipeline.parse import parse_source_code
    from treepeat.pipeline.shingle import ASTShingler
    from treepeat.pipeline.region_extraction import ExtractedRegion
    from treepeat.models.similarity import Region

    source = b"""
    package com.example
    import java.util.*
    /* Multiline
       comment */
    class Test {
        // Line comment
        fun foo() {
            val x = 1
        }
    }
    """

    parsed = parse_source_code(source, "kotlin", Path("test.kt"))
    rules = [rule for rule, _ in build_default_rules()]
    engine = RuleEngine(rules)

    region = Region(
        path=Path("test.kt"),
        language="kotlin",
        region_type="lines",
        region_name="test",
        start_line=1,
        end_line=11,
    )
    extracted_region = ExtractedRegion(region=region, node=parsed.root_node)

    shingler = ASTShingler(rule_engine=engine, k=2)
    shingler.rule_engine.reset_identifiers()
    shingler.rule_engine.precompute_queries(extracted_region.node, "kotlin", source)
    shingled = shingler.shingle_region(extracted_region, source)

    shingle_str = " ".join(shingled.shingles.get_contents())

    # Imports and comments should be removed
    assert "import_directive" not in shingle_str
    assert "line_comment" not in shingle_str
    assert "multiline_comment" not in shingle_str

    # Class and function should be there
    assert "class_declaration" in shingle_str
    assert "function_declaration" in shingle_str
