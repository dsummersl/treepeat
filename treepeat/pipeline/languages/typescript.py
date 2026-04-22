from .base import RegionExtractionRule
from .javascript import JavaScriptConfig


class TypeScriptConfig(JavaScriptConfig):
    """Configuration for TypeScript language (inherits from JavaScript)."""

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        # TypeScript grammar has no JSX node types; exclude JSX regions.
        return [
            RegionExtractionRule(
                query="[(function_declaration) (function_expression) (arrow_function)] @region",
                label="function",
            ),
            RegionExtractionRule.from_node_type("method_definition"),
            RegionExtractionRule.from_node_type("class_declaration"),
        ]
