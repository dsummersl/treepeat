"""SQL language configuration."""

from typing import TYPE_CHECKING

from .base import LanguageConfig, RegionExtractionRule

if TYPE_CHECKING:
    from tssim.pipeline.rules import Rule


class SQLConfig(LanguageConfig):
    """Configuration for SQL language."""

    def get_language_name(self) -> str:
        return "sql"

    def get_default_rules(self) -> list["Rule"]:
        from tssim.pipeline.rules import Rule, RuleAction

        return [
            Rule(
                name="Skip SQL comments",
                languages=["sql"],
                query="[(comment) (marginalia)] @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize SQL identifiers",
                languages=["sql"],
                query="[(identifier) (object_reference)] @var",
                action=RuleAction.ANONYMIZE,
                params={"prefix": "VAR"},
            ),
        ]

    def get_loose_rules(self) -> list["Rule"]:
        from tssim.pipeline.rules import Rule, RuleAction

        return [
            *self.get_default_rules(),
            Rule(
                name="Replace SQL literal values",
                languages=["sql"],
                query="[(string) (number)] @lit",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<LIT>"},
            ),
            Rule(
                name="Replace SQL keywords",
                languages=["sql"],
                query="(keyword) @kw",
                action=RuleAction.RENAME,
                params={"token": "<KW>"},
            ),
            Rule(
                name="Replace SQL expressions",
                languages=["sql"],
                query="[(binary_expression) (unary_expression)] @exp",
                action=RuleAction.RENAME,
                params={"token": "<EXP>"},
            ),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return []
