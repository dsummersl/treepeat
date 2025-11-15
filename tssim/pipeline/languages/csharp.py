"""C# language configuration."""

from .base import LanguageConfig, RegionExtractionRule


class CSharpConfig(LanguageConfig):
    """Configuration for C# language."""

    def get_language_name(self) -> str:
        return "csharp"

    def get_default_rules(self) -> list[str]:
        return [
            "csharp:skip:nodes=using_directive",
            "csharp:skip:nodes=comment",
            "csharp:anonymize_identifiers:nodes=identifier,scheme=flat,prefix=VAR",
        ]

    def get_loose_rules(self) -> list[str]:
        return [
            *self.get_default_rules(),
            "csharp:replace_value:nodes=string_literal|verbatim_string_literal|character_literal|integer_literal|real_literal|boolean_literal|null_literal,value=<LIT>",
            "csharp:replace_name:nodes=binary_expression|prefix_unary_expression|postfix_unary_expression|assignment_expression|conditional_expression,token=<EXP>",
            "csharp:canonicalize_types:nodes=type_identifier|predefined_type|array_type|nullable_type|pointer_type,token=<TYPE>",
            "csharp:replace_name:nodes=array_creation_expression|initializer_expression,token=<COLL>",
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return []
