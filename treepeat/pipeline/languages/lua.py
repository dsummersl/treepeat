from treepeat.pipeline.rules.models import Rule, RuleAction

from .base import LanguageConfig, RegionExtractionRule


class LuaConfig(LanguageConfig):
    def get_default_rules(self) -> list[Rule]:
        return [
            Rule(
                name="Ignore require declarations",
                languages=["lua"],
                query="""(
                    (variable_declaration
                      (assignment_statement
                        (expression_list (function_call name: (identifier) @_fn))))
                    @require
                    (#eq? @_fn "require")
                )""",
                target="require",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Ignore comments",
                languages=["lua"],
                query="(comment) @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize function names",
                languages=["lua"],
                query="""[
                    (function_declaration name: (identifier) @name)
                    (function_declaration name: (dot_index_expression field: (identifier) @name))
                    (function_declaration name: (method_index_expression method: (identifier) @name))
                ]""",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "FUNC"},
            ),
        ]

    def get_loose_rules(self) -> list[Rule]:
        return [
            Rule(
                name="Ignore string content",
                languages=["lua"],
                query="(string_content) @content",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize identifiers",
                languages=["lua"],
                query="(identifier) @var",
                action=RuleAction.ANONYMIZE,
                params={"prefix": "VAR"},
            ),
            Rule(
                name="Anonymize string literals",
                languages=["lua"],
                query="(string) @str",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<STR>"},
            ),
            Rule(
                name="Anonymize numeric literals",
                languages=["lua"],
                query="(number) @num",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<NUM>"},
            ),
            Rule(
                name="Anonymize boolean and nil literals",
                languages=["lua"],
                query="[(true) (false) (nil)] @lit",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<LIT>"},
            ),
            Rule(
                name="Anonymize binary expressions",
                languages=["lua"],
                query="(binary_expression) @binop",
                action=RuleAction.REPLACE_NODE_TYPE,
                params={"token": "<BINOP>"},
            ),
            Rule(
                name="Anonymize unary expressions",
                languages=["lua"],
                query="(unary_expression) @unop",
                action=RuleAction.REPLACE_NODE_TYPE,
                params={"token": "<UNOP>"},
            ),
            *self.get_default_rules(),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            RegionExtractionRule.from_node_type("function_declaration"),
            RegionExtractionRule.from_node_type("function_definition"),
            RegionExtractionRule.from_node_type("table_constructor"),
        ]
