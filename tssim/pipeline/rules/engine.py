"""Rule engine for applying rules to syntax tree nodes."""

from typing import Callable, Optional

from tree_sitter import Node

from .models import Rule, RuleOperation, SkipNodeException
from .parser import parse_rule



class RuleEngine:
    """
    Engine for applying rules to syntax tree nodes.

    Replaces the normalizer system with a more flexible rule-based approach.
    """

    def __init__(self, rules: list[Rule]):
        """
        Initialize the rule engine with a list of rules.

        Args:
            rules: List of rules to apply (last rule wins for conflicts)
        """
        self.rules = rules
        self._identifier_counters: dict[str, int] = {}
        self._operation_handlers = self._build_operation_handlers()

    def _build_operation_handlers(
        self,
    ) -> dict[
        RuleOperation,
        Callable[
            [Rule, str, str, Optional[str], Optional[str]],
            tuple[Optional[str], Optional[str]],
        ],
    ]:
        """Build mapping of operations to handler functions."""
        return {
            RuleOperation.SKIP: self._handle_skip,
            RuleOperation.REPLACE_NAME: self._handle_replace_name,
            RuleOperation.REPLACE_VALUE: self._handle_replace_value,
            RuleOperation.ANONYMIZE_IDENTIFIERS: self._handle_anonymize,
            RuleOperation.CANONICALIZE_TYPES: self._handle_canonicalize,
        }

    def _get_anonymized_identifier(self, prefix: str) -> str:
        """Generate an anonymized identifier."""
        if prefix not in self._identifier_counters:
            self._identifier_counters[prefix] = 0
        self._identifier_counters[prefix] += 1
        return f"{prefix}_{self._identifier_counters[prefix]}"

    def _handle_skip(
        self, rule: Rule, node_type: str, language: str, name: Optional[str], value: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Handle SKIP operation."""
        raise SkipNodeException(
            f"Node type '{node_type}' matched skip rule for language '{language}'"
        )

    def _handle_replace_name(
        self, rule: Rule, node_type: str, language: str, name: Optional[str], value: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Handle REPLACE_NAME operation."""
        return rule.params.get("token", "<NODE>"), value

    def _handle_replace_value(
        self, rule: Rule, node_type: str, language: str, name: Optional[str], value: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Handle REPLACE_VALUE operation."""
        return name, rule.params.get("value", "<LIT>")

    def _handle_anonymize(
        self, rule: Rule, node_type: str, language: str, name: Optional[str], value: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Handle ANONYMIZE_IDENTIFIERS operation."""
        prefix = rule.params.get("prefix", "VAR")
        return name, self._get_anonymized_identifier(prefix)

    def _handle_canonicalize(
        self, rule: Rule, node_type: str, language: str, name: Optional[str], value: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Handle CANONICALIZE_TYPES operation."""
        return rule.params.get("token", "<TYPE>"), value

    def _apply_single_rule(
        self, rule: Rule, node_type: str, language: str, name: Optional[str], value: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """Apply a single matching rule and return updated name and value."""
        handler = self._operation_handlers[rule.operation]
        return handler(rule, node_type, language, name, value)

    def apply_rules(
        self, node: Node, language: str, node_name: Optional[str] = None
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Apply all matching rules to a node.

        Args:
            node: The syntax tree node
            language: The language of the source code
            node_name: Optional override for node type name

        Returns:
            Tuple of (name, value) where either can be None

        Raises:
            SkipNodeException: If a skip rule matches this node
        """
        node_type = node_name or node.type
        name = None
        value = None

        for rule in self.rules:
            if rule.matches_language(language) and rule.matches_node_type(node_type):
                name, value = self._apply_single_rule(rule, node_type, language, name, value)

        return name, value

    def reset_identifiers(self) -> None:
        """Reset the identifier counter (useful between files)."""
        self._identifier_counters.clear()


def build_default_rules() -> list[tuple[Rule, str]]:
    return [
        # Python-specific rules
        (parse_rule("python:skip:nodes=import_statement|import_from_statement"), "Skip Python import statements"),
        (parse_rule("python:skip:nodes=comment"), "Skip Python comments"),
        (parse_rule("python:skip:nodes=string_content"), "Skip Python docstrings and string literals"),
        (parse_rule("python:replace_value:nodes=string|integer|float|number|template_string|true|false|none|null|undefined,value=<LIT>"), "Replace Python literal values with placeholder"),
        (parse_rule("python:anonymize_identifiers:nodes=identifier,scheme=flat,prefix=VAR"), "Anonymize Python identifiers to generic variables"),

        # JavaScript/TypeScript rules
        (parse_rule("javascript|typescript:skip:nodes=import_statement|export_statement"), "Skip JS/TS import and export statements"),
        (parse_rule("javascript|typescript:skip:nodes=comment"), "Skip JS/TS comments"),
        (parse_rule("javascript|typescript:replace_value:nodes=string|number|template_string,value=<LIT>"), "Replace JS/TS literal values with placeholder"),
        (parse_rule("javascript|typescript:anonymize_identifiers:nodes=identifier,scheme=flat,prefix=VAR"), "Anonymize JS/TS identifiers to generic variables"),

        # HTML rules
        (parse_rule("html:skip:nodes=comment"), "Skip HTML comments"),
        (parse_rule("html:replace_value:nodes=attribute_value|text,value=<LIT>"), "Replace HTML attribute values and text content with placeholder"),

        # CSS rules
        (parse_rule("css:skip:nodes=comment"), "Skip CSS comments"),
        (parse_rule("css:replace_value:nodes=string_value|integer_value|float_value|color_value|plain_value,value=<LIT>"), "Replace CSS literal values with placeholder"),
        (parse_rule("css:anonymize_identifiers:nodes=class_name|id_name|tag_name,scheme=flat,prefix=SEL"), "Anonymize CSS selectors to generic names"),

        # Java rules
        (parse_rule("java:skip:nodes=import_declaration|package_declaration"), "Skip Java import and package declarations"),
        (parse_rule("java:skip:nodes=comment|line_comment|block_comment"), "Skip Java comments"),
        (parse_rule("java:replace_value:nodes=string_literal|character_literal|decimal_integer_literal|hex_integer_literal|octal_integer_literal|binary_integer_literal|decimal_floating_point_literal|hex_floating_point_literal|true|false|null_literal,value=<LIT>"), "Replace Java literal values with placeholder"),
        (parse_rule("java:anonymize_identifiers:nodes=identifier,scheme=flat,prefix=VAR"), "Anonymize Java identifiers to generic variables"),

        # SQL rules
        (parse_rule("sql:skip:nodes=comment|marginalia"), "Skip SQL comments"),
        (parse_rule("sql:replace_value:nodes=string|number,value=<LIT>"), "Replace SQL literal values with placeholder"),
        (parse_rule("sql:anonymize_identifiers:nodes=identifier|object_reference,scheme=flat,prefix=VAR"), "Anonymize SQL identifiers to generic variables"),

        # Bash/Shell rules
        (parse_rule("bash:skip:nodes=comment"), "Skip Bash comments"),
        (parse_rule("bash:replace_value:nodes=string|raw_string|simple_expansion|number,value=<LIT>"), "Replace Bash literal values with placeholder"),
        (parse_rule("bash:anonymize_identifiers:nodes=variable_name,scheme=flat,prefix=VAR"), "Anonymize Bash variable names to generic variables"),

        # Rust rules
        (parse_rule("rust:skip:nodes=use_declaration"), "Skip Rust use declarations"),
        (parse_rule("rust:skip:nodes=line_comment|block_comment"), "Skip Rust comments"),
        (parse_rule("rust:replace_value:nodes=string_literal|raw_string_literal|char_literal|integer_literal|float_literal|boolean_literal,value=<LIT>"), "Replace Rust literal values with placeholder"),
        (parse_rule("rust:anonymize_identifiers:nodes=identifier,scheme=flat,prefix=VAR"), "Anonymize Rust identifiers to generic variables"),

        # Ruby rules
        (parse_rule("ruby:skip:nodes=comment"), "Skip Ruby comments"),
        (parse_rule("ruby:replace_value:nodes=string|string_content|integer|float|simple_symbol|hash_key_symbol|true|false|nil,value=<LIT>"), "Replace Ruby literal values with placeholder"),
        (parse_rule("ruby:anonymize_identifiers:nodes=identifier|constant,scheme=flat,prefix=VAR"), "Anonymize Ruby identifiers to generic variables"),

        # Go rules
        (parse_rule("go:skip:nodes=import_declaration|package_clause"), "Skip Go import and package declarations"),
        (parse_rule("go:skip:nodes=comment|line_comment|block_comment"), "Skip Go comments"),
        (parse_rule("go:replace_value:nodes=interpreted_string_literal|raw_string_literal|rune_literal|int_literal|float_literal|imaginary_literal|true|false|nil,value=<LIT>"), "Replace Go literal values with placeholder"),
        (parse_rule("go:anonymize_identifiers:nodes=identifier,scheme=flat,prefix=VAR"), "Anonymize Go identifiers to generic variables"),

        # C# rules
        (parse_rule("csharp:skip:nodes=using_directive"), "Skip C# using directives"),
        (parse_rule("csharp:skip:nodes=comment"), "Skip C# comments"),
        (parse_rule("csharp:replace_value:nodes=string_literal|verbatim_string_literal|character_literal|integer_literal|real_literal|boolean_literal|null_literal,value=<LIT>"), "Replace C# literal values with placeholder"),
        (parse_rule("csharp:anonymize_identifiers:nodes=identifier,scheme=flat,prefix=VAR"), "Anonymize C# identifiers to generic variables"),
    ]


def build_loose_rules() -> list[tuple[Rule, str]]:
    return [
        *build_default_rules(),

        # Python
        (parse_rule("python:replace_name:nodes=binary_operator|boolean_operator|comparison_operator|unary_operator,token=<OP>"), "Replace Python operators with generic placeholder"),
        (parse_rule("python:canonicalize_types:nodes=type"), "Canonicalize Python type annotations"),
        (parse_rule("python:replace_name:nodes=list|dictionary|tuple|set,token=<COLL>"), "Replace Python collections with generic placeholder"),

        # JS/TS
        (parse_rule("typescript:canonicalize_types:nodes=type_annotation|predefined_type|type_identifier"), "Canonicalize TypeScript type annotations"),
        (parse_rule("javascript|typescript:replace_name:nodes=array|object,token=<COLL>"), "Replace JS/TS collections with generic placeholder"),
        (parse_rule("javascript|typescript:replace_name:nodes=binary_expression|unary_expression|update_expression|assignment_expression|ternary_expression,token=<EXP>"), "Replace JS/TS expressions with generic placeholder"),

        # HTML
        (parse_rule("html:replace_name:nodes=element|tag_name,token=<TAG>"), "Replace HTML elements with generic placeholder"),
        (parse_rule("html:replace_name:nodes=attribute_name,token=<ATTR>"), "Replace HTML attribute names with generic placeholder"),

        # CSS
        (parse_rule("css:replace_name:nodes=property_name,token=<PROP>"), "Replace CSS property names with generic placeholder"),
        (parse_rule("css:replace_name:nodes=feature_name,token=<FEAT>"), "Replace CSS feature names with generic placeholder"),

        # Java
        (parse_rule("java:replace_name:nodes=binary_expression|unary_expression|update_expression|assignment_expression|ternary_expression,token=<EXP>"), "Replace Java expressions with generic placeholder"),
        (parse_rule("java:canonicalize_types:nodes=type_identifier|generic_type|array_type|integral_type|floating_point_type|boolean_type,token=<TYPE>"), "Canonicalize Java types"),
        (parse_rule("java:replace_name:nodes=array_initializer|array_creation_expression,token=<COLL>"), "Replace Java arrays with generic placeholder"),

        # SQL
        (parse_rule("sql:replace_name:nodes=keyword,token=<KW>"), "Replace SQL keywords with generic placeholder"),
        (parse_rule("sql:replace_name:nodes=binary_expression|unary_expression,token=<EXP>"), "Replace SQL expressions with generic placeholder"),

        # Bash
        (parse_rule("bash:replace_name:nodes=command|command_name,token=<CMD>"), "Replace Bash commands with generic placeholder"),
        (parse_rule("bash:replace_name:nodes=binary_expression|unary_expression,token=<EXP>"), "Replace Bash expressions with generic placeholder"),

        # Rust
        (parse_rule("rust:replace_name:nodes=binary_expression|unary_expression|assignment_expression,token=<EXP>"), "Replace Rust expressions with generic placeholder"),
        (parse_rule("rust:canonicalize_types:nodes=type_identifier|generic_type|array_type|reference_type|pointer_type|tuple_type|primitive_type,token=<TYPE>"), "Canonicalize Rust types"),
        (parse_rule("rust:replace_name:nodes=array_expression|struct_expression,token=<COLL>"), "Replace Rust collections with generic placeholder"),

        # Ruby
        (parse_rule("ruby:replace_name:nodes=binary|unary|assignment,token=<EXP>"), "Replace Ruby expressions with generic placeholder"),
        (parse_rule("ruby:replace_name:nodes=array|hash,token=<COLL>"), "Replace Ruby collections with generic placeholder"),

        # Go
        (parse_rule("go:replace_name:nodes=binary_expression|unary_expression|assignment_expression,token=<EXP>"), "Replace Go expressions with generic placeholder"),
        (parse_rule("go:canonicalize_types:nodes=type_identifier|pointer_type|array_type|slice_type|struct_type|interface_type|map_type|channel_type,token=<TYPE>"), "Canonicalize Go types"),
        (parse_rule("go:replace_name:nodes=composite_literal|slice_literal,token=<COLL>"), "Replace Go collections with generic placeholder"),

        # C#
        (parse_rule("csharp:replace_name:nodes=binary_expression|prefix_unary_expression|postfix_unary_expression|assignment_expression|conditional_expression,token=<EXP>"), "Replace C# expressions with generic placeholder"),
        (parse_rule("csharp:canonicalize_types:nodes=type_identifier|predefined_type|array_type|nullable_type|pointer_type,token=<TYPE>"), "Canonicalize C# types"),
        (parse_rule("csharp:replace_name:nodes=array_creation_expression|initializer_expression,token=<COLL>"), "Replace C# collections with generic placeholder"),
    ]
