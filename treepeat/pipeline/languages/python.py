from treepeat.pipeline.rules.models import Rule, RuleAction

from .base import LanguageConfig, RegionExtractionRule


class PythonConfig(LanguageConfig):
    """Configuration for Python language."""

    def get_language_name(self) -> str:
        return "python"

    def get_default_rules(self) -> list[Rule]:
        return [
            Rule(
                name="Ignore import statements",
                languages=["python"],
                query="[(import_statement) (import_from_statement) (future_import_statement)] @import",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Ignore TYPE_CHECKING blocks",
                languages=["python"],
                query="""(if_statement
                    condition: (attribute
                        attribute: (identifier) @attr_name
                        (#match? @attr_name "TYPE_CHECKING")
                    )
                ) @type_check""",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Ignore TypeVar declarations",
                languages=["python"],
                query="""(expression_statement
                    (assignment
                        right: (call
                            function: (attribute
                                attribute: (identifier) @func_name
                                (#match? @func_name "TypeVar")
                            )
                        )
                    )
                ) @typevar""",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Ignore comments",
                languages=["python"],
                query="(comment) @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Ignore docstrings",
                languages=["python"],
                query="(expression_statement (string))",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize function names",
                languages=["python"],
                query="(function_definition name: (identifier) @func)",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "FUNC"},
            ),
            Rule(
                name="Anonymize class names",
                languages=["python"],
                query="(class_definition name: (identifier) @class)",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "CLASS"},
            ),
        ]

    def get_loose_rules(self) -> list[Rule]:
        return [
            *self.get_default_rules(),
            Rule(
                name="Ignore string content",
                languages=["python"],
                query="(string_content) @content",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize identifiers",
                languages=["python"],
                query="(identifier) @var",
                action=RuleAction.ANONYMIZE,
                params={"prefix": "VAR"},
            ),
            Rule(
                name="Anonymize literals",
                languages=["python"],
                query="[(string) (integer) (float) (true) (false) (none)] @lit",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<LIT>"},
            ),
            Rule(
                name="Anonymize operators",
                languages=["python"],
                query="[(binary_operator) (boolean_operator) (comparison_operator) (unary_operator)] @op",
                action=RuleAction.RENAME,
                params={"token": "<OP>"},
            ),
            Rule(
                name="Anonymize types",
                languages=["python"],
                query="(type) @type",
                action=RuleAction.RENAME,
                params={"type": "<T>"},
            ),
            Rule(
                name="Anonymize collections",
                languages=["python"],
                query="[(list) (dictionary) (tuple) (set)] @coll",
                action=RuleAction.RENAME,
                params={"token": "<COLL>"},
            ),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            RegionExtractionRule.from_node_type("function_definition"),
            RegionExtractionRule.from_node_type("class_definition"),
        ]
