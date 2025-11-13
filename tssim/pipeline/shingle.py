import logging
from collections import deque
from pathlib import Path

from tree_sitter import Node

from tssim.models.ast import ParsedFile, ParseResult
from tssim.models.normalization import NodeRepresentation, SkipNode
from tssim.models.shingle import ShingledRegion, ShingleResult, ShingleList, ShingledFile
from tssim.pipeline.normalizers import Normalizer
from tssim.pipeline.region_extraction import ExtractedRegion

logger = logging.getLogger(__name__)

# Maximum length for node values in shingles (longer values are truncated)
MAX_NODE_VALUE_LENGTH = 50


class ASTShingler:
    def __init__(
        self,
        normalizers: list[Normalizer],
        k: int = 3,
    ):
        if k < 1:
            raise ValueError("k must be at least 1")
        self.normalizers = normalizers
        self.k = k

    def shingle_file(self, parsed_file: ParsedFile) -> ShingledFile:
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
            shingles=ShingleList(shingles=shingles),
        )

    def shingle_region(self, extracted_region: ExtractedRegion, source: bytes) -> ShingledRegion:
        region = extracted_region.region

        # If region has multiple nodes (section regions), extract shingles from all
        if extracted_region.nodes is not None:
            all_shingles: list[str] = []
            for node in extracted_region.nodes:
                node_shingles = self._extract_shingles(node, region.language, source)
                all_shingles.extend(node_shingles)
            shingles = all_shingles
        else:
            # Single node region (target regions like functions/classes or line-based regions)
            # For line-based regions, we need to filter nodes by line range
            start_line = region.start_line if region.region_type == "lines" else None
            end_line = region.end_line if region.region_type == "lines" else None
            shingles = self._extract_shingles(
                extracted_region.node,
                region.language,
                source,
                start_line=start_line,
                end_line=end_line,
            )

        logger.debug(
            "Extracted %d shingle(s) from %s (k=%d)",
            len(shingles),
            region.region_name,
            self.k,
        )

        return ShingledRegion(
            region=region,
            shingles=ShingleList(shingles=shingles),
        )

    def _extract_node_value(self, node: Node, source: bytes) -> str | None:
        if len(node.children) != 0:
            return None

        text = source[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")
        text = text.replace("→", "->").replace("\n", "\\n").replace("\t", "\\t")

        # Truncate long values instead of dropping them
        if len(text) > MAX_NODE_VALUE_LENGTH:
            text = text[:MAX_NODE_VALUE_LENGTH]

        return text

    def _apply_normalizers(
        self,
        node: Node,
        name: str,
        value: str | None,
        language: str,
        source: bytes,
    ) -> tuple[str, str | None]:
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
        name = node.type
        value = self._extract_node_value(node, source)
        name, value = self._apply_normalizers(node, name, value, language, source)
        return NodeRepresentation(name=name, value=value)

    def _extract_shingles(
        self,
        root: Node,
        language: str,
        source: bytes,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> list[str]:
        shingles: list[str] = []

        # Pre-order traversal to extract all paths
        def traverse(node: Node, path: deque[NodeRepresentation]) -> None:
            # Filter nodes by line range if specified (for line-based regions)
            if start_line is not None and end_line is not None:
                node_start = node.start_point[0] + 1  # Convert 0-indexed to 1-indexed
                node_end = node.end_point[0] + 1
                # Skip nodes that are completely outside the line range
                if node_end < start_line or node_start > end_line:
                    return

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
                shingles.append(shingle)

            # Recursively traverse children
            for child in node.children:
                traverse(child, path)

            # Backtrack
            _ = path.pop()

        traverse(root, deque())
        return shingles


def shingle_files(
    parse_result: ParseResult,
    normalizers: list[Normalizer],
    k: int = 3,
) -> ShingleResult:
    logger.info("Shingling %d file(s) with k=%d", len(parse_result.parsed_files), k)

    shingler = ASTShingler(normalizers=normalizers, k=k)
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


def _shingle_single_region(
    extracted_region: ExtractedRegion,
    path_to_source: dict[Path, bytes],
    shingler: ASTShingler,
) -> ShingledRegion | None:
    source = path_to_source.get(extracted_region.region.path)
    if source is None:
        logger.error(
            "Source not found for region %s in %s",
            extracted_region.region.region_name,
            extracted_region.region.path,
        )
        return None

    return shingler.shingle_region(extracted_region, source)


def shingle_regions(
    extracted_regions: list[ExtractedRegion],
    parsed_files: list[ParsedFile],
    normalizers: list[Normalizer],
    k: int = 3,
) -> list[ShingledRegion]:
    logger.info(
        "Shingling %d region(s) across %d file(s) with k=%d",
        len(extracted_regions),
        len(parsed_files),
        k,
    )

    path_to_source = {pf.path: pf.source for pf in parsed_files}
    shingler = ASTShingler(normalizers=normalizers, k=k)
    shingled_regions = []
    filtered_count = 0

    for extracted_region in extracted_regions:
        try:
            shingled_region = _shingle_single_region(
                extracted_region, path_to_source, shingler
            )
            if shingled_region is not None:
                shingled_regions.append(shingled_region)
            else:
                filtered_count += 1
        except Exception as e:
            logger.error(
                "Failed to shingle region %s: %s", extracted_region.region.region_name, e
            )

    logger.info(
        "Shingling complete: %d region(s) shingled, %d filtered",
        len(shingled_regions),
        filtered_count
    )
    return shingled_regions
