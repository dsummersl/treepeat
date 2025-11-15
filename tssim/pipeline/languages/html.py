"""HTML language configuration."""

from .base import LanguageConfig, RegionExtractionRule


class HTMLConfig(LanguageConfig):
    """Configuration for HTML language."""

    def get_language_name(self) -> str:
        return "html"

    def get_default_rules(self) -> list[str]:
        return [
            "html:skip:nodes=comment",
        ]

    def get_loose_rules(self) -> list[str]:
        return [
            *self.get_default_rules(),
            "html:replace_value:nodes=attribute_value|text,value=<LIT>",
            "html:replace_name:nodes=element|tag_name,token=<TAG>",
            "html:replace_name:nodes=attribute_name,token=<ATTR>",
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return []
