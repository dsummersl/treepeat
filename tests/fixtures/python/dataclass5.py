"""Configuration for normalizers using pydantic-settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NormalizerSettings(BaseSettings):
    pass


# All available normalizers
NORMALIZER_REGISTRY: list[NormalizerSpec] = [
    NormalizerSpec(
        name="python-imports",
        description="Skip Python import statements during analysis",
        factory=lambda: PythonImportNormalizer(),
    ),
]
