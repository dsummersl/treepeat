"""SQL language configuration."""

from treepeat.pipeline.rules.models import Rule, RuleAction

from .base import LanguageConfig, RegionExtractionRule


class SQLConfig(LanguageConfig):
    """Configuration for SQL language."""

    def get_language_name(self) -> str:
        return "sql"

    def get_default_rules(self) -> list[Rule]:
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

    def get_loose_rules(self) -> list[Rule]:
        return [
            *self.get_default_rules(),
            Rule(
                name="Replace SQL literal values",
                languages=["sql"],
                query="(literal) @lit",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<LIT>"},
            ),
            # Note: SQL grammar doesn't have a generic (keyword) node type
            # Keywords are specific types like keyword_insert, keyword_into, etc.
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
