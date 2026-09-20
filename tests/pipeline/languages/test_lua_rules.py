from pathlib import Path

from treepeat.models.similarity import Region
from treepeat.pipeline.languages.lua import LuaConfig
from treepeat.pipeline.parse import parse_source_code
from treepeat.pipeline.region_extraction import ExtractedRegion
from treepeat.pipeline.rules.engine import RuleEngine
from treepeat.pipeline.shingle import ASTShingler


def _loose_tokens(source: str) -> list[str]:
    """Shingle a snippet with the full loose ruleset."""
    engine = RuleEngine(LuaConfig().get_loose_rules())
    source_bytes = source.encode("utf-8")
    parsed = parse_source_code(source_bytes, "lua", Path("test.lua"))
    region = Region(
        path=Path("test.lua"),
        language="lua",
        region_type="test",
        region_name="test",
        start_line=1,
        end_line=source.count("\n") + 1,
    )
    extracted = ExtractedRegion(region=region, node=parsed.root_node)

    shingler = ASTShingler(rule_engine=engine, k=1)
    engine.reset_identifiers()
    engine.precompute_queries(extracted.node, "lua", source_bytes)
    return shingler.shingle_region(extracted, source_bytes).shingles.get_contents()


def test_lua_rules_detailed(rule_tester):
    config = LuaConfig()
    rule_tester.verify_rules(
        config,
        [
            {
                "rule_name": "Ignore require declarations",
                "source": 'local socket = require("socket")',
                "expected_symbol": None,
                "unexpected_symbol": "variable_declaration",
            },
            {
                "rule_name": "Ignore comments",
                "source": "-- line comment\n--[[ multi\nline ]]",
                "expected_symbol": None,
                "unexpected_symbol": "comment",
            },
            {
                "rule_name": "Anonymize function names",
                "source": "local function myFunc() end",
                "expected_symbol": "FUNC",
                "unexpected_symbol": "myFunc",
            },
            {
                "rule_name": "Anonymize function names",
                "source": "function M.myFunc() end",
                "expected_symbol": "FUNC",
                "unexpected_symbol": "myFunc",
            },
            {
                "rule_name": "Anonymize function names",
                "source": "function M:myMethod() end",
                "expected_symbol": "FUNC",
                "unexpected_symbol": "myMethod",
            },
            {
                "rule_name": "Ignore string content",
                "source": 'local s = "secret"',
                "expected_symbol": None,
                "unexpected_symbol": "secret",
            },
            {
                "rule_name": "Anonymize identifiers",
                "source": "local myVar = 1",
                "expected_symbol": "VAR_1",
                "unexpected_symbol": "myVar",
            },
            {
                "rule_name": "Anonymize string literals",
                "source": 'local s = "hello"',
                "expected_symbol": "<STR>",
                # The content itself is stripped by the "Ignore string content"
                # rule, so this rule alone is not expected to hide it.
                "unexpected_symbol": None,
            },
            {
                "rule_name": "Anonymize string literals",
                "source": "local s = [[hello]]",
                "expected_symbol": "<STR>",
                "unexpected_symbol": None,
            },
            {
                "rule_name": "Anonymize numeric literals",
                "source": "local n = 42 + 1.5",
                "expected_symbol": "<NUM>",
                "unexpected_symbol": "42",
            },
            {
                "rule_name": "Anonymize boolean and nil literals",
                "source": "local a = true\nlocal b = false\nlocal c = nil",
                "expected_symbol": "<LIT>",
                "unexpected_symbol": None,
            },
            {
                "rule_name": "Anonymize binary expressions",
                "source": 'local x = a .. b',
                "expected_symbol": "<BINOP>",
                "unexpected_symbol": "binary_expression",
            },
            {
                "rule_name": "Anonymize unary expressions",
                "source": "local x = not a",
                "expected_symbol": "<UNOP>",
                "unexpected_symbol": "unary_expression",
            },
        ],
    )


def test_lua_function_name_rule_wins_over_identifier_anonymization():
    # The function name must stay FUNC even though the loose ruleset also
    # anonymizes every identifier.
    tokens = _loose_tokens("local function foo() end")

    assert "identifier(FUNC)" in tokens
    assert "identifier(VAR_1)" not in tokens


def test_lua_method_table_name_is_preserved():
    # Only the trailing name segment is replaced; the table keeps its identity
    # (anonymized as an ordinary identifier under the loose ruleset).
    tokens = _loose_tokens("function Obj:method() end")

    assert "identifier(FUNC)" in tokens
    assert "identifier(VAR_1)" in tokens
