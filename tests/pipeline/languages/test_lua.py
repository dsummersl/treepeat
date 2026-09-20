"""Tests for Lua language configuration and rules."""

from pathlib import Path

import pytest

from tests.conftest import parse_fixture
from treepeat.models.similarity import Region
from treepeat.pipeline.languages import LANGUAGE_CONFIGS, LANGUAGE_EXTENSIONS
from treepeat.pipeline.languages.lua import LuaConfig
from treepeat.pipeline.parse import detect_language, parse_source_code
from treepeat.pipeline.region_extraction import ExtractedRegion, extract_all_regions
from treepeat.pipeline.rules.engine import RuleEngine, build_default_rules, build_loose_rules
from treepeat.pipeline.shingle import ASTShingler

# Fixture path
fixture_comprehensive = Path(__file__).parent.parent.parent / "fixtures" / "lua" / "comprehensive.lua"


def _shingle_source(source: str, rules, k: int = 2) -> list[str]:
    """Shingle a Lua snippet with the given rules."""
    source_bytes = source.encode("utf-8")
    parsed = parse_source_code(source_bytes, "lua", Path("test.lua"))
    engine = RuleEngine(rules)
    region = Region(
        path=Path("test.lua"),
        language="lua",
        region_type="lines",
        region_name="test",
        start_line=1,
        end_line=source.count("\n") + 1,
    )
    extracted = ExtractedRegion(region=region, node=parsed.root_node)
    engine.reset_identifiers()
    engine.precompute_queries(extracted.node, "lua", source_bytes)
    shingler = ASTShingler(rule_engine=engine, k=k)
    return shingler.shingle_region(extracted, source_bytes).shingles.get_contents()


def test_lua_is_registered():
    """Lua is wired into the language registry and detected by extension."""
    assert isinstance(LANGUAGE_CONFIGS["lua"], LuaConfig)
    assert LANGUAGE_EXTENSIONS["lua"] == [".lua"]
    assert detect_language(Path("init.lua")) == "lua"


@pytest.mark.parametrize(
    "rules",
    [[rule for rule, _ in build_default_rules()], [rule for rule, _ in build_loose_rules()]],
)
def test_lua_rules_extract(rules):
    """Test that Lua files can be processed with different rule sets."""
    parsed = parse_fixture(fixture_comprehensive, "lua")
    engine = RuleEngine(rules)
    regions = extract_all_regions([parsed], engine)

    region_types = {r.region.region_type for r in regions}
    assert region_types == {"function_declaration", "function_definition", "table_constructor"}


def test_lua_qualified_function_names_are_reported():
    """Table-qualified declarations keep a useful region name."""
    parsed = parse_fixture(fixture_comprehensive, "lua")
    engine = RuleEngine([rule for rule, _ in build_default_rules()])
    names = {r.region.region_name for r in extract_all_regions([parsed], engine)}

    assert "Comprehensive.calculateSum" in names
    assert "Comprehensive:greet" in names


def test_lua_specific_rules():
    """Test that Lua-specific default rules (requires, comments) work."""
    source = """
local socket = require("socket")
-- line comment
--[[ block
     comment ]]
local M = {}
function M.foo()
  local x = 1
  return x
end
"""
    shingle_str = " ".join(_shingle_source(source, [rule for rule, _ in build_default_rules()]))

    # Requires and comments should be removed
    assert "require" not in shingle_str
    assert "comment" not in shingle_str

    # Structural elements should remain
    assert "function_declaration" in shingle_str
    assert "table_constructor" in shingle_str


def test_lua_local_declarations_are_not_mistaken_for_requires():
    """Only `require` declarations are dropped; other locals survive."""
    shingle_str = " ".join(
        _shingle_source('local port = compute("socket")', [rule for rule, _ in build_default_rules()])
    )

    assert "variable_declaration" in shingle_str


def test_lua_renamed_functions_produce_identical_shingles():
    """Two identical functions differing only in name must shingle the same."""
    rules = [rule for rule, _ in build_default_rules()]
    a = _shingle_source("local function add(x, y)\n  return x + y\nend", rules)
    b = _shingle_source("local function plus(x, y)\n  return x + y\nend", rules)

    assert a == b
