"""Java language configuration."""

from .base import LanguageConfig, RegionExtractionRule


class JavaConfig(LanguageConfig):
    """Configuration for Java language."""

    def get_language_name(self) -> str:
        return "java"

    def get_default_rules(self) -> list[str]:
        return [
            "java:skip:nodes=import_declaration|package_declaration",
            "java:skip:nodes=comment|line_comment|block_comment",
            "java:anonymize_identifiers:nodes=identifier,scheme=flat,prefix=VAR",
        ]

    def get_loose_rules(self) -> list[str]:
        return [
            *self.get_default_rules(),
            "java:replace_value:nodes=string_literal|character_literal|decimal_integer_literal|hex_integer_literal|octal_integer_literal|binary_integer_literal|decimal_floating_point_literal|hex_floating_point_literal|true|false|null_literal,value=<LIT>",
            "java:replace_name:nodes=binary_expression|unary_expression|update_expression|assignment_expression|ternary_expression,token=<EXP>",
            "java:canonicalize_types:nodes=type_identifier|generic_type|array_type|integral_type|floating_point_type|boolean_type,token=<TYPE>",
            "java:replace_name:nodes=array_initializer|array_creation_expression,token=<COLL>",
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return []
