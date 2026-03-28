from treepeat.pipeline.rules.models import Rule, RuleAction

from .base import LanguageConfig, RegionExtractionRule


class RustConfig(LanguageConfig):
    """Configuration for Rust language."""

    def get_language_name(self) -> str:
        return "rust"

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
                # Lifetimes are borrow-checker annotations, not logic — omit non-static ones
                # so that copy-pasted functions with renamed lifetime parameters ('a → 'b) are
                # still detected as duplicates. 'static is preserved because it carries semantic
                # content (permanent storage duration), unlike named lifetimes.
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
                # Covers both outer (#[...]) and inner (#![...]) attribute forms.
                # Inner attributes are a distinct node type in tree-sitter-rust.
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
                # Covers struct, enum, trait, type alias, and union item names.
                # Note: type_identifier nodes inside impl_item (e.g. `impl Foo`)
                # are intentionally NOT anonymized — doing so would collapse
                # impl blocks for unrelated types that happen to have similar
                # method bodies, producing false-positive clone matches.
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
                # Removes the macro path before `!` for both simple (`println!`)
                # and scoped (`log::info!`) forms, so calls differing only in
                # macro name (e.g. log level) normalize identically. The `!`
                # delimiter and token_tree arguments are preserved, so the
                # presence and arity of the call still contributes to similarity.
                # Note: tree-sitter-rust parses token_tree contents as structured
                # nodes (string_literal, identifier, etc.), so the existing
                # string-content and identifier rules already reach inside macro
                # arguments.
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
                # Covers regular strings, raw strings, and character literals.
                # byte strings (b"...") parse as string_literal and are included.
                # Note: string_content child nodes must be removed separately by
                # the "Ignore string content" rule to prevent content from leaking.
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
                # Covers arithmetic, comparison, logical, and bitwise operators.
                # compound_assignment_expr (+=, -=, etc.) is a separate node type
                # and is not anonymized here. The same gap exists in Go and Python
                # configs and is accepted as a known limitation.
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
