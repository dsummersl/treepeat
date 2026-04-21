"""Tests for Rust language configuration and rules."""

from pathlib import Path

import pytest

from tests.conftest import parse_fixture
from treepeat.pipeline.region_extraction import extract_all_regions
from treepeat.pipeline.rules.engine import RuleEngine, build_default_rules, build_loose_rules

# Fixture path
fixture_comprehensive = (
    Path(__file__).parent.parent.parent / "fixtures" / "rust" / "comprehensive.rs"
)


@pytest.mark.parametrize(
    "rules",
    [[rule for rule, _ in build_default_rules()], [rule for rule, _ in build_loose_rules()]],
)
def test_rust_rules_extract(rules):
    """Test that Rust files can be processed with different rule sets."""
    parsed = parse_fixture(fixture_comprehensive, "rust")
    engine = RuleEngine(rules)
    regions = extract_all_regions([parsed], engine)

    # All six extraction types must be present
    region_types = {r.region.region_type for r in regions}
    assert region_types == {
        "function_item", "impl_item", "struct_item",
        "enum_item", "trait_item", "macro_definition",
    }


def test_lifetime_names_do_not_affect_similarity():
    """Functions that differ only in lifetime parameter names must produce identical shingles.

    'a and 'b are α-equivalent-ish; renaming them should not affect duplicate detection.
    'static is intentionally excluded from this rule and is verified in test_rust_rules.py.
    """
    from treepeat.models.similarity import Region
    from treepeat.pipeline.parse import parse_source_code
    from treepeat.pipeline.region_extraction import ExtractedRegion
    from treepeat.pipeline.shingle import ASTShingler

    def shingle_source(source: str) -> list[str]:
        source_bytes = source.encode("utf-8")
        parsed = parse_source_code(source_bytes, "rust", Path("test.rs"))
        rules = [rule for rule, _ in build_loose_rules()]
        engine = RuleEngine(rules)
        region = Region(
            path=Path("test.rs"),
            language="rust",
            region_type="lines",
            region_name="test",
            start_line=1,
            end_line=source.count("\n") + 1,
        )
        extracted = ExtractedRegion(region=region, node=parsed.root_node)
        engine.reset_identifiers()
        engine.precompute_queries(extracted.node, "rust", source_bytes)
        shingler = ASTShingler(rule_engine=engine, k=2)
        return shingler.shingle_region(extracted, source_bytes).shingles.get_contents()

    shingles_a = shingle_source("fn foo<'a>(x: &'a str) -> &'a str { x }")
    shingles_b = shingle_source("fn foo<'b>(x: &'b str) -> &'b str { x }")

    assert shingles_a == shingles_b


def test_rust_specific_rules():
    """Test that Rust-specific default rules (use, comments, attributes) work."""
    from treepeat.models.similarity import Region
    from treepeat.pipeline.parse import parse_source_code
    from treepeat.pipeline.region_extraction import ExtractedRegion
    from treepeat.pipeline.shingle import ASTShingler

    source = b"""
#![allow(dead_code)]
use std::collections::HashMap;
extern crate serde;
// line comment
/// doc comment
/* block comment */
#[derive(Debug, Clone)]
pub struct Foo {
    pub x: i32,
}
impl Foo {
    pub fn new(x: i32) -> Self {
        Foo { x }
    }
}
"""

    parsed = parse_source_code(source, "rust", Path("test.rs"))
    rules = [rule for rule, _ in build_default_rules()]
    engine = RuleEngine(rules)

    region = Region(
        path=Path("test.rs"),
        language="rust",
        region_type="lines",
        region_name="test",
        start_line=1,
        end_line=source.count(b"\n") + 1,
    )
    extracted_region = ExtractedRegion(region=region, node=parsed.root_node)

    shingler = ASTShingler(rule_engine=engine, k=2)
    shingler.rule_engine.reset_identifiers()
    shingler.rule_engine.precompute_queries(extracted_region.node, "rust", source)
    shingled = shingler.shingle_region(extracted_region, source)

    shingle_str = " ".join(shingled.shingles.get_contents())

    # Noise should be removed
    assert "use_declaration" not in shingle_str
    assert "extern_crate_declaration" not in shingle_str
    assert "line_comment" not in shingle_str
    assert "block_comment" not in shingle_str
    assert "attribute_item" not in shingle_str
    assert "inner_attribute_item" not in shingle_str

    # Structural elements should remain
    assert "struct_item" in shingle_str
    assert "impl_item" in shingle_str
    assert "function_item" in shingle_str
