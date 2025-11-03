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


# Global settings instance that can be accessed throughout the application
_settings: NormalizerSettings | None = None


def get_settings() -> NormalizerSettings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = NormalizerSettings()
    return _settings


def set_settings(settings: NormalizerSettings) -> None:
    """Set the global settings instance."""
    global _settings
    _settings = settings
