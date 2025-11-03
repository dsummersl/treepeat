"""Shingling pipeline stage.

This module extracts shingles (structural features) from ASTs for similarity detection.
Shingles are k-gram paths through the AST that capture structural patterns.
"""

import logging
from collections import deque

from tree_sitter import Node

from tssim.models.ast import ParsedFile, ParseResult
from tssim.models.normalization import NodeRepresentation, SkipNode
from tssim.models.shingle import ShingleResult, ShingleSet, ShingledFile
from tssim.pipeline.normalizers import Normalizer

logger = logging.getLogger(__name__)


class ASTShingler:
    """Extracts shingles from tree-sitter ASTs.

    Shingles are structural features extracted from the AST. This implementation
    uses path-based k-grams: sequences of k node representations along paths through the tree.

    Normalizers are applied to each node to potentially skip nodes or modify their
    representations before shingling.
    """

    def __init__(
        self,
        normalizers: list[Normalizer],
        k: int = 3,
        include_text: bool = False,
    ):
        """Initialize the shingler.

        Args:
            normalizers: List of normalizers to apply to nodes
            k: Length of k-grams (number of nodes in each shingle path)
            include_text: If True, include node text in shingles for more specificity
        """
        if k < 1:
            raise ValueError("k must be at least 1")
        self.normalizers = normalizers
        self.k = k
        self.include_text = include_text

    def shingle_file(self, parsed_file: ParsedFile) -> ShingledFile:
        """Extract shingles from a parsed file.

        Args:
            parsed_file: The parsed file to shingle

        Returns:
            ShingledFile with extracted shingles
        """
        shingles = self._extract_shingles(
            parsed_file.root_node,
            parsed_file.language,
            parsed_file.source,
        )

        logger.debug(
            "Extracted %d shingle(s) from %s (k=%d)",
            len(shingles),
            parsed_file.path,
            self.k,
        )

        return ShingledFile(
            path=parsed_file.path,
            language=parsed_file.language,
            shingles=ShingleSet(shingles=shingles),
        )

    def _get_node_representation(
        self,
        node: Node,
        language: str,
        source: bytes,
    ) -> NodeRepresentation:
        """Get the normalized representation of a node.

        Applies all normalizers and returns the final node representation.

        Args:
            node: The tree-sitter node
            language: Programming language
            source: Source code bytes

        Returns:
            NodeRepresentation for the node

        Raises:
            SkipNode: If any normalizer requests this node be skipped
        """
        # Start with defaults
        name = node.type
        value = None

        # Extract value for leaf nodes if include_text is enabled
        if self.include_text and len(node.children) == 0:
            if node.end_byte - node.start_byte < 50:  # Limit value length
                text = source[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")
                # Escape special characters
                value = text.replace("→", "->").replace("\n", "\\n").replace("\t", "\\t")

        # Apply all normalizers
        for normalizer in self.normalizers:
            result = normalizer.normalize_node(node, name, value, language, source)
            if result is not None:
                # Apply modifications
                if result.name is not None:
                    name = result.name
                if result.value is not None:
                    value = result.value

        return NodeRepresentation(name=name, value=value)

    def _extract_shingles(self, root: Node, language: str, source: bytes) -> set[str]:
        """Extract all k-gram shingles from the AST.

        Uses a sliding window approach to extract all paths of length k.
        Applies normalizers to each node, potentially skipping nodes.

        Args:
            root: Root node of the AST
            language: Programming language
            source: Source code bytes

        Returns:
            Set of unique shingles
        """
        shingles: set[str] = set()

        # Pre-order traversal to extract all paths
        def traverse(node: Node, path: deque[NodeRepresentation]) -> None:
            # Get normalized representation (may raise SkipNode)
            try:
                node_repr = self._get_node_representation(node, language, source)
            except SkipNode:
                # Skip this node and its entire subtree
                return

            path.append(node_repr)

            # If path is long enough, create a shingle
            if len(path) >= self.k:
                shingle_path = list(path)[-self.k :]
                shingle = "→".join(str(repr) for repr in shingle_path)
                shingles.add(shingle)

            # Recursively traverse children
            for child in node.children:
                traverse(child, path)

            # Backtrack
            path.pop()

        traverse(root, deque())
        return shingles


def shingle_files(
    parse_result: ParseResult,
    normalizers: list[Normalizer],
    k: int = 3,
    include_text: bool = False,
) -> ShingleResult:
    """Shingle all parsed files.

    Args:
        parse_result: Result from the parse stage
        normalizers: List of normalizers to apply during shingling
        k: Length of k-grams for shingling
        include_text: If True, include node text in shingles

    Returns:
        ShingleResult with shingled files
    """
    logger.info("Shingling %d file(s) with k=%d", len(parse_result.parsed_files), k)

    shingler = ASTShingler(normalizers=normalizers, k=k, include_text=include_text)
    shingled_files = []
    failed_files = dict(parse_result.failed_files)  # Start with parse failures

    for parsed_file in parse_result.parsed_files:
        try:
            shingled_file = shingler.shingle_file(parsed_file)
            shingled_files.append(shingled_file)
        except Exception as e:
            logger.error("Failed to shingle %s: %s", parsed_file.path, e)
            failed_files[parsed_file.path] = str(e)

    logger.info(
        "Shingling complete: %d succeeded, %d failed",
        len(shingled_files),
        len(failed_files) - len(parse_result.failed_files),
    )

    return ShingleResult(
        shingled_files=shingled_files,
        failed_files=failed_files,
    )
