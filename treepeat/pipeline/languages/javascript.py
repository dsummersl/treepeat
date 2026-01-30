from treepeat.pipeline.rules.models import Rule, RuleAction

from .base import LanguageConfig, RegionExtractionRule


class JavaScriptConfig(LanguageConfig):
    """Configuration for JavaScript language."""

    def get_language_name(self) -> str:
        return "javascript"

    def get_default_rules(self) -> list[Rule]:
        return [
            Rule(
                name="Ignore import/export statements",
                languages=["javascript"],
                query="[(import_statement) (export_statement)] @import",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Ignore comments",
                languages=["javascript"],
                query="(comment) @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize function names",
                languages=["javascript"],
                query="[(function_declaration name: (identifier) @name) (method_definition name: (property_identifier) @name)]",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "FUNC"},
            ),
            Rule(
                name="Anonymize class names",
                languages=["javascript"],
                query="(class_declaration name: (identifier) @name)",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "CLASS"},
            ),
            Rule(
                name="Anonymize identifiers",
                languages=["javascript"],
                query="(identifier) @var",
                action=RuleAction.ANONYMIZE,
                params={"prefix": "VAR"},
            ),
        ]

    def get_loose_rules(self) -> list[Rule]:
        return [
            *self.get_default_rules(),
            Rule(
                name="Anonymize literal values",
                languages=["javascript"],
                query="[(string) (number) (template_string)] @lit",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<LIT>"},
            ),
            Rule(
                name="Anonymize collections",
                languages=["javascript"],
                query="[(array) (object)] @coll",
                action=RuleAction.RENAME,
                params={"token": "<COLL>"},
            ),
            Rule(
                name="Anonymize expressions",
                languages=["javascript"],
                query="[(binary_expression) (unary_expression) (update_expression) (assignment_expression) (ternary_expression)] @exp",
                action=RuleAction.RENAME,
                params={"token": "<EXP>"},
            ),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            RegionExtractionRule(
                query="[(function_declaration) (function_expression) (arrow_function)] @region",
                label="function",
            ),
            RegionExtractionRule.from_node_type("method_definition"),
            RegionExtractionRule.from_node_type("class_declaration"),
        ]
