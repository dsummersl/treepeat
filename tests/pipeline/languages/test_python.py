"""Tests for Python language configuration and rules."""

from pathlib import Path

import pytest

from tests.conftest import parse_fixture
from whorl.pipeline.languages.python import PythonConfig
from whorl.pipeline.region_extraction import extract_all_regions
from whorl.pipeline.rules.engine import RuleEngine, build_default_rules, build_loose_rules


# Fixture path
fixture_comprehensive = Path(__file__).parent.parent.parent / "fixtures" / "python" / "class_with_methods.py"


@pytest.mark.parametrize("rules", [
    [],
    [rule for rule, _ in build_default_rules()],
    [rule for rule, _ in build_loose_rules()]
])
def test_python_rules_extract(rules):
    """Test that Python files can be processed with different rule sets."""
    parsed = parse_fixture(fixture_comprehensive, "python")
    engine = RuleEngine(rules)
    regions = extract_all_regions([parsed], engine)

    assert len(regions) > 0


def test_language_name():
    """Test that Python config returns correct language name."""
    assert PythonConfig().get_language_name() == "python"


def test_import_removal_rules():
    """Test that all import types (including future imports) are removed."""
    from whorl.pipeline.parse import parse_source_code
    from whorl.pipeline.shingle import ASTShingler
    from whorl.pipeline.region_extraction import ExtractedRegion
    from whorl.models.similarity import Region

    # Code with future imports, regular imports, and from imports
    source = b"""from __future__ import annotations

import os
import sys
from pathlib import Path

def foo():
    return 42
"""

    parsed = parse_source_code(source, "python", Path("test.py"))
    rules = [rule for rule, _ in build_default_rules()]
    engine = RuleEngine(rules)

    # Create a region for the entire file
    region = Region(
        path=Path("test.py"),
        language="python",
        region_type="lines",
        region_name="test",
        start_line=1,
        end_line=9,
    )
    extracted_region = ExtractedRegion(region=region, node=parsed.root_node)

    # Shingle the region
    shingler = ASTShingler(rule_engine=engine, k=3)
    shingler.rule_engine.reset_identifiers()
    shingler.rule_engine.precompute_queries(extracted_region.node, "python", source)
    shingled = shingler.shingle_region(extracted_region, source)

    # Check that shingles don't contain import-related nodes
    shingle_str = " ".join(shingled.shingles.shingles)
    assert "future_import_statement" not in shingle_str
    assert "import_statement" not in shingle_str
    assert "import_from_statement" not in shingle_str

    # Shingles should only contain function-related nodes
    assert "function_definition" in shingle_str


def test_type_checking_block_removal():
    """Test that TYPE_CHECKING blocks are removed."""
    from whorl.pipeline.parse import parse_source_code
    from whorl.pipeline.shingle import ASTShingler
    from whorl.pipeline.region_extraction import ExtractedRegion
    from whorl.models.similarity import Region

    # Code with TYPE_CHECKING block
    source = b"""import typing as t

if t.TYPE_CHECKING:
    from foo import Bar
    from baz import Qux

def foo():
    return 42
"""

    parsed = parse_source_code(source, "python", Path("test.py"))
    rules = [rule for rule, _ in build_default_rules()]
    engine = RuleEngine(rules)

    region = Region(
        path=Path("test.py"),
        language="python",
        region_type="lines",
        region_name="test",
        start_line=1,
        end_line=8,
    )
    extracted_region = ExtractedRegion(region=region, node=parsed.root_node)

    shingler = ASTShingler(rule_engine=engine, k=3)
    shingler.rule_engine.reset_identifiers()
    shingler.rule_engine.precompute_queries(extracted_region.node, "python", source)
    shingled = shingler.shingle_region(extracted_region, source)

    # TYPE_CHECKING block should be removed
    shingle_str = " ".join(shingled.shingles.shingles)
    assert "TYPE_CHECKING" not in shingle_str

    # Regular function should still be present
    assert "function_definition" in shingle_str


def test_typevar_removal():
    """Test that TypeVar declarations are removed."""
    from whorl.pipeline.parse import parse_source_code
    from whorl.pipeline.shingle import ASTShingler
    from whorl.pipeline.region_extraction import ExtractedRegion
    from whorl.models.similarity import Region

    # Code with TypeVar declarations
    source = b"""import typing as t

T = t.TypeVar("T")
T_bound = t.TypeVar("T_bound", bound=str)

def foo():
    return 42
"""

    parsed = parse_source_code(source, "python", Path("test.py"))
    rules = [rule for rule, _ in build_default_rules()]
    engine = RuleEngine(rules)

    region = Region(
        path=Path("test.py"),
        language="python",
        region_type="lines",
        region_name="test",
        start_line=1,
        end_line=7,
    )
    extracted_region = ExtractedRegion(region=region, node=parsed.root_node)

    shingler = ASTShingler(rule_engine=engine, k=3)
    shingler.rule_engine.reset_identifiers()
    shingler.rule_engine.precompute_queries(extracted_region.node, "python", source)
    shingled = shingler.shingle_region(extracted_region, source)

    # TypeVar should be removed
    shingle_str = " ".join(shingled.shingles.shingles)
    assert "TypeVar" not in shingle_str

    # Regular function should still be present
    assert "function_definition" in shingle_str
