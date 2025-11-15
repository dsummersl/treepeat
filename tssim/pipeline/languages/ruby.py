"""Ruby language configuration."""

from .base import LanguageConfig, RegionExtractionRule


class RubyConfig(LanguageConfig):
    """Configuration for Ruby language."""

    def get_language_name(self) -> str:
        return "ruby"

    def get_default_rules(self) -> list[str]:
        return [
            "ruby:skip:nodes=comment",
            "ruby:anonymize_identifiers:nodes=identifier|constant,scheme=flat,prefix=VAR",
        ]

    def get_loose_rules(self) -> list[str]:
        return [
            *self.get_default_rules(),
            "ruby:replace_value:nodes=string|string_content|integer|float|simple_symbol|hash_key_symbol|true|false|nil,value=<LIT>",
            "ruby:replace_name:nodes=binary|unary|assignment,token=<EXP>",
            "ruby:replace_name:nodes=array|hash,token=<COLL>",
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return []
