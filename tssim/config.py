"""Configuration for normalizers using pydantic-settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PythonNormalizerSettings(BaseSettings):
    """Settings for Python-specific normalizers."""

    model_config = SettingsConfigDict(
        env_prefix="PYTHON_",
    )

    ignore_imports: bool = Field(
        default=True,
        description="Ignore import statements during normalization",
    )


class NormalizerSettings(BaseSettings):
    """Main settings for all normalizers."""

    model_config = SettingsConfigDict(
        env_prefix="NORMALIZER_",
    )

    python: PythonNormalizerSettings = Field(default_factory=PythonNormalizerSettings)


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
    include_text: bool = Field(
        default=False,
        description="Include node text in shingles for more specificity",
    )


class PipelineSettings(BaseSettings):
    """Global settings for the entire pipeline."""

    model_config = SettingsConfigDict(
        env_prefix="TSSIM_",
    )

    normalizer: NormalizerSettings = Field(default_factory=NormalizerSettings)
    shingle: ShingleSettings = Field(default_factory=ShingleSettings)


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
