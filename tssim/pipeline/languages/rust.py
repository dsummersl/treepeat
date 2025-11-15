"""Rust language configuration."""

from typing import TYPE_CHECKING

from .base import LanguageConfig, RegionExtractionRule

if TYPE_CHECKING:
    from tssim.pipeline.rules import Rule


class RustConfig(LanguageConfig):
    """Configuration for Rust language."""

    def get_language_name(self) -> str:
        return "rust"

    def get_default_rules(self) -> list["Rule"]:
        from tssim.pipeline.rules import Rule, RuleAction

        return [
            Rule(
                name="Skip Rust use declarations",
                languages=["rust"],
                query="(use_declaration) @import",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Skip Rust comments",
                languages=["rust"],
                query="[(line_comment) (block_comment)] @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize Rust identifiers",
                languages=["rust"],
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
                name="Replace Rust literal values",
                languages=["rust"],
                query="[(string_literal) (raw_string_literal) (char_literal) (integer_literal) (float_literal) (boolean_literal)] @lit",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<LIT>"},
            ),
            Rule(
                name="Replace Rust expressions",
                languages=["rust"],
                query="[(binary_expression) (unary_expression) (assignment_expression)] @exp",
                action=RuleAction.RENAME,
                params={"token": "<EXP>"},
            ),
            Rule(
                name="Canonicalize Rust types",
                languages=["rust"],
                query="[(type_identifier) (generic_type) (array_type) (reference_type) (pointer_type) (tuple_type) (primitive_type)] @type",
                action=RuleAction.CANONICALIZE,
                params={"token": "<TYPE>"},
            ),
            Rule(
                name="Replace Rust collections",
                languages=["rust"],
                query="[(array_expression) (struct_expression)] @coll",
                action=RuleAction.RENAME,
                params={"token": "<COLL>"},
            ),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return []
