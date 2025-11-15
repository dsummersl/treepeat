"""JavaScript language configuration."""

from .base import LanguageConfig, RegionExtractionRule


class JavaScriptConfig(LanguageConfig):
    """Configuration for JavaScript language."""

    def get_language_name(self) -> str:
        return "javascript"

    def get_default_rules(self) -> list[str]:
        return [
            "javascript:skip:nodes=import_statement|export_statement",
            "javascript:skip:nodes=comment",
            "javascript:anonymize_identifiers:nodes=identifier,scheme=flat,prefix=VAR",
        ]

    def get_loose_rules(self) -> list[str]:
        return [
            *self.get_default_rules(),
            "javascript:replace_value:nodes=string|number|template_string,value=<LIT>",
            "javascript:replace_name:nodes=array|object,token=<COLL>",
            "javascript:replace_name:nodes=binary_expression|unary_expression|update_expression|assignment_expression|ternary_expression,token=<EXP>",
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            RegionExtractionRule(
                node_types=["function_declaration", "function", "arrow_function"],
                region_type="function",
            ),
            RegionExtractionRule(node_types=["method_definition"], region_type="method"),
            RegionExtractionRule(node_types=["class_declaration"], region_type="class"),
        ]
