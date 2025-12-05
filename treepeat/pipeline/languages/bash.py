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
                name="Anonymize variables",
                languages=["bash"],
                query="(variable_name) @var",
                action=RuleAction.ANONYMIZE,
                params={"prefix": "VAR"},
            ),
        ]

    def get_loose_rules(self) -> list[Rule]:
        return [
            *self.get_default_rules(),
            Rule(
                name="Anonymize literal values",
                languages=["bash"],
                query="[(string) (raw_string) (simple_expansion) (number)] @lit",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<LIT>"},
            ),
            Rule(
                name="Anonymize commands",
                languages=["bash"],
                query="[(command) (command_name)] @cmd",
                action=RuleAction.RENAME,
                params={"token": "<CMD>"},
            ),
            Rule(
                name="Anonymize expressions",
                languages=["bash"],
                query="[(binary_expression) (unary_expression)] @exp",
                action=RuleAction.RENAME,
                params={"token": "<EXP>"},
            ),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            RegionExtractionRule.from_node_type("function_definition"),
            RegionExtractionRule.from_node_type("if_statement"),
            RegionExtractionRule.from_node_type("while_statement"),
        ]
