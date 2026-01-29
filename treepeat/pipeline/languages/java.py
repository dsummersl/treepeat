from treepeat.pipeline.rules.models import Rule, RuleAction
from .base import LanguageConfig, RegionExtractionRule


class JavaConfig(LanguageConfig):
    """Configuration for Java language."""

    def get_language_name(self) -> str:
        return "java"

    def get_default_rules(self) -> list[Rule]:
        return [
            Rule(
                name="Ignore import statements",
                languages=["java"],
                query="(import_declaration) @import",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Ignore comments",
                languages=["java"],
                query="[(line_comment) (block_comment)] @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize method names",
                languages=["java"],
                query="(method_declaration name: (identifier) @name)",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "METHOD"},
            ),
            Rule(
                name="Anonymize class names",
                languages=["java"],
                query="(class_declaration name: (identifier) @name)",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "CLASS"},
            ),
        ]

    def get_loose_rules(self) -> list[Rule]:
        return [
            *self.get_default_rules(),
            Rule(
                name="Anonymize identifiers",
                languages=["java"],
                query="(identifier) @id",
                action=RuleAction.ANONYMIZE,
                params={"prefix": "VAR"},
            ),
            Rule(
                name="Anonymize literals",
                languages=["java"],
                query="[(string_literal) (decimal_integer_literal) (decimal_floating_point_literal) (null_literal)] @lit",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<LIT>"},
            ),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            RegionExtractionRule.from_node_type("method_declaration"),
            RegionExtractionRule.from_node_type("class_declaration"),
        ]
