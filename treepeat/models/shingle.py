"""Models for shingling stage."""

from typing import Sequence

from pydantic import BaseModel, Field

from treepeat.models.similarity import Region


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

    def __repr__(self) -> str:
        return f"ShingleList(size={self.size})"


class ShingledRegion(BaseModel):
    """A region with its extracted shingles."""

    region: Region = Field(description="The code region")
    shingles: ShingleList = Field(description="Set of shingles extracted from the region")

    @property
    def shingle_count(self) -> int:
        """Return the number of unique shingles in this region."""
        return self.shingles.size



