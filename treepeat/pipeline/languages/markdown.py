from treepeat.pipeline.rules.models import Rule

from .base import LanguageConfig, RegionExtractionRule


class MarkdownConfig(LanguageConfig):
    """Configuration for Markdown language."""

    def get_language_name(self) -> str:
        return "markdown"

    def get_default_rules(self) -> list[Rule]:
        return []

    def get_loose_rules(self) -> list[Rule]:
        return []

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            RegionExtractionRule(
                query="[(atx_heading) (setext_heading) (section)] @region",
                label="heading",
            ),
            RegionExtractionRule(
                query="[(fenced_code_block) (indented_code_block)] @region",
                label="code_block",
            ),
        ]
