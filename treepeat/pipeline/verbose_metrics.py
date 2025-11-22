"""Verbose metrics collection for pipeline runs."""

from collections import Counter
from dataclasses import dataclass, field


@dataclass
class VerboseMetrics:
    """Container for verbose metrics collected during pipeline run."""

    ignored_node_types: Counter[str] = field(default_factory=Counter)
    used_node_types_by_language: dict[str, Counter[str]] = field(default_factory=dict)


# Global metrics instance
_metrics = VerboseMetrics()


def get_verbose_metrics() -> VerboseMetrics:
    """Get the current verbose metrics."""
    return _metrics


def reset_verbose_metrics() -> None:
    """Reset all verbose metrics."""
    global _metrics
    _metrics = VerboseMetrics()


def record_ignored_node_type(node_type: str, count: int = 1) -> None:
    """Record that a node type was ignored."""
    _metrics.ignored_node_types[node_type] += count


def record_used_node_type(language: str, node_type: str, count: int = 1) -> None:
    """Record that a node type was used for a language."""
    if language not in _metrics.used_node_types_by_language:
        _metrics.used_node_types_by_language[language] = Counter()
    _metrics.used_node_types_by_language[language][node_type] += count
