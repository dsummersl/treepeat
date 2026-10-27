from treepeat.pipeline.rules.models import Rule, RuleAction

from .base import LanguageConfig, RegionExtractionRule


class RustConfig(LanguageConfig):


    def get_default_rules(self) -> list[Rule]:
        return [
            Rule(
                name="Ignore use declarations",
                languages=["rust"],
                query="(use_declaration) @use",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Ignore extern crate declarations",
                languages=["rust"],
                query="(extern_crate_declaration) @extern_crate",
                action=RuleAction.REMOVE,
            ),
            Rule(




                name="Ignore generic lifetimes",
                languages=["rust"],
                query='((lifetime) @life (#not-eq? @life "\'static"))',
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Ignore line comments",
                languages=["rust"],
                query="(line_comment) @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Ignore block comments",
                languages=["rust"],
                query="(block_comment) @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(


                name="Ignore attribute items",
                languages=["rust"],
                query="[(attribute_item) (inner_attribute_item)] @attr",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize function names",
                languages=["rust"],
                query="(function_item name: (identifier) @func)",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "FUNC"},
            ),
            Rule(





                name="Anonymize type names",
                languages=["rust"],
                query="""[
                    (struct_item name: (type_identifier) @type)
                    (enum_item name: (type_identifier) @type)
                    (trait_item name: (type_identifier) @type)
                    (type_item name: (type_identifier) @type)
                    (union_item name: (type_identifier) @type)
                ]""",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "TYPE"},
            ),
        ]

    def get_loose_rules(self) -> list[Rule]:
        return [
            Rule(









                name="Anonymize macro names",
                languages=["rust"],
                query="[(macro_invocation (identifier) @name) (macro_invocation (scoped_identifier) @name)]",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Ignore string content",
                languages=["rust"],
                query="(string_content) @content",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize identifiers",
                languages=["rust"],
                query='((identifier) @var (#not-eq? @var "static"))',
                action=RuleAction.ANONYMIZE,
                params={"prefix": "VAR"},
            ),
            Rule(




                name="Anonymize string literals",
                languages=["rust"],
                query="[(string_literal) (raw_string_literal) (char_literal)] @str",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<STR>"},
            ),
            Rule(
                name="Anonymize numeric literals",
                languages=["rust"],
                query="[(integer_literal) (float_literal)] @num",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<NUM>"},
            ),
            Rule(
                name="Anonymize boolean literals",
                languages=["rust"],
                query="(boolean_literal) @bool",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<BOOL>"},
            ),
            Rule(




                name="Anonymize binary expressions",
                languages=["rust"],
                query="(binary_expression) @binop",
                action=RuleAction.REPLACE_NODE_TYPE,
                params={"token": "<BINOP>"},
            ),
            Rule(
                name="Anonymize unary expressions",
                languages=["rust"],
                query="(unary_expression) @unop",
                action=RuleAction.REPLACE_NODE_TYPE,
                params={"token": "<UNOP>"},
            ),
            *self.get_default_rules(),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            RegionExtractionRule.from_node_type("function_item"),
            RegionExtractionRule.from_node_type("impl_item"),
            RegionExtractionRule.from_node_type("struct_item"),
            RegionExtractionRule.from_node_type("enum_item"),
            RegionExtractionRule.from_node_type("trait_item"),
            RegionExtractionRule.from_node_type("macro_definition"),
        ]
