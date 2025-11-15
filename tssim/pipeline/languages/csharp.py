"""C# language configuration."""

from tssim.pipeline.rules.models import Rule, RuleAction

from .base import LanguageConfig, RegionExtractionRule


class CSharpConfig(LanguageConfig):
    """Configuration for C# language."""

    def get_language_name(self) -> str:
        return "csharp"

    def get_default_rules(self) -> list[Rule]:
        return [
            Rule(
                name="Skip C# using directives",
                languages=["csharp"],
                query="(using_directive) @import",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Skip C# comments",
                languages=["csharp"],
                query="(comment) @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize C# identifiers",
                languages=["csharp"],
                query="(identifier) @var",
                action=RuleAction.ANONYMIZE,
                params={"prefix": "VAR"},
            ),
        ]

    def get_loose_rules(self) -> list[Rule]:
        return [
            *self.get_default_rules(),
            Rule(
                name="Replace C# literal values",
                languages=["csharp"],
                query="[(string_literal) (verbatim_string_literal) (character_literal) (integer_literal) (real_literal) (boolean_literal) (null_literal)] @lit",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<LIT>"},
            ),
            Rule(
                name="Replace C# expressions",
                languages=["csharp"],
                query="[(binary_expression) (prefix_unary_expression) (postfix_unary_expression) (assignment_expression) (conditional_expression)] @exp",
                action=RuleAction.RENAME,
                params={"token": "<EXP>"},
            ),
            Rule(
                name="Canonicalize C# types",
                languages=["csharp"],
                query="[(type_identifier) (predefined_type) (array_type) (nullable_type) (pointer_type)] @type",
                action=RuleAction.CANONICALIZE,
                params={"token": "<TYPE>"},
            ),
            Rule(
                name="Replace C# collections",
                languages=["csharp"],
                query="[(array_creation_expression) (initializer_expression)] @coll",
                action=RuleAction.RENAME,
                params={"token": "<COLL>"},
            ),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return []
