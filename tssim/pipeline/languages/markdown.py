"""Markdown language configuration."""

from typing import TYPE_CHECKING

from .base import LanguageConfig, RegionExtractionRule

if TYPE_CHECKING:
    from tssim.pipeline.rules import Rule


class MarkdownConfig(LanguageConfig):
    """Configuration for Markdown language."""

    def get_language_name(self) -> str:
        return "markdown"

    def get_default_rules(self) -> list["Rule"]:
        return []

    def get_loose_rules(self) -> list["Rule"]:
        return []

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            RegionExtractionRule(
                node_types=["atx_heading", "setext_heading", "section"],
                region_type="heading",
            ),
            RegionExtractionRule(
                node_types=["fenced_code_block", "indented_code_block"],
                region_type="code_block",
            ),
        ]
