from treepeat.pipeline.rules.models import Rule, RuleAction

from .base import LanguageConfig, RegionExtractionRule


class AstroConfig(LanguageConfig):
    """Configuration for Astro (.astro) components.

    Astro files consist of an optional TypeScript/JavaScript *frontmatter* block
    (delimited by ``---`` on the first and last line) followed by an HTML-like
    template.  The frontmatter is declared as a language-injection region so
    that the shingler re-parses it as TypeScript and applies full TypeScript
    normalization rules.  This ensures that identical TypeScript code in an
    ``.astro`` file produces the same shingle hashes as the same code in a
    ``.ts`` file, enabling cross-file similarity detection.
    """

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
            # The frontmatter block is re-parsed as TypeScript via language
            # injection so that the shingler applies TypeScript rules.
            # content_query targets the opaque frontmatter_js_block child
            # (which holds the raw TypeScript bytes) rather than the wrapper
            # frontmatter node that also contains the --- delimiters.
            RegionExtractionRule(
                query="(frontmatter) @region",
                label="frontmatter",
                target_language="typescript",
                content_query="(frontmatter_js_block) @content",
            ),
            # Each top-level element in the document is the HTML template
            # (or the entire file content for template-only components).
            # Shingled with the Astro grammar so that Astro normalisation rules
            # (comment removal, tag/attr anonymisation) apply, enabling
            # structural similarity detection across Astro templates.
            RegionExtractionRule(
                query="(document (element) @region)",
                label="template",
            ),
        ]
