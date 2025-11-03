"""Normalizer interface and implementations."""

from abc import ABC, abstractmethod

from tssim.models.ast import ParsedFile


class Normalizer(ABC):
    """Base interface for AST normalizers.

    Normalizers transform parsed ASTs to reduce noise and focus on
    structural similarities. Each normalizer can be language-specific
    and can be enabled/disabled via configuration.
    """

    @abstractmethod
    def normalize(self, parsed_file: ParsedFile) -> ParsedFile:
        """Normalize a parsed file's AST.

        Args:
            parsed_file: The parsed file to normalize

        Returns:
            A new ParsedFile with the normalized AST
        """
        pass

    @abstractmethod
    def should_apply(self, parsed_file: ParsedFile) -> bool:
        """Check if this normalizer should be applied to the given file.

        Args:
            parsed_file: The parsed file to check

        Returns:
            True if this normalizer should be applied, False otherwise
        """
        pass
