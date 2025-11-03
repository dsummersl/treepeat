"""Factory for building normalizers based on settings."""

import logging
from typing import Callable

from tssim.config import PipelineSettings
from tssim.pipeline.normalizers import Normalizer
from tssim.pipeline.normalizers.python import PythonImportNormalizer

logger = logging.getLogger(__name__)


# Registry of available normalizers
class NormalizerSpec:
    """Specification for a normalizer."""

    def __init__(
        self,
        name: str,
        description: str,
        factory: Callable[[], Normalizer],
    ):
        self.name = name
        self.description = description
        self.factory = factory


# All available normalizers
NORMALIZER_REGISTRY: list[NormalizerSpec] = [
    NormalizerSpec(
        name="python-imports",
        description="Skip Python import statements during analysis",
        factory=lambda: PythonImportNormalizer(),
    ),
]


def get_available_normalizers() -> list[NormalizerSpec]:
    """Get list of all available normalizers.

    Returns:
        List of normalizer specifications
    """
    return NORMALIZER_REGISTRY


def build_normalizers(settings: PipelineSettings) -> list[Normalizer]:
    """Build list of normalizers based on settings.

    This function assembles the appropriate normalizers based on the
    configuration. Normalizers themselves don't check settings - the
    pipeline configures which ones to use.

    Args:
        settings: Pipeline settings

    Returns:
        List of normalizer instances to apply
    """
    normalizers: list[Normalizer] = []
    disabled = set(settings.normalizer.disabled_normalizers)

    for spec in NORMALIZER_REGISTRY:
        if spec.name not in disabled:
            normalizers.append(spec.factory())
            logger.debug("Added %s", spec.name)
        else:
            logger.debug("Skipped %s (disabled)", spec.name)

    logger.info("Built %d normalizer(s)", len(normalizers))
    return normalizers
