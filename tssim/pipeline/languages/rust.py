"""Rust language configuration."""

from .base import LanguageConfig, RegionExtractionRule


class RustConfig(LanguageConfig):
    """Configuration for Rust language."""

    def get_language_name(self) -> str:
        return "rust"

    def get_default_rules(self) -> list[str]:
        return [
            "rust:skip:nodes=use_declaration",
            "rust:skip:nodes=line_comment|block_comment",
            "rust:anonymize_identifiers:nodes=identifier,scheme=flat,prefix=VAR",
        ]

    def get_loose_rules(self) -> list[str]:
        return [
            *self.get_default_rules(),
            "rust:replace_value:nodes=string_literal|raw_string_literal|char_literal|integer_literal|float_literal|boolean_literal,value=<LIT>",
            "rust:replace_name:nodes=binary_expression|unary_expression|assignment_expression,token=<EXP>",
            "rust:canonicalize_types:nodes=type_identifier|generic_type|array_type|reference_type|pointer_type|tuple_type|primitive_type,token=<TYPE>",
            "rust:replace_name:nodes=array_expression|struct_expression,token=<COLL>",
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return []
