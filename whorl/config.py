"""Configuration using pydantic-settings."""

from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RulesSettings(BaseSettings):
    """Settings for the rules engine."""

    model_config = SettingsConfigDict(
        env_prefix="RULES_",
    )

    ruleset: str = Field(
        default="default",
        description="Ruleset profile to use (none, default, loose)",
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

    # Window/stride settings for line matching (shingle-based windows)
    window_size: int = Field(
        default=20,
        ge=1,
        description="Size of sliding window in number of shingles for line-based similarity detection",
    )

    stride: int = Field(
        default=5,
        ge=1,
        description="Stride (step size) for sliding window in number of shingles",
    )

    # Internal thresholds (not exposed as environment variables or CLI options)
    # Region matching uses higher thresholds for exact matches
    region_threshold: float = 0.5
    region_min_similarity: float = 0.9

    # Line matching uses lower threshold to find approximate windows, then filters to exact matches
    line_threshold: float = 0.3
    line_min_similarity: float = 0.95

    def __init__(self, threshold: float | None = None, **data: Any) -> None:
        """Initialize LSH settings, optionally overriding thresholds with a single value."""
        # If threshold is provided, use it for all thresholds (backward compatibility)
        if threshold is not None:
            data.setdefault('region_threshold', threshold)
            data.setdefault('line_threshold', threshold)
            data.setdefault('region_min_similarity', threshold)
            data.setdefault('line_min_similarity', threshold)
        super().__init__(**data)


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
