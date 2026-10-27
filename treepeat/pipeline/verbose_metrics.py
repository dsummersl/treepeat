from dataclasses import dataclass, field


@dataclass
class VerboseMetrics:
    excluded_node_types_by_language: dict[str, set[str]] = field(default_factory=dict)
    used_node_types_by_language: dict[str, set[str]] = field(default_factory=dict)
    stage_timings: dict[str, float] = field(default_factory=dict)
    stage_counts: dict[str, int] = field(default_factory=dict)


_metrics = VerboseMetrics()


def get_verbose_metrics() -> VerboseMetrics:

    return _metrics


def reset_verbose_metrics() -> None:

    global _metrics
    _metrics = VerboseMetrics()


def record_used_node_type(language: str, node_type: str) -> None:

    if language not in _metrics.used_node_types_by_language:
        _metrics.used_node_types_by_language[language] = set()
    _metrics.used_node_types_by_language[language].add(node_type)


def record_stage_timing(stage: str, elapsed_s: float) -> None:

    _metrics.stage_timings[stage] = elapsed_s


def record_stage_count(stage: str, count: int) -> None:

    _metrics.stage_counts[stage] = count
