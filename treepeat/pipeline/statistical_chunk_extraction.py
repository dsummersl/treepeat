import logging
from collections import Counter
from dataclasses import dataclass
from tree_sitter import Node

from treepeat.config import get_settings
from treepeat.models.ast import ParsedFile
from treepeat.pipeline.region_extraction import ExtractedRegion
from treepeat.pipeline.auto_chunk_extraction import (
    _calculate_node_lines,
    _create_chunk_region,
)
from treepeat.pipeline.verbose_metrics import record_ignored_node_type, record_used_node_type

logger = logging.getLogger(__name__)


@dataclass
class ChunkStats:
    """Statistics about chunks found in a file."""

    total_chunks: int
    file_lines: int
    node_type_counts: Counter[str]  # node_type -> count
    node_type_sizes: dict[str, list[int]]  # node_type -> [sizes]
    chunks_by_type: dict[str, list[Node]]  # node_type -> [nodes]


def _collect_all_chunks(root: Node, min_lines: int) -> list[Node]:
    """Collect ALL potential chunks (leaf nodes meeting min_lines).

    This is the same as auto_chunk_extraction but collects rather than
    filters, so we can analyze statistics before deciding what to keep.
    """
    chunks = []

    def traverse(node: Node) -> bool:
        node_lines = _calculate_node_lines(node)

        if node_lines < min_lines:
            return False

        has_chunk_children = False
        for child in node.children:
            if traverse(child):
                has_chunk_children = True

        if not has_chunk_children:
            chunks.append(node)
            return True

        return True

    traverse(root)
    return chunks


def _analyze_chunks(chunks: list[Node], file_lines: int) -> ChunkStats:
    """Analyze statistical properties of chunks."""
    node_type_counts: Counter[str] = Counter()
    node_type_sizes: dict[str, list[int]] = {}
    chunks_by_type: dict[str, list[Node]] = {}

    for chunk in chunks:
        node_type = chunk.type
        chunk_lines = _calculate_node_lines(chunk)

        node_type_counts[node_type] += 1

        if node_type not in node_type_sizes:
            node_type_sizes[node_type] = []
            chunks_by_type[node_type] = []

        node_type_sizes[node_type].append(chunk_lines)
        chunks_by_type[node_type].append(chunk)

    return ChunkStats(
        total_chunks=len(chunks),
        file_lines=file_lines,
        node_type_counts=node_type_counts,
        node_type_sizes=node_type_sizes,
        chunks_by_type=chunks_by_type,
    )


def _get_all_chunks_from_stats(stats: ChunkStats) -> list[Node]:
    """Extract all chunks from stats."""
    return [chunk for chunks in stats.chunks_by_type.values() for chunk in chunks]


def _process_node_type_for_frequency(
    node_type: str,
    chunks: list[Node],
    total_chunks: int,
    max_frequency_ratio: float,
) -> list[Node]:
    """Process a single node type for frequency filtering."""
    frequency_ratio = len(chunks) / total_chunks
    if frequency_ratio <= max_frequency_ratio:
        logger.debug(
            "Keeping node type '%s': %d chunks (%.1f%% frequency)",
            node_type,
            len(chunks),
            frequency_ratio * 100,
        )
        return list(chunks)

    logger.debug(
        "Filtering out node type '%s': too frequent (%d chunks, %.1f%%)",
        node_type,
        len(chunks),
        frequency_ratio * 100,
    )
    return []


def _filter_by_frequency(
    stats: ChunkStats,
    max_frequency_ratio: float = 0.3,
    min_total_chunks: int = 10,
) -> list[Node]:
    """Filter out node types that appear too frequently.

    The intuition: If a node type appears many times (>30% of all chunks),
    it's probably too granular (like 'argument_list' or 'parameter').

    Only applies when total_chunks >= min_total_chunks to avoid filtering
    everything when there are very few chunks.

    Args:
        stats: Chunk statistics
        max_frequency_ratio: Maximum ratio of chunks that can be same type
        min_total_chunks: Minimum total chunks before applying frequency filter

    Returns:
        Filtered list of chunks
    """
    # Don't apply frequency filter if there are too few chunks
    if stats.total_chunks < min_total_chunks:
        logger.debug(
            "Skipping frequency filter: only %d chunks (need %d)",
            stats.total_chunks,
            min_total_chunks,
        )
        return _get_all_chunks_from_stats(stats)

    filtered_chunks = []
    for node_type, chunks in stats.chunks_by_type.items():
        filtered_chunks.extend(
            _process_node_type_for_frequency(
                node_type, chunks, stats.total_chunks, max_frequency_ratio
            )
        )

    return filtered_chunks


def _filter_by_size_percentile(
    chunks: list[Node],
    min_percentile: float = 0.5,
) -> list[Node]:
    """Keep only chunks above a size percentile.

    The intuition: Smaller chunks are often less interesting. Keep the
    larger half (or top 75%, etc.) of chunks.

    Args:
        chunks: List of chunk nodes
        min_percentile: Minimum percentile to keep (0.5 = median and above)

    Returns:
        Filtered list of chunks
    """
    if not chunks:
        return []

    sizes = [_calculate_node_lines(chunk) for chunk in chunks]
    sizes_sorted = sorted(sizes)
    percentile_index = int(len(sizes_sorted) * min_percentile)
    threshold = sizes_sorted[percentile_index]

    filtered = [chunk for chunk in chunks if _calculate_node_lines(chunk) >= threshold]

    logger.debug(
        "Size percentile filter (%.0f%%): %d -> %d chunks (threshold: %d lines)",
        min_percentile * 100,
        len(chunks),
        len(filtered),
        threshold,
    )

    return filtered


def _filter_by_size_range(
    chunks: list[Node],
    file_lines: int,
    min_file_ratio: float = 0.05,
    max_file_ratio: float = 0.9,
) -> list[Node]:
    """Keep chunks in a size range relative to file size.

    The intuition: Chunks should be neither too small (< 5% of file)
    nor too large (> 90% of file) to be meaningful.

    Args:
        chunks: List of chunk nodes
        file_lines: Total lines in file
        min_file_ratio: Minimum ratio of file size
        max_file_ratio: Maximum ratio of file size

    Returns:
        Filtered list of chunks
    """
    min_lines = int(file_lines * min_file_ratio)
    max_lines = int(file_lines * max_file_ratio)

    filtered = [
        chunk
        for chunk in chunks
        if min_lines <= _calculate_node_lines(chunk) <= max_lines
    ]

    logger.debug(
        "Size range filter (%.1f%%-%.1f%% of file): %d -> %d chunks (range: %d-%d lines)",
        min_file_ratio * 100,
        max_file_ratio * 100,
        len(chunks),
        len(filtered),
        min_lines,
        max_lines,
    )

    return filtered


def _partition_chunks_by_ignore(
    chunks: list[Node],
    ignore_node_types: list[str],
) -> tuple[list[Node], Counter[str]]:
    """Partition chunks into kept and ignored, returning counts of ignored types."""
    filtered = []
    ignored_counts: Counter[str] = Counter()
    ignore_set = set(ignore_node_types)
    for chunk in chunks:
        if chunk.type in ignore_set:
            ignored_counts[chunk.type] += 1
        else:
            filtered.append(chunk)
    return filtered, ignored_counts


def _filter_by_ignored_types(
    chunks: list[Node],
    ignore_node_types: list[str],
) -> list[Node]:
    """Filter out chunks whose node type is in the ignore list."""
    if not ignore_node_types:
        return chunks

    filtered, ignored_counts = _partition_chunks_by_ignore(chunks, ignore_node_types)

    # Record ignored node types for verbose output
    for node_type, count in ignored_counts.items():
        record_ignored_node_type(node_type, count)

    if len(filtered) < len(chunks):
        ignored_count = len(chunks) - len(filtered)
        logger.debug(
            "Ignored %d chunks with types: %s",
            ignored_count,
            ", ".join(ignore_node_types),
        )

    return filtered


def _apply_statistical_filters(
    chunks: list[Node],
    stats: ChunkStats,
    max_frequency_ratio: float,
    min_percentile: float,
    min_file_ratio: float,
    max_file_ratio: float,
) -> list[Node]:
    """Apply all statistical filters in sequence."""
    # Apply frequency filter
    filtered = _filter_by_frequency(stats, max_frequency_ratio)

    # Apply size percentile filter
    if filtered:
        filtered = _filter_by_size_percentile(filtered, min_percentile)

    # Apply size range filter
    if filtered:
        filtered = _filter_by_size_range(
            filtered, stats.file_lines, min_file_ratio, max_file_ratio
        )

    return filtered


def _apply_ignore_node_types_filter(chunks: list[Node], file_path: str) -> list[Node] | None:
    """Apply ignore_node_types filter if configured. Returns None if all chunks filtered out."""
    settings = get_settings()
    if not settings.lsh.ignore_node_types:
        return chunks

    filtered = _filter_by_ignored_types(chunks, settings.lsh.ignore_node_types)
    if not filtered:
        logger.info("All chunks filtered out by ignore_node_types for %s", file_path)
        return None

    logger.debug("After ignoring types: %d chunks", len(filtered))
    return filtered


def _log_chunk_type_summary(regions: list[ExtractedRegion]) -> None:
    """Log summary of region types found."""
    type_counts = Counter(r.region.region_type for r in regions)
    for node_type, count in type_counts.most_common():
        logger.debug("  %s: %d chunks", node_type, count)


def extract_chunks_statistical(
    parsed_file: ParsedFile,
    min_lines: int = 5,
    max_frequency_ratio: float = 0.4,
    min_percentile: float = 0.3,
    min_file_ratio: float = 0.0,  # Disabled by default (min_lines handles this)
    max_file_ratio: float = 1.0,  # Disabled by default
) -> list[ExtractedRegion]:
    """Extract chunks using statistical filtering.

    This combines multiple heuristics to find meaningful chunks:
    1. Start with all leaf chunks (min_lines threshold)
    2. Filter out node types that appear too frequently
    3. Filter by size percentile (keep larger chunks)
    4. Filter by size range relative to file (not too small/large)

    Args:
        parsed_file: Parsed source file
        min_lines: Minimum lines for initial chunk discovery
        max_frequency_ratio: Max frequency for a node type (default: 40%)
        min_percentile: Min size percentile to keep (default: 30%)
        min_file_ratio: Min chunk size as ratio of file (default: 0% = disabled)
        max_file_ratio: Max chunk size as ratio of file (default: 100% = disabled)

    Returns:
        Filtered list of extracted regions
    """
    logger.info(
        "Statistical chunking: %s (%s) with min_lines=%d",
        parsed_file.path,
        parsed_file.language,
        min_lines,
    )

    # Collect all potential chunks
    all_chunks = _collect_all_chunks(parsed_file.root_node, min_lines)
    if not all_chunks:
        logger.info("No chunks found for %s", parsed_file.path)
        return []

    logger.debug("Initial chunks: %d", len(all_chunks))

    # Filter out ignored node types early
    filtered_chunks = _apply_ignore_node_types_filter(all_chunks, str(parsed_file.path))
    if filtered_chunks is None:
        return []
    all_chunks = filtered_chunks

    # Analyze statistics and apply filters
    file_lines = _calculate_node_lines(parsed_file.root_node)
    stats = _analyze_chunks(all_chunks, file_lines)
    chunks = _apply_statistical_filters(
        all_chunks, stats, max_frequency_ratio, min_percentile, min_file_ratio, max_file_ratio
    )

    # Convert to ExtractedRegion objects
    regions = [_create_chunk_region(node, parsed_file) for node in chunks]

    # Record used node types for verbose output
    type_counts = Counter(r.region.region_type for r in regions)
    for node_type, count in type_counts.items():
        record_used_node_type(parsed_file.language, node_type, count)

    logger.info(
        "Statistical chunking: %d -> %d chunks after filtering",
        len(all_chunks),
        len(regions),
    )

    _log_chunk_type_summary(regions)
    return regions


def extract_chunks_adaptive(
    parsed_file: ParsedFile,
    min_lines: int = 5,
    target_chunk_count: int = 10,
) -> list[ExtractedRegion]:
    """Extract chunks with adaptive filtering to hit a target count.

    This variant tries to automatically adjust filtering parameters
    to achieve approximately the target number of chunks.

    Args:
        parsed_file: Parsed source file
        min_lines: Minimum lines for chunk discovery
        target_chunk_count: Desired number of chunks (approximate)

    Returns:
        Filtered list of extracted regions
    """
    logger.info(
        "Adaptive chunking: %s (target: %d chunks)",
        parsed_file.path,
        target_chunk_count,
    )

    # Collect all chunks
    all_chunks = _collect_all_chunks(parsed_file.root_node, min_lines)
    if not all_chunks:
        return []

    # If we already have few chunks, return them all
    if len(all_chunks) <= target_chunk_count:
        logger.info(
            "Already at/below target: %d chunks", len(all_chunks)
        )
        return [_create_chunk_region(node, parsed_file) for node in all_chunks]

    # Calculate what percentile would give us target_chunk_count
    target_ratio = target_chunk_count / len(all_chunks)
    # Use inverse percentile (if we want 10 out of 30, use 66th percentile)
    min_percentile = max(0.0, 1.0 - target_ratio)

    logger.debug(
        "Adaptive filtering: %d chunks -> target %d (using %.0f%% percentile)",
        len(all_chunks),
        target_chunk_count,
        min_percentile * 100,
    )

    # Apply size percentile filter
    chunks = _filter_by_size_percentile(all_chunks, min_percentile)

    # Convert to regions
    regions = [_create_chunk_region(node, parsed_file) for node in chunks]

    logger.info(
        "Adaptive chunking: %d -> %d chunks (target was %d)",
        len(all_chunks),
        len(regions),
        target_chunk_count,
    )

    return regions
