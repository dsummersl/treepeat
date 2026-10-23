from treepeat.pipeline.rules.models import Rule, RuleAction

from .base import LanguageConfig, RegionExtractionRule


class PHPConfig(LanguageConfig):
    """Configuration for PHP language."""

    def get_default_rules(self) -> list[Rule]:
        return [
            Rule(
                name="Ignore namespace imports",
                languages=["php"],
                query="(namespace_use_declaration) @import",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Ignore comments",
                languages=["php"],
                query="(comment) @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize function and method names",
                languages=["php"],
                query="[(function_definition name: (name) @name) (method_declaration name: (name) @name)]",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "FUNC"},
            ),
            Rule(
                name="Anonymize type declaration names",
                languages=["php"],
                query=(
                    "[(class_declaration name: (name) @name) "
                    "(interface_declaration name: (name) @name) "
                    "(trait_declaration name: (name) @name) "
                    "(enum_declaration name: (name) @name)]"
                ),
                action=RuleAction.REPLACE_VALUE,
                params={"value": "CLASS"},
            ),
        ]

    def get_loose_rules(self) -> list[Rule]:
        return [
            Rule(
                # Variable, member, constant and callable identifiers all contain name nodes.
                name="Anonymize identifiers",
                languages=["php"],
                query="(name) @id",
                action=RuleAction.ANONYMIZE,
                params={"prefix": "VAR"},
            ),
            Rule(
                # Normalize leaves: replacing a string's value alone leaves its content intact.
                name="Anonymize literal values",
                languages=["php"],
                query=(
                    "[(integer) (float) (boolean) (null) (string_content) (escape_sequence) "
                    "(nowdoc_string) (heredoc_start) (heredoc_end)] @lit"
                ),
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<LIT>"},
            ),
            *self.get_default_rules(),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            RegionExtractionRule(label="function", query="(function_definition) @region"),
            RegionExtractionRule(label="method", query="(method_declaration) @region"),
            RegionExtractionRule(label="class", query="(class_declaration) @region"),
            RegionExtractionRule.from_node_type("anonymous_function"),
            RegionExtractionRule.from_node_type("arrow_function"),
            RegionExtractionRule.from_node_type("anonymous_class"),
            RegionExtractionRule.from_node_type("interface_declaration"),
            RegionExtractionRule.from_node_type("trait_declaration"),
            RegionExtractionRule.from_node_type("enum_declaration"),
        ]
