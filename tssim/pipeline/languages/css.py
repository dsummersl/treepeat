"""CSS language configuration."""

from .base import LanguageConfig, RegionExtractionRule


class CSSConfig(LanguageConfig):
    """Configuration for CSS language."""

    def get_language_name(self) -> str:
        return "css"

    def get_default_rules(self) -> list[str]:
        return [
            "css:skip:nodes=comment",
            "css:anonymize_identifiers:nodes=class_name|id_name|tag_name,scheme=flat,prefix=SEL",
        ]

    def get_loose_rules(self) -> list[str]:
        return [
            *self.get_default_rules(),
            "css:replace_value:nodes=string_value|integer_value|float_value|color_value|plain_value,value=<LIT>",
            "css:replace_name:nodes=property_name,token=<PROP>",
            "css:replace_name:nodes=feature_name,token=<FEAT>",
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return []
