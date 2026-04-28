from pathlib import Path

import pytest

from treepeat.models.similarity import Region
from treepeat.pipeline.languages.javascript import JavaScriptConfig
from treepeat.pipeline.languages.jsx import JsxConfig
from treepeat.pipeline.languages.tsx import TsxConfig
from treepeat.pipeline.languages.typescript import TypeScriptConfig
from treepeat.pipeline.parse import parse_source_code
from treepeat.pipeline.region_extraction import ExtractedRegion
from treepeat.pipeline.rules.engine import RuleEngine
from treepeat.pipeline.shingle import ASTShingler


def _shingle_tokens(config, language: str, source: str, loose: bool) -> list[str]:
    rules = config.get_loose_rules() if loose else config.get_default_rules()
    engine = RuleEngine(rules)
    source_bytes = source.encode("utf-8")
    parsed = parse_source_code(source_bytes, language, Path("test_file"))
    region = Region(
        path=Path("test_file"),
        language=language,
        region_type="test",
        region_name="test",
        start_line=1,
        end_line=source.count("\n") + 1,
    )
    extracted_region = ExtractedRegion(region=region, node=parsed.root_node)

    engine.reset_identifiers()
    engine.precompute_queries(extracted_region.node, language, source_bytes)
    shingled = ASTShingler(rule_engine=engine, k=1).shingle_region(extracted_region, source_bytes)
    return shingled.shingles.get_contents()


@pytest.mark.parametrize(
    ("config", "language"),
    [
        (JavaScriptConfig(), "javascript"),
        (TypeScriptConfig(), "typescript"),
        (JsxConfig(), "jsx"),
        (TsxConfig(), "tsx"),
    ],
)
def test_javascript_family_default_rules_preserve_identifiers(config, language):
    tokens = _shingle_tokens(config, language, "const renamed = original;", loose=False)
    token_str = " ".join(tokens)

    assert "identifier(renamed)" in token_str
    assert "identifier(original)" in token_str
    assert "VAR_1" not in token_str


@pytest.mark.parametrize(
    ("config", "language"),
    [
        (JavaScriptConfig(), "javascript"),
        (TypeScriptConfig(), "typescript"),
        (JsxConfig(), "jsx"),
        (TsxConfig(), "tsx"),
    ],
)
def test_javascript_family_loose_rules_anonymize_identifiers(config, language):
    tokens = _shingle_tokens(config, language, "const renamed = original;", loose=True)
    token_str = " ".join(tokens)

    assert any("identifier(VAR_" in t for t in tokens)
    assert "renamed" not in token_str
    assert "original" not in token_str


def test_javascript_loose_rules_function_name_beats_anonymize():
    # "Anonymize function names" (REPLACE_VALUE) runs after "Anonymize identifiers" (ANONYMIZE)
    # and overwrites the value slot, so function names surface as FUNC not VAR_n.
    tokens = _shingle_tokens(JavaScriptConfig(), "javascript", "function foo() {}", loose=True)
    token_str = " ".join(tokens)

    assert "identifier(FUNC)" in token_str
    assert "foo" not in token_str


def test_javascript_rules_detailed(rule_tester):
    config = JavaScriptConfig()
    rule_tester.verify_rules(
        config,
        [
            {
                "rule_name": "Ignore import/export statements",
                "source": "import { foo } from 'bar';\nexport const x = 1;",
                "expected_symbol": None,
                "unexpected_symbol": "import_statement",
            },
            {
                "rule_name": "Ignore comments",
                "source": "// line comment\n/* block\ncomment */",
                "expected_symbol": None,
                "unexpected_symbol": "comment",
            },
            {
                "rule_name": "Anonymize function names",
                "source": "function myFunc() {}",
                "expected_symbol": "identifier(FUNC)",
                "unexpected_symbol": "myFunc",
            },
            {
                "rule_name": "Anonymize class names",
                "source": "class MyClass {}",
                "expected_symbol": "identifier(CLASS)",
                "unexpected_symbol": "MyClass",
            },
            {
                "rule_name": "Anonymize identifiers",
                "source": "let x = 1;",
                "expected_symbol": "identifier(VAR_1)",
                "unexpected_symbol": "let x = 1",
            },
            {
                "rule_name": "Anonymize literal values",
                "source": "const s = 'hello';",
                "expected_symbol": "string(<LIT>)",
                "unexpected_symbol": "hello world",
            },
            {
                "rule_name": "Anonymize collections",
                "source": "const a = [];",
                "expected_symbol": "<COLL>",
                "unexpected_symbol": "array",
            },
            {
                "rule_name": "Anonymize expressions",
                "source": "x = a + b;",
                "expected_symbol": "<EXP>",
                "unexpected_symbol": "binary_expression",
            },
        ],
    )
