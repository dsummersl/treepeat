from abc import ABC, abstractmethod
from dataclasses import dataclass

from treepeat.pipeline.rules.models import Rule, TargetLanguage


@dataclass
class RegionExtractionRule:
    """Configuration for extracting a specific type of region from a language."""

    label: str
    query: str
    # When set, the matched node's content is re-parsed as this language so the
    # shingler produces target-language-quality shingles (language injection).
    # May be a static string ("typescript") or a callable that resolves the
    # language dynamically from the matched node (e.g. Markdown code blocks).
    target_language: TargetLanguage = None
    # Optional tree-sitter query (compiled against the *primary* language
    # grammar) that selects the child node whose raw bytes are injected.
    # When None, the entire matched node's bytes are used.
    content_query: str | None = None

    @classmethod
    def from_node_type(cls, node_type: str) -> "RegionExtractionRule":
        return cls(
            label=node_type,
            query=f"({node_type}) @region",
        )


class LanguageConfig(ABC):
    """Base class for language-specific configuration."""

    @abstractmethod
    def get_default_rules(self) -> list[Rule]:
        """Return list of Rule objects for default normalization mode."""
        pass

    @abstractmethod
    def get_loose_rules(self) -> list[Rule]:
        """Return list of Rule objects for loose normalization mode (including default rules)."""
        pass

    @abstractmethod
    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        """Return list of regions to perform similarity comparisons for this language."""
        pass
