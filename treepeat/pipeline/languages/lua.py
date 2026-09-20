from treepeat.pipeline.rules.models import Rule, RuleAction

from .base import LanguageConfig, RegionExtractionRule


class LuaConfig(LanguageConfig):
    """Configuration for Lua language."""

    def get_default_rules(self) -> list[Rule]:
        return [
            Rule(
                # Lua has no import statement; `local x = require("mod")` is the
                # idiomatic equivalent, so the whole declaration is dropped the
                # way other languages drop their imports.
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
                # Covers both `--` line comments and `--[[ ]]` block comments,
                # which share the single `comment` node type in tree-sitter-lua.
                name="Ignore comments",
                languages=["lua"],
                query="(comment) @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(
                # A declaration's name is a plain identifier (`function f`), a
                # dot index (`function M.f`), or a method index (`function M:f`).
                # Only the trailing name segment is anonymized: the table part
                # (`M`) identifies the module the function hangs off, and
                # collapsing it would merge unrelated modules' methods.
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
                # Covers quoted and long-bracket ([[...]]) strings alike; the
                # `string_content` children are removed separately so no text
                # leaks through this non-leaf node.
                name="Anonymize string literals",
                languages=["lua"],
                query="(string) @str",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<STR>"},
            ),
            Rule(
                # Lua has a single numeric type, so integers, floats, and hex
                # literals all parse as `number`.
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
                # Covers arithmetic, comparison, logical, bitwise, and the
                # string concatenation operator (..), which tree-sitter-lua all
                # model as binary_expression.
                name="Anonymize binary expressions",
                languages=["lua"],
                query="(binary_expression) @binop",
                action=RuleAction.REPLACE_NODE_TYPE,
                params={"token": "<BINOP>"},
            ),
            Rule(
                # Covers -, not, #, and ~.
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
            # Lua models modules and objects as tables, so a table constructor
            # is the closest analogue to a class body.
            RegionExtractionRule.from_node_type("table_constructor"),
        ]
