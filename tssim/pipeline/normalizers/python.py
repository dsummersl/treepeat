"""Python-specific normalizers."""

import logging

from tree_sitter import Node

from tssim.models.normalization import NormalizationResult, SkipNode
from tssim.pipeline.normalizers import Normalizer

logger = logging.getLogger(__name__)


class PythonImportNormalizer(Normalizer):
    """Skip import statements in Python code.

    This normalizer causes import and from...import statements to be
    excluded from shingling, focusing on actual implementation.
    """

    def normalize_node(
        self,
        node: Node,
        name: str,
        value: str | None,
        language: str,
        source: bytes,
    ) -> NormalizationResult | None:
        """Skip import statements in Python code.

        Args:
            node: The tree-sitter node
            name: Current node name
            value: Current node value or None
            language: Programming language
            source: Source code bytes

        Returns:
            None (not applicable for non-Python or non-import nodes)

        Raises:
            SkipNode: If this is a Python import statement
        """
        if language != "python":
            return None

        if node.type in ("import_statement", "import_from_statement"):
            logger.debug("Skipping %s node", node.type)
            raise SkipNode()

        return None
