"""Normalizer interface and implementations."""

from abc import ABC, abstractmethod

from tree_sitter import Node

from tssim.models.normalization import NormalizationResult, SkipNode  # noqa: F401


class Normalizer(ABC):
    """Base interface for AST normalizers.

    Normalizers are pure functions that can:
    - Return None if not applicable (no change)
    - Return NormalizationResult to modify node name and/or value
    - Raise SkipNode to exclude the node from shingling

    Normalizers should NOT check configuration settings - the pipeline
    assembles the appropriate normalizers based on settings.
    """

    @abstractmethod
    def normalize_node(
        self,
        node: Node,
        name: str,
        value: str | None,
        language: str,
        source: bytes,
    ) -> NormalizationResult | None:
        """Normalize a node's representation for shingling.

        Args:
            node: The tree-sitter node
            name: Current node name (typically node.type)
            value: Current node value (from source) or None for structural nodes
            language: Programming language of the file
            source: Source code bytes

        Returns:
            NormalizationResult with modified name/value, or None if not applicable

        Raises:
            SkipNode: If this node should be excluded from shingling entirely
        """
        pass
