from treepeat.pipeline.rules.models import Rule, RuleAction
from .base import LanguageConfig, RegionExtractionRule


class KotlinConfig(LanguageConfig):
    """Configuration for Kotlin language."""

    def get_language_name(self) -> str:
        return "kotlin"

    def get_default_rules(self) -> list[Rule]:
        return [
            Rule(
                name="Ignore import statements",
                languages=["kotlin"],
                query="[(import_header) (package_header)] @import",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Ignore comments",
                languages=["kotlin"],
                query="[(line_comment) (multiline_comment)] @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize function names",
                languages=["kotlin"],
                query="(function_declaration (simple_identifier) @name)",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "FUNC"},
            ),
            Rule(
                name="Anonymize class names",
                languages=["kotlin"],
                query="(class_declaration (type_identifier) @name)",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "CLASS"},
            ),
        ]

    def get_loose_rules(self) -> list[Rule]:
        return [
            Rule(
                name="Anonymize identifiers",
                languages=["kotlin"],
                query="[(simple_identifier) (interpolated_identifier)] @id",
                action=RuleAction.ANONYMIZE,
                params={"prefix": "VAR"},
            ),
            Rule(
                name="Anonymize literals",
                languages=["kotlin"],
                query="[(string_literal) (string_content) (integer_literal) (real_literal) (boolean_literal) (null_literal)] @lit",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<LIT>"},
            ),
            *self.get_default_rules(),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            RegionExtractionRule.from_node_type("function_declaration"),
            RegionExtractionRule.from_node_type("class_declaration"),
        ]
