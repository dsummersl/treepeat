from treepeat.pipeline.rules.models import Rule, RuleAction

from .base import LanguageConfig, RegionExtractionRule


class GoConfig(LanguageConfig):
    """Configuration for Go language."""

    def get_language_name(self) -> str:
        return "go"

    def get_default_rules(self) -> list[Rule]:
        return [
            Rule(
                name="Ignore import declarations",
                languages=["go"],
                query="(import_declaration) @import",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Ignore package clause",
                languages=["go"],
                query="(package_clause) @package",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Ignore comments",
                languages=["go"],
                query="(comment) @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize function names",
                languages=["go"],
                query="(function_declaration name: (identifier) @func)",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "FUNC"},
            ),
            Rule(
                name="Anonymize method names",
                languages=["go"],
                query="(method_declaration name: (field_identifier) @method)",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "METHOD"},
            ),
            Rule(
                name="Anonymize type names",
                languages=["go"],
                query="(type_declaration (type_spec name: (type_identifier) @type))",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "TYPE"},
            ),
        ]

    def get_loose_rules(self) -> list[Rule]:
        return [
            *self.get_default_rules(),
            Rule(
                name="Anonymize string literals",
                languages=["go"],
                query="[(interpreted_string_literal) (raw_string_literal)] @str",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<STR>"},
            ),
            Rule(
                name="Anonymize numeric literals",
                languages=["go"],
                query="[(int_literal) (float_literal) (imaginary_literal) (rune_literal)] @num",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<NUM>"},
            ),
            Rule(
                name="Anonymize identifiers",
                languages=["go"],
                query="(identifier) @var",
                action=RuleAction.ANONYMIZE,
                params={"prefix": "VAR"},
            ),
            Rule(
                name="Anonymize field identifiers",
                languages=["go"],
                query="(field_identifier) @field",
                action=RuleAction.ANONYMIZE,
                params={"prefix": "FIELD"},
            ),
            Rule(
                name="Anonymize binary expressions",
                languages=["go"],
                query="(binary_expression) @binop",
                action=RuleAction.RENAME,
                params={"token": "<BINOP>"},
            ),
            Rule(
                name="Anonymize unary expressions",
                languages=["go"],
                query="(unary_expression) @unop",
                action=RuleAction.RENAME,
                params={"token": "<UNOP>"},
            ),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            RegionExtractionRule.from_node_type("function_declaration"),
            RegionExtractionRule.from_node_type("method_declaration"),
            RegionExtractionRule.from_node_type("type_declaration"),
        ]
