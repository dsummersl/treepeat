"""Models for shingling stage."""

from pathlib import Path
from typing import Sequence

from pydantic import BaseModel, Field

from whorl.models.similarity import Region


class Shingle(BaseModel):
    """A single shingle with its content and line range metadata.

    Shingles are sequences of node types that represent structural patterns.
    Each shingle tracks the line range it spans based on the AST nodes it was extracted from.
    """

    content: str = Field(description="The shingle content (stringified k-gram path)")
    start_line: int = Field(description="Starting line number (1-indexed)")
    end_line: int = Field(description="Ending line number (1-indexed, inclusive)")

    def __str__(self) -> str:
        return self.content

    def __repr__(self) -> str:
        return f"Shingle({self.content!r}, lines {self.start_line}-{self.end_line})"


class ShingleList(BaseModel):
    """A set of shingles extracted from an AST.

    Shingles are sequences of node types that represent structural patterns.
    These will be used for MinHash similarity estimation.
    """

    shingles: Sequence[Shingle | str] = Field(
        description="Set of shingles (with line ranges or legacy strings)"
    )

    @property
    def size(self) -> int:
        """Return the number of unique shingles."""
        return len(self.shingles)

    def get_contents(self) -> list[str]:
        """Get shingle contents as strings (for backward compatibility)."""
        return [s.content if isinstance(s, Shingle) else s for s in self.shingles]

    def _get_shingle_objects(self) -> list[Shingle]:
        """Extract Shingle objects from mixed list."""
        return [s for s in self.shingles if isinstance(s, Shingle)]

    def get_line_range(self) -> tuple[int, int] | None:
        """Get the min/max line range covered by these shingles."""
        shingle_objects = self._get_shingle_objects()
        if not shingle_objects:
            return None
        return (min(s.start_line for s in shingle_objects), max(s.end_line for s in shingle_objects))

    def __repr__(self) -> str:
        return f"ShingleList(size={self.size})"


class ShingledFile(BaseModel):
    """A file with its extracted shingles."""

    model_config = {"arbitrary_types_allowed": True}

    path: Path = Field(description="Path to the source file")
    language: str = Field(description="Programming language of the file")
    shingles: ShingleList = Field(description="Set of shingles extracted from the AST")

    @property
    def shingle_count(self) -> int:
        """Return the number of unique shingles in this file."""
        return self.shingles.size


class ShingledRegion(BaseModel):
    """A region with its extracted shingles."""

    model_config = {"arbitrary_types_allowed": True}

    region: Region = Field(description="The code region")
    shingles: ShingleList = Field(description="Set of shingles extracted from the region")

    @property
    def shingle_count(self) -> int:
        """Return the number of unique shingles in this region."""
        return self.shingles.size


class ShingleResult(BaseModel):
    """Result of shingling multiple files."""

    shingled_files: list[ShingledFile] = Field(
        default_factory=list, description="Successfully shingled files"
    )
    failed_files: dict[Path, str] = Field(
        default_factory=dict, description="Files that failed to shingle with error messages"
    )

    @property
    def total_files(self) -> int:
        """Total number of files processed."""
        return len(self.shingled_files) + len(self.failed_files)

    @property
    def success_count(self) -> int:
        """Number of successfully shingled files."""
        return len(self.shingled_files)

    @property
    def failure_count(self) -> int:
        """Number of files that failed to shingle."""
        return len(self.failed_files)
