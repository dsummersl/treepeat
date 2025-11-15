"""SQL language configuration."""

from .base import LanguageConfig, RegionExtractionRule


class SQLConfig(LanguageConfig):
    """Configuration for SQL language."""

    def get_language_name(self) -> str:
        return "sql"

    def get_default_rules(self) -> list[str]:
        return [
            "sql:skip:nodes=comment|marginalia",
            "sql:anonymize_identifiers:nodes=identifier|object_reference,scheme=flat,prefix=VAR",
        ]

    def get_loose_rules(self) -> list[str]:
        return [
            *self.get_default_rules(),
            "sql:replace_value:nodes=string|number,value=<LIT>",
            "sql:replace_name:nodes=keyword,token=<KW>",
            "sql:replace_name:nodes=binary_expression|unary_expression,token=<EXP>",
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return []
