from treepeat.pipeline.languages.bash import BashConfig


def test_bash_rules_detailed(rule_tester):
    config = BashConfig()
    rule_tester.verify_rules(
        config,
        [
            {
                "rule_name": "Ignore comments",
                "source": "# comment",
                "expected_symbol": None,
                "unexpected_symbol": "comment",
            },
            {
                "rule_name": "Anonymize function names",
                "source": "my_func() { echo hi; }",
                "expected_symbol": "word(FUNC)",
                "unexpected_symbol": "my_func",
            },
            {
                "rule_name": "Anonymize commands",
                "source": "ls -la",
                "expected_symbol": "<CMD>",
                "unexpected_symbol": "command_name",
            },
            {
                "rule_name": "Anonymize variables",
                "source": "$VAR",
                "expected_symbol": "variable_name(<VAR>)",
                "unexpected_symbol": None,
            },
            {
                "rule_name": "Anonymize expressions",
                "source": "[[ $a == $b ]]",
                "expected_symbol": "<EXP>",
                "unexpected_symbol": "binary_expression",
            },
            {
                "rule_name": "Anonymize strings",
                "source": 'echo "hello"',
                "expected_symbol": "<STR>",
                "unexpected_symbol": "hello",
            },
            {
                "rule_name": "Anonymize numbers",
                "source": "x=123",
                "expected_symbol": "<NUM>",
                "unexpected_symbol": "123",
            },
        ],
    )
