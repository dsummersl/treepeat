import pytest

from treepeat.pipeline.rules.parser import RuleParseError, _parse_yaml_rule


def test_parse_yaml_rule_rejects_wildcard_language() -> None:
    with pytest.raises(RuleParseError, match="Wildcard rule languages"):
        _parse_yaml_rule(
            {
                "name": "wildcard",
                "languages": ["*", "python"],
                "query": "(identifier) @id",
                "action": "remove",
            },
            "test",
        )
