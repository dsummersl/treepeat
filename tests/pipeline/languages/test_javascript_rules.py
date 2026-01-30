from treepeat.pipeline.languages.javascript import JavaScriptConfig


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
