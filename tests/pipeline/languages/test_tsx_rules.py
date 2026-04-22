from treepeat.pipeline.languages.tsx import TsxConfig


def test_tsx_rules_detailed(rule_tester):
    # TSX inherits all rules from TypeScript (which inherits from JavaScript)
    config = TsxConfig()
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
                "source": "// tsx comment",
                "expected_symbol": None,
                "unexpected_symbol": "comment",
            },
            {
                "rule_name": "Anonymize function names",
                "source": "function MyComponent() { return null; }",
                "expected_symbol": "identifier(FUNC)",
                "unexpected_symbol": "MyComponent",
            },
            {
                "rule_name": "Anonymize class names",
                "source": "class TsxClass {}",
                "expected_symbol": "type_identifier(CLASS)",
                "unexpected_symbol": "TsxClass",
            },
            {
                "rule_name": "Anonymize identifiers",
                "source": "const tsxVar = 1;",
                "expected_symbol": "identifier(VAR_1)",
                "unexpected_symbol": "tsxVar",
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
