from treepeat.pipeline.rules.models import Rule, RuleAction

from .base import LanguageConfig, RegionExtractionRule


class CSSConfig(LanguageConfig):
    """Configuration for CSS language."""

    def get_language_name(self) -> str:
        return "css"

    def get_default_rules(self) -> list[Rule]:
        return [
            Rule(
                name="Ignore comments",
                languages=["css"],
                query="(comment) @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize selectors",
                languages=["css"],
                query="[(class_name) (id_name) (tag_name)] @sel",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "SEL"},
            ),
        ]

    def get_loose_rules(self) -> list[Rule]:
        return [
            *self.get_default_rules(),
            Rule(
                name="Anonymize literal values",
                languages=["css"],
                query="[(string_value) (integer_value) (float_value) (color_value) (plain_value)] @lit",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<LIT>"},
            ),
            Rule(
                name="Anonymize properties",
                languages=["css"],
                query="(property_name) @prop",
                action=RuleAction.RENAME,
                params={"token": "<PROP>"},
            ),
            Rule(
                name="Anonymize features",
                languages=["css"],
                query="(feature_name) @feat",
                action=RuleAction.RENAME,
                params={"token": "<FEAT>"},
            ),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            RegionExtractionRule.from_node_type("rule_set"),
            RegionExtractionRule.from_node_type("media_statement"),
            RegionExtractionRule.from_node_type("keyframes_statement"),
        ]
