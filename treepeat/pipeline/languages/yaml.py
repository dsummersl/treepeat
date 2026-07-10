from treepeat.pipeline.rules.models import Rule, RuleAction

from .base import LanguageConfig, RegionExtractionRule


class YAMLConfig(LanguageConfig):
    """Configuration for YAML language.

    Supports both standalone ``.yaml``/``.yml`` files and ` ```yaml ` fenced
    code blocks embedded in Markdown (via language injection).
    """

    def get_default_rules(self) -> list[Rule]:
        return [
            Rule(
                name="Ignore comments",
                languages=["yaml"],
                query="(comment) @comment",
                action=RuleAction.REMOVE,
            ),
        ]

    def get_loose_rules(self) -> list[Rule]:
        return [
            *self.get_default_rules(),
            Rule(
                name="Anonymize scalar values",
                languages=["yaml"],
                query=(
                    "["
                    "(integer_scalar) (float_scalar) (boolean_scalar)"
                    " (double_quote_scalar) (single_quote_scalar) (block_scalar)"
                    "] @lit"
                ),
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<LIT>"},
            ),
            Rule(
                name="Anonymize anchor and alias names",
                languages=["yaml"],
                query="[(anchor_name) (alias_name)] @ref",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<REF>"},
            ),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            RegionExtractionRule.from_node_type("block_mapping_pair"),
            RegionExtractionRule.from_node_type("block_sequence"),
        ]
