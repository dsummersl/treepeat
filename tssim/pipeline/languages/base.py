"""Base interface for language-specific configuration."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RegionExtractionRule:
    """Configuration for extracting a specific type of region from a language."""

    node_types: list[str]  # Node types to extract (e.g., ["function_definition"])
    region_type: str  # Region type label (e.g., "function")


class LanguageConfig(ABC):
    """Base class for language-specific configuration."""

    @abstractmethod
    def get_language_name(self) -> str:
        """Return the primary language name."""
        pass

    @abstractmethod
    def get_default_rules(self) -> list[str]:
        """Return list of rule strings for default normalization mode."""
        pass

    @abstractmethod
    def get_loose_rules(self) -> list[str]:
        """Return list of rule strings for loose normalization mode (includes default rules)."""
        pass

    @abstractmethod
    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        """Return list of region extraction rules for this language."""
        pass
