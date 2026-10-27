from treepeat.pipeline.rules.models import Rule, RuleAction

from .base import LanguageConfig, RegionExtractionRule


class AstroConfig(LanguageConfig):


    def get_default_rules(self) -> list[Rule]:
        return [
            Rule(
                name="Ignore Astro/HTML comments",
                languages=["astro"],
                query="(comment) @comment",
                action=RuleAction.REMOVE,
            ),
        ]

    def get_loose_rules(self) -> list[Rule]:
        return [
            *self.get_default_rules(),
            Rule(
                name="Anonymize tag names",
                languages=["astro"],
                query="(tag_name) @tag",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<TAG>"},
            ),
            Rule(
                name="Anonymize attribute names",
                languages=["astro"],
                query="(attribute_name) @attr",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<ATTR>"},
            ),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [





            RegionExtractionRule(
                query="(frontmatter) @region",
                label="frontmatter",
                target_language="typescript",
                content_query="(frontmatter_js_block) @content",
            ),





            RegionExtractionRule(
                query="(document (element) @region)",
                label="template",
            ),
        ]
