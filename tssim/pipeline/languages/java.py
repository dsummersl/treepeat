"""Java language configuration."""

from typing import TYPE_CHECKING

from .base import LanguageConfig, RegionExtractionRule

if TYPE_CHECKING:
    from tssim.pipeline.rules import Rule


class JavaConfig(LanguageConfig):
    """Configuration for Java language."""

    def get_language_name(self) -> str:
        return "java"

    def get_default_rules(self) -> list["Rule"]:
        from tssim.pipeline.rules import Rule, RuleAction

        return [
            Rule(
                name="Skip Java import/package declarations",
                languages=["java"],
                query="[(import_declaration) (package_declaration)] @import",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Skip Java comments",
                languages=["java"],
                query="[(comment) (line_comment) (block_comment)] @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize Java identifiers",
                languages=["java"],
                query="(identifier) @var",
                action=RuleAction.ANONYMIZE,
                params={"prefix": "VAR"},
            ),
        ]

    def get_loose_rules(self) -> list["Rule"]:
        from tssim.pipeline.rules import Rule, RuleAction

        return [
            *self.get_default_rules(),
            Rule(
                name="Replace Java literal values",
                languages=["java"],
                query="[(string_literal) (character_literal) (decimal_integer_literal) (hex_integer_literal) (octal_integer_literal) (binary_integer_literal) (decimal_floating_point_literal) (hex_floating_point_literal) (true) (false) (null_literal)] @lit",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<LIT>"},
            ),
            Rule(
                name="Replace Java expressions",
                languages=["java"],
                query="[(binary_expression) (unary_expression) (update_expression) (assignment_expression) (ternary_expression)] @exp",
                action=RuleAction.RENAME,
                params={"token": "<EXP>"},
            ),
            Rule(
                name="Canonicalize Java types",
                languages=["java"],
                query="[(type_identifier) (generic_type) (array_type) (integral_type) (floating_point_type) (boolean_type)] @type",
                action=RuleAction.CANONICALIZE,
                params={"token": "<TYPE>"},
            ),
            Rule(
                name="Replace Java collections",
                languages=["java"],
                query="[(array_initializer) (array_creation_expression)] @coll",
                action=RuleAction.RENAME,
                params={"token": "<COLL>"},
            ),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return []
