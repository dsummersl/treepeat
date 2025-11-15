"""Python language configuration."""

from .base import LanguageConfig, RegionExtractionRule


class PythonConfig(LanguageConfig):
    """Configuration for Python language."""

    def get_language_name(self) -> str:
        return "python"

    def get_default_rules(self) -> list[str]:
        return [
            "python:skip:nodes=import_statement|import_from_statement",
            "python:skip:nodes=comment",
            "python:anonymize_identifiers:nodes=identifier,scheme=flat,prefix=VAR",
        ]

    def get_loose_rules(self) -> list[str]:
        return [
            *self.get_default_rules(),
            "python:replace_value:nodes=string|integer|float|number|template_string|true|false|none|null|undefined,value=<LIT>",
            "python:replace_name:nodes=binary_operator|boolean_operator|comparison_operator|unary_operator,token=<OP>",
            "python:canonicalize_types:nodes=type",
            "python:replace_name:nodes=list|dictionary|tuple|set,token=<COLL>",
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            RegionExtractionRule(node_types=["function_definition"], region_type="function"),
            RegionExtractionRule(node_types=["class_definition"], region_type="class"),
        ]
