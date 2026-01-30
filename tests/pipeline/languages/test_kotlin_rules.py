from treepeat.pipeline.languages.kotlin import KotlinConfig


def test_kotlin_rules_detailed(rule_tester):
    config = KotlinConfig()
    rule_tester.verify_rules(
        config,
        [
            {
                "rule_name": "Ignore import statements",
                "source": "package com.foo\nimport java.util.*",
                "expected_symbol": None,
                "unexpected_symbol": "package_header",
            },
            {
                "rule_name": "Ignore comments",
                "source": "// line comment\n/* multi\nline */",
                "expected_symbol": None,
                "unexpected_symbol": "comment",
            },
            {
                "rule_name": "Anonymize function names",
                "source": "fun myFunc() {}",
                "expected_symbol": "FUNC",
                "unexpected_symbol": "myFunc",
            },
            {
                "rule_name": "Anonymize function names",
                "source": "fun String.myExtensionFunc() {}",
                "expected_symbol": "FUNC",
                "unexpected_symbol": "myExtensionFunc",
            },
            {
                "rule_name": "Anonymize function names",
                "source": "fun <T> myGenericFunc() {}",
                "expected_symbol": "FUNC",
                "unexpected_symbol": "myGenericFunc",
            },
            {
                "rule_name": "Anonymize class names",
                "source": "class MyClass {}",
                "expected_symbol": "CLASS",
                "unexpected_symbol": "MyClass",
            },
            {
                "rule_name": "Anonymize identifiers",
                "source": "val myVar = 1",
                "expected_symbol": "VAR_1",
                "unexpected_symbol": "myVar",
            },
            {
                "rule_name": "Anonymize literals",
                "source": 'val x = "hello" + 123 + 1.23 + true + null',
                "expected_symbol": "<LIT>",
                "unexpected_symbol": "hello",
            },
        ],
    )


def test_kotlin_rules_conflict():
    config = KotlinConfig()
    # Test that function name is FUNC even when Anonymize identifiers is present
    from treepeat.pipeline.rules.engine import RuleEngine
    from treepeat.pipeline.parse import parse_source_code
    from treepeat.pipeline.shingle import ASTShingler
    from treepeat.pipeline.region_extraction import ExtractedRegion
    from treepeat.models.similarity import Region
    from pathlib import Path

    rules = config.get_loose_rules()
    engine = RuleEngine(rules)
    source = "fun foo() {}"
    source_bytes = source.encode("utf-8")
    parsed = parse_source_code(source_bytes, "kotlin", Path("test.kt"))

    region = Region(
        path=Path("test.kt"),
        language="kotlin",
        region_type="test",
        region_name="test",
        start_line=1,
        end_line=1,
    )
    extracted = ExtractedRegion(region=region, node=parsed.root_node)

    shingler = ASTShingler(rule_engine=engine, k=1)
    engine.precompute_queries(extracted.node, "kotlin", source_bytes)
    shingled = shingler.shingle_region(extracted, source_bytes)

    tokens = shingled.shingles.get_contents()
    # Find the token for the function name. It should be simple_identifier(FUNC)
    # If the bug exists, it will be simple_identifier(VAR_1)
    assert "simple_identifier(FUNC)" in tokens
    assert "simple_identifier(VAR_1)" not in tokens


def test_kotlin_class_rules_conflict():
    config = KotlinConfig()
    from treepeat.pipeline.rules.engine import RuleEngine
    from treepeat.pipeline.parse import parse_source_code
    from treepeat.pipeline.shingle import ASTShingler
    from treepeat.pipeline.region_extraction import ExtractedRegion
    from treepeat.models.similarity import Region
    from pathlib import Path

    rules = config.get_loose_rules()
    engine = RuleEngine(rules)
    source = "class MyClass {}"
    source_bytes = source.encode("utf-8")
    parsed = parse_source_code(source_bytes, "kotlin", Path("test.kt"))

    region = Region(
        path=Path("test.kt"),
        language="kotlin",
        region_type="test",
        region_name="test",
        start_line=1,
        end_line=1,
    )
    extracted = ExtractedRegion(region=region, node=parsed.root_node)

    shingler = ASTShingler(rule_engine=engine, k=1)
    engine.precompute_queries(extracted.node, "kotlin", source_bytes)
    shingled = shingler.shingle_region(extracted, source_bytes)

    tokens = shingled.shingles.get_contents()
    # Find the token for the class name. It should be type_identifier(CLASS)
    assert "type_identifier(CLASS)" in tokens
