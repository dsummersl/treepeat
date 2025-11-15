"""Go language configuration."""

from .base import LanguageConfig, RegionExtractionRule


class GoConfig(LanguageConfig):
    """Configuration for Go language."""

    def get_language_name(self) -> str:
        return "go"

    def get_default_rules(self) -> list[str]:
        return [
            "go:skip:nodes=import_declaration|package_clause",
            "go:skip:nodes=comment|line_comment|block_comment",
            "go:anonymize_identifiers:nodes=identifier,scheme=flat,prefix=VAR",
        ]

    def get_loose_rules(self) -> list[str]:
        return [
            *self.get_default_rules(),
            "go:replace_value:nodes=interpreted_string_literal|raw_string_literal|rune_literal|int_literal|float_literal|imaginary_literal|true|false|nil,value=<LIT>",
            "go:replace_name:nodes=binary_expression|unary_expression|assignment_expression,token=<EXP>",
            "go:canonicalize_types:nodes=type_identifier|pointer_type|array_type|slice_type|struct_type|interface_type|map_type|channel_type,token=<TYPE>",
            "go:replace_name:nodes=composite_literal|slice_literal,token=<COLL>",
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return []
