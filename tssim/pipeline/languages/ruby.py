"""Ruby language configuration."""

from tssim.pipeline.rules.models import Rule, RuleAction

from .base import LanguageConfig, RegionExtractionRule


class RubyConfig(LanguageConfig):
    """Configuration for Ruby language."""

    def get_language_name(self) -> str:
        return "ruby"

    def get_default_rules(self) -> list[Rule]:
        return [
            Rule(
                name="Skip Ruby comments",
                languages=["ruby"],
                query="(comment) @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize Ruby identifiers",
                languages=["ruby"],
                query="[(identifier) (constant)] @var",
                action=RuleAction.ANONYMIZE,
                params={"prefix": "VAR"},
            ),
        ]

    def get_loose_rules(self) -> list[Rule]:
        return [
            *self.get_default_rules(),
            Rule(
                name="Replace Ruby literal values",
                languages=["ruby"],
                query="[(string) (string_content) (integer) (float) (simple_symbol) (hash_key_symbol) (true) (false) (nil)] @lit",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<LIT>"},
            ),
            Rule(
                name="Replace Ruby expressions",
                languages=["ruby"],
                query="[(binary) (unary) (assignment)] @exp",
                action=RuleAction.RENAME,
                params={"token": "<EXP>"},
            ),
            Rule(
                name="Replace Ruby collections",
                languages=["ruby"],
                query="[(array) (hash)] @coll",
                action=RuleAction.RENAME,
                params={"token": "<COLL>"},
            ),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return []
