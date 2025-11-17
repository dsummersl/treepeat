"""Factory for building normalizers based on settings."""

import logging
from typing import Callable

from covey.config import PipelineSettings
from covey.pipeline.normalizers import Normalizer
from covey.pipeline.normalizers.python import PythonImportNormalizer

logger = logging.getLogger(__name__)


# Registry of available normalizers
class NormalizerSpec:
    """Specification for a normalizer."""

    pass


# Global settings instance that can be accessed throughout the application
_settings: PipelineSettings | None = None
