"""Bash language configuration."""

from .base import LanguageConfig, RegionExtractionRule


class BashConfig(LanguageConfig):
    """Configuration for Bash language."""

    def get_language_name(self) -> str:
        return "bash"

    def get_default_rules(self) -> list[str]:
        return [
            "bash:skip:nodes=comment",
            "bash:anonymize_identifiers:nodes=variable_name,scheme=flat,prefix=VAR",
        ]

    def get_loose_rules(self) -> list[str]:
        return [
            *self.get_default_rules(),
            "bash:replace_value:nodes=string|raw_string|simple_expansion|number,value=<LIT>",
            "bash:replace_name:nodes=command|command_name,token=<CMD>",
            "bash:replace_name:nodes=binary_expression|unary_expression,token=<EXP>",
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return []
