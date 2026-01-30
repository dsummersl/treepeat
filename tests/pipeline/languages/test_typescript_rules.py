from treepeat.pipeline.languages.typescript import TypeScriptConfig


def test_typescript_rules_detailed(rule_tester):
    # TypeScript inherits all rules from JavaScript
    config = TypeScriptConfig()
    rule_tester.verify_rules(
        config,
        [
            {
                "rule_name": "Ignore import/export statements",
                "source": "import { T } from './types';\nexport type { T };",
                "expected_symbol": None,
                "unexpected_symbol": "import_statement",
            },
            {
                "rule_name": "Ignore comments",
                "source": "// ts comment",
                "expected_symbol": None,
                "unexpected_symbol": "comment",
            },
            {
                "rule_name": "Anonymize function names",
                "source": "function tsFunc() {}",
                "expected_symbol": "identifier(FUNC)",
                "unexpected_symbol": "tsFunc",
            },
            {
                "rule_name": "Anonymize class names",
                "source": "class TsClass {}",
                "expected_symbol": "type_identifier(CLASS)",
                "unexpected_symbol": "TsClass",
            },
            {
                "rule_name": "Anonymize identifiers",
                "source": "const tsVar = 1;",
                "expected_symbol": "identifier(VAR_1)",
                "unexpected_symbol": "tsVar",
            },
            {
                "rule_name": "Anonymize literal values",
                "source": "const n = 42;",
                "expected_symbol": "number(<LIT>)",
                "unexpected_symbol": "42",
            },
            {
                "rule_name": "Anonymize collections",
                "source": "const arr = [];",
                "expected_symbol": "<COLL>",
                "unexpected_symbol": "array",
            },
            {
                "rule_name": "Anonymize expressions",
                "source": "const sum = a + b;",
                "expected_symbol": "<EXP>",
                "unexpected_symbol": "binary_expression",
            },
        ],
    )
