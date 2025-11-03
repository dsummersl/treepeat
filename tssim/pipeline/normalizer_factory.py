"""Factory for building normalizers based on settings."""

import logging

from tssim.config import PipelineSettings
from tssim.pipeline.normalizers import Normalizer
from tssim.pipeline.normalizers.python import PythonImportNormalizer

logger = logging.getLogger(__name__)


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

    # Python normalizers
    if settings.normalizer.python.ignore_imports:
        normalizers.append(PythonImportNormalizer())
        logger.debug("Added PythonImportNormalizer")

    # Future: Add more normalizers based on settings
    # if settings.normalizer.python.normalize_identifiers:
    #     normalizers.append(PythonIdentifierNormalizer())
    # if settings.normalizer.python.normalize_literals:
    #     normalizers.append(PythonLiteralNormalizer())

    logger.info("Built %d normalizer(s)", len(normalizers))
    return normalizers
