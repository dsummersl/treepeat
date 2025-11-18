from abc import ABC, abstractmethod
from dataclasses import dataclass

from treepeat.pipeline.rules.models import Rule


@dataclass
class RegionExtractionRule:
    """Configuration for extracting a specific type of region from a language."""

    query: str  # TreeSitter query to match nodes (e.g., "(function_definition) @region")
    region_type: str  # Region type label (e.g., "function")


class LanguageConfig(ABC):
    """Base class for language-specific configuration."""

    @abstractmethod
    def get_language_name(self) -> str:
        """Return the primary language name."""
        pass

    @abstractmethod
    def get_default_rules(self) -> list[Rule]:
        """Return list of Rule objects for default normalization mode."""
        pass

    @abstractmethod
    def get_loose_rules(self) -> list[Rule]:
        """Return list of Rule objects for loose normalization mode (includes default rules)."""
        pass

    @abstractmethod
    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        """Return list of region extraction rules for this language."""
        pass
