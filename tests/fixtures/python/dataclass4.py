"""Factory for building normalizers based on settings."""

import logging

from treepeat.config import PipelineSettings

logger = logging.getLogger(__name__)


# Registry of available normalizers
class NormalizerSpec:
    """Specification for a normalizer."""

    pass


# Global settings instance that can be accessed throughout the application
_settings: PipelineSettings | None = None
