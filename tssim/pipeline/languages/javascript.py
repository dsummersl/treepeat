"""JavaScript language configuration."""

from tssim.pipeline.rules.models import Rule, RuleAction

from .base import LanguageConfig, RegionExtractionRule


class JavaScriptConfig(LanguageConfig):
    """Configuration for JavaScript language."""

    def get_language_name(self) -> str:
        return "javascript"

    def get_default_rules(self) -> list[Rule]:

        return [
            Rule(
                name="Skip JavaScript import/export statements",
                languages=["javascript"],
                query="[(import_statement) (export_statement)] @import",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Skip JavaScript comments",
                languages=["javascript"],
                query="(comment) @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize JavaScript identifiers",
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
                name="Replace JavaScript literal values",
                languages=["javascript"],
                query="[(string) (number) (template_string)] @lit",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<LIT>"},
            ),
            Rule(
                name="Replace JavaScript collections",
                languages=["javascript"],
                query="[(array) (object)] @coll",
                action=RuleAction.RENAME,
                params={"token": "<COLL>"},
            ),
            Rule(
                name="Replace JavaScript expressions",
                languages=["javascript"],
                query="[(binary_expression) (unary_expression) (update_expression) (assignment_expression) (ternary_expression)] @exp",
                action=RuleAction.RENAME,
                params={"token": "<EXP>"},
            ),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            RegionExtractionRule(
                query="[(function_declaration) (function) (arrow_function)] @region",
                region_type="function",
            ),
            RegionExtractionRule(
                query="(method_definition) @region",
                region_type="method"
            ),
            RegionExtractionRule(
                query="(class_declaration) @region",
                region_type="class"
            ),
        ]
