"""Markdown language configuration."""

from whorl.pipeline.rules.models import Rule

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
                region_type="heading",
            ),
            RegionExtractionRule(
                query="[(fenced_code_block) (indented_code_block)] @region",
                region_type="code_block",
            ),
        ]
