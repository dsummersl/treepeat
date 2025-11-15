"""Go language configuration."""

from typing import TYPE_CHECKING

from .base import LanguageConfig, RegionExtractionRule

if TYPE_CHECKING:
    from tssim.pipeline.rules import Rule


class GoConfig(LanguageConfig):
    """Configuration for Go language."""

    def get_language_name(self) -> str:
        return "go"

    def get_default_rules(self) -> list["Rule"]:
        from tssim.pipeline.rules import Rule, RuleAction

        return [
            Rule(
                name="Skip Go import/package declarations",
                languages=["go"],
                query="[(import_declaration) (package_clause)] @import",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Skip Go comments",
                languages=["go"],
                query="[(comment) (line_comment) (block_comment)] @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize Go identifiers",
                languages=["go"],
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
                name="Replace Go literal values",
                languages=["go"],
                query="[(interpreted_string_literal) (raw_string_literal) (rune_literal) (int_literal) (float_literal) (imaginary_literal) (true) (false) (nil)] @lit",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<LIT>"},
            ),
            Rule(
                name="Replace Go expressions",
                languages=["go"],
                query="[(binary_expression) (unary_expression) (assignment_expression)] @exp",
                action=RuleAction.RENAME,
                params={"token": "<EXP>"},
            ),
            Rule(
                name="Canonicalize Go types",
                languages=["go"],
                query="[(type_identifier) (pointer_type) (array_type) (slice_type) (struct_type) (interface_type) (map_type) (channel_type)] @type",
                action=RuleAction.CANONICALIZE,
                params={"token": "<TYPE>"},
            ),
            Rule(
                name="Replace Go collections",
                languages=["go"],
                query="[(composite_literal) (slice_literal)] @coll",
                action=RuleAction.RENAME,
                params={"token": "<COLL>"},
            ),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return []
