from .base import RegionExtractionRule
from .javascript import JavaScriptConfig


class JsxConfig(JavaScriptConfig):
    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            *super().get_region_extraction_rules(),
            RegionExtractionRule(
                query="(jsx_element (jsx_expression) @region)",
                label="jsx_expression",
            ),
        ]
