"""HTML language configuration."""

from typing import TYPE_CHECKING

from .base import LanguageConfig, RegionExtractionRule

if TYPE_CHECKING:
    from tssim.pipeline.rules import Rule


class HTMLConfig(LanguageConfig):
    """Configuration for HTML language."""

    def get_language_name(self) -> str:
        return "html"

    def get_default_rules(self) -> list["Rule"]:
        from tssim.pipeline.rules import Rule, RuleAction

        return [
            Rule(
                name="Skip HTML comments",
                languages=["html"],
                query="(comment) @comment",
                action=RuleAction.REMOVE,
            ),
        ]

    def get_loose_rules(self) -> list["Rule"]:
        from tssim.pipeline.rules import Rule, RuleAction

        return [
            *self.get_default_rules(),
            Rule(
                name="Replace HTML literal values",
                languages=["html"],
                query="[(attribute_value) (text)] @lit",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<LIT>"},
            ),
            Rule(
                name="Replace HTML tags",
                languages=["html"],
                query="[(element) (tag_name)] @tag",
                action=RuleAction.RENAME,
                params={"token": "<TAG>"},
            ),
            Rule(
                name="Replace HTML attributes",
                languages=["html"],
                query="(attribute_name) @attr",
                action=RuleAction.RENAME,
                params={"token": "<ATTR>"},
            ),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return []
