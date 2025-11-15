"""Python language configuration."""

from tssim.pipeline.rules.models import Rule, RuleAction

from .base import LanguageConfig, RegionExtractionRule


class PythonConfig(LanguageConfig):
    """Configuration for Python language."""

    def get_language_name(self) -> str:
        return "python"

    def get_default_rules(self) -> list[Rule]:

        return [
            Rule(
                name="Skip Python import statements",
                languages=["python"],
                query="[(import_statement) (import_from_statement)] @import",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Skip Python comments",
                languages=["python"],
                query="(comment) @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize Python identifiers",
                languages=["python"],
                query="(identifier) @var",
                action=RuleAction.ANONYMIZE,
                params={"prefix": "VAR"},
            ),
        ]

    def get_loose_rules(self) -> list[Rule]:
        return [
            *self.get_default_rules(),
            Rule(
                name="Replace Python literal values",
                languages=["python"],
                query="[(string) (integer) (float) (true) (false) (none)] @lit",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<LIT>"},
            ),
            Rule(
                name="Replace Python operators",
                languages=["python"],
                query="[(binary_operator) (boolean_operator) (comparison_operator) (unary_operator)] @op",
                action=RuleAction.RENAME,
                params={"token": "<OP>"},
            ),
            Rule(
                name="Canonicalize Python types",
                languages=["python"],
                query="(type) @type",
                action=RuleAction.CANONICALIZE,
            ),
            Rule(
                name="Replace Python collections",
                languages=["python"],
                query="[(list) (dictionary) (tuple) (set)] @coll",
                action=RuleAction.RENAME,
                params={"token": "<COLL>"},
            ),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            RegionExtractionRule(node_types=["function_definition"], region_type="function"),
            RegionExtractionRule(node_types=["class_definition"], region_type="class"),
        ]
