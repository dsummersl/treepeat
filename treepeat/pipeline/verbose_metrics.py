"""Verbose metrics collection for pipeline runs."""

from dataclasses import dataclass, field


@dataclass
class VerboseMetrics:
    """Container for verbose metrics collected during pipeline run."""

    excluded_node_types_by_language: dict[str, set[str]] = field(default_factory=dict)
    used_node_types_by_language: dict[str, set[str]] = field(default_factory=dict)
    stage_timings: dict[str, float] = field(default_factory=dict)
    stage_counts: dict[str, int] = field(default_factory=dict)


# Global metrics instance
_metrics = VerboseMetrics()


def get_verbose_metrics() -> VerboseMetrics:
    """Get the current verbose metrics."""
    return _metrics


def reset_verbose_metrics() -> None:
    """Reset all verbose metrics."""
    global _metrics
    _metrics = VerboseMetrics()


def record_excluded_node_type(language: str, node_type: str) -> None:
    """Record that a node type was excluded via --ignore-node-types for a language."""
    if language not in _metrics.excluded_node_types_by_language:
        _metrics.excluded_node_types_by_language[language] = set()
    _metrics.excluded_node_types_by_language[language].add(node_type)


def record_used_node_type(language: str, node_type: str) -> None:
    """Record that a node type was used for region analysis."""
    if language not in _metrics.used_node_types_by_language:
        _metrics.used_node_types_by_language[language] = set()
    _metrics.used_node_types_by_language[language].add(node_type)


def record_stage_timing(stage: str, elapsed_s: float) -> None:
    """Record wall-clock time for a pipeline stage."""
    _metrics.stage_timings[stage] = elapsed_s


def record_stage_count(stage: str, count: int) -> None:
    """Record item count produced by a pipeline stage."""
    _metrics.stage_counts[stage] = count
