from treepeat.pipeline.rules.models import Rule, RuleAction

from .base import LanguageConfig, RegionExtractionRule


class JavaScriptConfig(LanguageConfig):
    """Configuration for JavaScript language."""

    def get_default_rules(self) -> list[Rule]:
        return [
            Rule(
                name="Ignore import/export statements",
                languages=["javascript", "typescript", "tsx"],
                query="[(import_statement) (export_statement)] @import",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Ignore comments",
                languages=["javascript", "typescript", "tsx"],
                query="[(comment) (hash_bang_line)] @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize identifiers",
                languages=["javascript", "typescript", "tsx"],
                query="[(identifier) (property_identifier)] @id",
                target="id",
                action=RuleAction.ANONYMIZE,
                params={"prefix": "VAR"},
            ),
            Rule(
                name="Anonymize function names",
                languages=["javascript", "typescript", "tsx"],
                query="[(function_declaration (identifier) @name) (method_definition (property_identifier) @name)]",
                target="name",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "FUNC"},
            ),
            Rule(
                name="Anonymize class names",
                languages=["javascript"],
                query="(class_declaration (identifier) @name)",
                target="name",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "CLASS"},
            ),
            Rule(
                name="Anonymize class names",
                languages=["typescript", "tsx"],
                query="(class_declaration (type_identifier) @name)",
                target="name",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "CLASS"},
            ),
        ]

    def get_loose_rules(self) -> list[Rule]:
        return [
            Rule(
                name="Anonymize literal values",
                languages=["javascript", "typescript", "tsx"],
                query="[(string) (number) (template_string)] @lit",
                target="lit",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<LIT>"},
            ),
            Rule(
                name="Anonymize collections",
                languages=["javascript", "typescript", "tsx"],
                query="[(array) (object)] @coll",
                target="coll",
                action=RuleAction.REPLACE_NODE_TYPE,
                params={"token": "<COLL>"},
            ),
            Rule(
                name="Anonymize expressions",
                languages=["javascript", "typescript", "tsx"],
                query=(
                    "[(binary_expression) (unary_expression) (update_expression) "
                    "(assignment_expression) (ternary_expression)] @exp"
                ),
                target="exp",
                action=RuleAction.REPLACE_NODE_TYPE,
                params={"token": "<EXP>"},
            ),
            *self.get_default_rules(),
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
