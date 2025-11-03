"""Shingling pipeline stage.

This module extracts shingles (structural features) from ASTs for similarity detection.
Shingles are k-gram paths through the AST that capture structural patterns.
"""

import logging
from collections import deque

from tree_sitter import Node

from tssim.models.ast import ParsedFile, ParseResult
from tssim.models.normalization import NodeRepresentation, SkipNode
from tssim.models.shingle import ShingledRegion, ShingleResult, ShingleSet, ShingledFile
from tssim.pipeline.normalizers import Normalizer
from tssim.pipeline.region_extraction import ExtractedRegion

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

    def shingle_region(self, extracted_region: ExtractedRegion, source: bytes) -> ShingledRegion:
        """Extract shingles from a code region.

        Args:
            extracted_region: The region with its AST node to shingle
            source: Source code bytes (from the parsed file)

        Returns:
            ShingledRegion with extracted shingles
        """
        region = extracted_region.region
        shingles = self._extract_shingles(
            extracted_region.node,
            region.language,
            source,
        )

        logger.debug(
            "Extracted %d shingle(s) from %s (k=%d)",
            len(shingles),
            region.region_name,
            self.k,
        )

        return ShingledRegion(
            region=region,
            shingles=ShingleSet(shingles=shingles),
        )

    def _extract_node_value(self, node: Node, source: bytes) -> str | None:
        """Extract text value from a leaf node.

        Args:
            node: The tree-sitter node
            source: Source code bytes

        Returns:
            Extracted and escaped text value, or None
        """
        if not self.include_text or len(node.children) != 0:
            return None

        if node.end_byte - node.start_byte >= 50:  # Limit value length
            return None

        text = source[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")
        return text.replace("→", "->").replace("\n", "\\n").replace("\t", "\\t")

    def _apply_normalizers(
        self,
        node: Node,
        name: str,
        value: str | None,
        language: str,
        source: bytes,
    ) -> tuple[str, str | None]:
        """Apply all normalizers to a node.

        Args:
            node: The tree-sitter node
            name: Initial node name
            value: Initial node value
            language: Programming language
            source: Source code bytes

        Returns:
            Tuple of (final_name, final_value)

        Raises:
            SkipNode: If any normalizer requests this node be skipped
        """
        for normalizer in self.normalizers:
            result = normalizer.normalize_node(node, name, value, language, source)
            if result is not None:
                if result.name is not None:
                    name = result.name
                if result.value is not None:
                    value = result.value
        return name, value

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
        name = node.type
        value = self._extract_node_value(node, source)
        name, value = self._apply_normalizers(node, name, value, language, source)
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


def shingle_regions(
    extracted_regions: list[ExtractedRegion],
    parsed_files: list[ParsedFile],
    normalizers: list[Normalizer],
    k: int = 3,
    include_text: bool = False,
) -> list[ShingledRegion]:
    """Shingle all extracted regions.

    Args:
        extracted_regions: Regions extracted from parsed files
        parsed_files: Original parsed files (needed for source bytes)
        normalizers: List of normalizers to apply during shingling
        k: Length of k-grams for shingling
        include_text: If True, include node text in shingles

    Returns:
        List of shingled regions
    """
    logger.info(
        "Shingling %d region(s) across %d file(s) with k=%d",
        len(extracted_regions),
        len(parsed_files),
        k,
    )

    # Create a map from path to source bytes for efficient lookup
    path_to_source = {pf.path: pf.source for pf in parsed_files}

    shingler = ASTShingler(normalizers=normalizers, k=k, include_text=include_text)
    shingled_regions = []

    for extracted_region in extracted_regions:
        try:
            source = path_to_source.get(extracted_region.region.path)
            if source is None:
                logger.error(
                    "Source not found for region %s in %s",
                    extracted_region.region.region_name,
                    extracted_region.region.path,
                )
                continue

            shingled_region = shingler.shingle_region(extracted_region, source)
            shingled_regions.append(shingled_region)
        except Exception as e:
            logger.error(
                "Failed to shingle region %s: %s", extracted_region.region.region_name, e
            )

    logger.info("Shingling complete: %d region(s) shingled", len(shingled_regions))
    return shingled_regions
