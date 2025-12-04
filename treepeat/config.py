from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RulesSettings(BaseSettings):
    """Settings for the rules engine."""

    model_config = SettingsConfigDict(
        env_prefix="RULES_",
    )

    ruleset: str = Field(
        default="default",
        description="Ruleset profile to use",
    )

    # Mapping of language -> allowed region node types to extract
    # When provided, only these languages and node types are used to build
    # region-extraction and normalization rules for the rule engine.
    region_filters: dict[str, set[str]] = Field(
        default_factory=dict,
        description="Limit rules to these languages and region node types (e.g., {'python': {'function_definition'}})",
    )
    additional_regions: dict[str, set[str]] = Field(
        default_factory=dict,
        description=(
            "Additional region extraction rules to include, mapping language to node types "
            "(e.g., {'python': {'decorated_definition'}})"
        ),
    )
    excluded_regions: dict[str, set[str]] = Field(
        default_factory=dict,
        description=(
            "Region extraction rules to exclude by label, mapping language to labels "
            "(e.g., {'python': {'function_definition', 'class_definition'}})"
        ),
    )


class ShingleSettings(BaseSettings):
    """Settings for shingling."""

    model_config = SettingsConfigDict(
        env_prefix="SHINGLE_",
    )

    k: int = Field(
        default=3,
        ge=1,
        description="Length of k-grams (number of nodes in each shingle path)",
    )


class MinHashSettings(BaseSettings):
    """Settings for MinHash."""

    model_config = SettingsConfigDict(
        env_prefix="MINHASH_",
    )

    num_perm: int = Field(
        default=128,
        ge=1,
        description="Number of hash permutations (higher = more accurate, slower)",
    )


class LSHSettings(BaseSettings):
    """Settings for Locality Sensitive Hashing."""

    model_config = SettingsConfigDict(
        env_prefix="LSH_",
    )

    min_lines: int = Field(
        default=5,
        ge=1,
        description="Minimum number of lines for a match to be considered valid",
    )

    similarity_percent: float = Field(default=0.8, ge=0.0, le=1.0, description="% treesitter similarity")

    ignore_node_types: list[str] = Field(
        default_factory=list,
        description="Node types to ignore during region extraction (e.g., ['parameters', 'argument_list'])",
    )


class PipelineSettings(BaseSettings):
    """Global settings for the entire pipeline."""

    model_config = SettingsConfigDict(
        env_prefix="TSSIM_",
    )

    rules: RulesSettings = Field(default_factory=RulesSettings)
    shingle: ShingleSettings = Field(default_factory=ShingleSettings)
    minhash: MinHashSettings = Field(default_factory=MinHashSettings)
    lsh: LSHSettings = Field(default_factory=LSHSettings)
    ignore_patterns: list[str] = Field(
        default_factory=list,
        description="List of glob patterns to ignore files",
    )
    ignore_file_patterns: list[str] = Field(
        default_factory=lambda: ["**/.*ignore"],
        description="List of glob patterns to find ignore files (like .gitignore)",
    )


# Global settings instance that can be accessed throughout the application
_settings: PipelineSettings | None = None


def get_settings() -> PipelineSettings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = PipelineSettings()
    return _settings


def set_settings(settings: PipelineSettings) -> None:
    """Set the global settings instance."""
    global _settings
    _settings = settings
