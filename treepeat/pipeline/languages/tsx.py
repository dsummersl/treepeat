from .base import RegionExtractionRule
from .typescript import TypeScriptConfig


class TsxConfig(TypeScriptConfig):
    """Configuration for TSX language (inherits from TypeScript)."""

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            *super().get_region_extraction_rules(),
            RegionExtractionRule(
                query="(jsx_element (jsx_expression) @region)",
                label="jsx_expression",
            ),
        ]
