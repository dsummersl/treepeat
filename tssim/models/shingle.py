"""Models for shingling stage."""

from pathlib import Path

from pydantic import BaseModel, Field

from tssim.models.similarity import Region


class ShingleList(BaseModel):
    """A set of shingles extracted from an AST.

    Shingles are sequences of node types that represent structural patterns.
    These will be used for MinHash similarity estimation.
    """

    shingles: list[str] = Field(
        description="Set of unique shingles (stringified k-gram paths through the AST)"
    )

    @property
    def size(self) -> int:
        """Return the number of unique shingles."""
        return len(self.shingles)

    def __repr__(self):
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
