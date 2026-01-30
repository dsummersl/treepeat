from treepeat.pipeline.rules.models import Rule, RuleAction

from .base import LanguageConfig, RegionExtractionRule


class BashConfig(LanguageConfig):
    """Configuration for Bash language."""

    def get_language_name(self) -> str:
        return "bash"

    def get_default_rules(self) -> list[Rule]:
        return [
            Rule(
                name="Ignore comments",
                languages=["bash"],
                query="(comment) @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize function names",
                languages=["bash"],
                query="(function_definition name: (word) @name)",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "FUNC"},
            ),
            Rule(
                name="Anonymize variables",
                languages=["bash"],
                query="(variable_name) @var",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<VAR>"},
            ),
        ]

    def get_loose_rules(self) -> list[Rule]:
        return [
            *self.get_default_rules(),
            Rule(
                name="Anonymize strings",
                languages=["bash"],
                query="[(string) (raw_string) (string_content)] @str",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<STR>"},
            ),
            Rule(
                name="Anonymize numbers",
                languages=["bash"],
                query="(number) @num",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<NUM>"},
            ),
            Rule(
                name="Anonymize commands",
                languages=["bash"],
                query="[(command) (command_name)] @cmd",
                action=RuleAction.REPLACE_NODE_TYPE,
                params={"token": "<CMD>"},
            ),
            Rule(
                name="Anonymize expressions",
                languages=["bash"],
                query="[(binary_expression) (unary_expression)] @exp",
                action=RuleAction.REPLACE_NODE_TYPE,
                params={"token": "<EXP>"},
            ),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            RegionExtractionRule.from_node_type("function_definition"),
            RegionExtractionRule.from_node_type("if_statement"),
            RegionExtractionRule.from_node_type("while_statement"),
        ]
