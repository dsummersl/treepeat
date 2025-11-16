"""CSS language configuration."""

from whorl.pipeline.rules.models import Rule, RuleAction

from .base import LanguageConfig, RegionExtractionRule


class CSSConfig(LanguageConfig):
    """Configuration for CSS language."""

    def get_language_name(self) -> str:
        return "css"

    def get_default_rules(self) -> list[Rule]:
        return [
            Rule(
                name="Skip CSS comments",
                languages=["css"],
                query="(comment) @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize CSS selectors",
                languages=["css"],
                query="[(class_name) (id_name) (tag_name)] @sel",
                action=RuleAction.ANONYMIZE,
                params={"prefix": "SEL"},
            ),
        ]

    def get_loose_rules(self) -> list[Rule]:
        return [
            *self.get_default_rules(),
            Rule(
                name="Replace CSS literal values",
                languages=["css"],
                query="[(string_value) (integer_value) (float_value) (color_value) (plain_value)] @lit",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<LIT>"},
            ),
            Rule(
                name="Replace CSS properties",
                languages=["css"],
                query="(property_name) @prop",
                action=RuleAction.RENAME,
                params={"token": "<PROP>"},
            ),
            Rule(
                name="Replace CSS features",
                languages=["css"],
                query="(feature_name) @feat",
                action=RuleAction.RENAME,
                params={"token": "<FEAT>"},
            ),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
        ]
