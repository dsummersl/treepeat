from treepeat.pipeline.rules.models import Rule, RuleAction

from .base import LanguageConfig, RegionExtractionRule


class HTMLConfig(LanguageConfig):
    """Configuration for HTML language."""

    def get_language_name(self) -> str:
        return "html"

    def get_default_rules(self) -> list[Rule]:
        return [
            Rule(
                name="Ignore comments",
                languages=["html"],
                query="(comment) @comment",
                action=RuleAction.REMOVE,
            ),
        ]

    def get_loose_rules(self) -> list[Rule]:
        return [
            *self.get_default_rules(),
            Rule(
                name="Anonymize tags",
                languages=["html"],
                query="[(element) (tag_name)] @tag",
                action=RuleAction.REPLACE_NODE_TYPE,
                params={"token": "<TAG>"},
            ),
            Rule(
                name="Anonymize attributes",
                languages=["html"],
                query="(attribute_name) @attr",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<ATTR>"},
            ),
            Rule(
                name="Anonymize attribute values",
                languages=["html"],
                query="(attribute_value) @val",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<VAL>"},
            ),
            Rule(
                name="Ignore text content",
                languages=["html"],
                query="(text) @text",
                action=RuleAction.REMOVE,
            ),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            RegionExtractionRule(
                query='(element (start_tag (tag_name) @tag_name) (#eq? @tag_name "head")) @region',
                label="head",
            ),
            RegionExtractionRule(
                query='(element (start_tag (tag_name) @tag_name) (#eq? @tag_name "body")) @region',
                label="body",
            ),
        ]
