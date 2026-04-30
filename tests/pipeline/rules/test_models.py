import pytest

from treepeat.pipeline.rules.models import Rule


def test_rule_rejects_wildcard_language() -> None:
    with pytest.raises(ValueError, match="Wildcard rule languages"):
        Rule(name="wildcard", languages=["*", "python"], query="(identifier) @id")
