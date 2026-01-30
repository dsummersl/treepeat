from treepeat.pipeline.languages.html import HTMLConfig


def test_html_rules_detailed(rule_tester):
    config = HTMLConfig()
    rule_tester.verify_rules(
        config,
        [
            {
                "rule_name": "Ignore comments",
                "source": "<!-- comment -->",
                "expected_symbol": None,
                "unexpected_symbol": "comment",
            },
            {
                "rule_name": "Anonymize tags",
                "source": "<div></div>",
                "expected_symbol": "<TAG>",
                "unexpected_symbol": "tag_name(div)",
            },
            {
                "rule_name": "Anonymize attributes",
                "source": '<div class="foo"></div>',
                "expected_symbol": "<ATTR>",
                "unexpected_symbol": "class",
            },
            {
                "rule_name": "Anonymize attribute values",
                "source": '<div class="foo"></div>',
                "expected_symbol": "<VAL>",
                "unexpected_symbol": "foo",
            },
            {
                "rule_name": "Ignore text content",
                "source": "<div>text content</div>",
                "expected_symbol": None,
                "unexpected_symbol": "text",
            },
        ],
    )
