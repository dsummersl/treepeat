"""Models for similarity detection."""

from pathlib import Path

from datasketch import MinHash  # type: ignore[import-untyped]
from pydantic import BaseModel, Field


class Region(BaseModel):
    """A region within a file (function, class, section, paragraph, etc)."""

    path: Path = Field(description="Path to the source file")
    language: str = Field(description="Language (python, javascript, markdown, html, etc)")
    region_type: str = Field(description="Type of region (function, class, heading, section, etc)")
    region_name: str = Field(description="Name or identifier of the region")
    start_line: int = Field(ge=1, description="Start line number (1-indexed)")
    end_line: int = Field(ge=1, description="End line number (1-indexed)")

    def __repr__(self) -> str:
        """Format as human-readable string."""
        return f"Region({self.region_name} ({self.region_type}) at {str(self.path)[-10:]}:{self.start_line}-{self.end_line})"


class RegionSignature(BaseModel):
    """MinHash signature for a region."""

    model_config = {"arbitrary_types_allowed": True}

    region: Region = Field(description="The region")
    minhash: MinHash = Field(description="MinHash signature")
    shingle_count: int = Field(description="Number of shingles used to create signature")


class SimilarRegionPair(BaseModel):
    """A pair of similar regions with their similarity score."""

    region1: Region = Field(description="First region")
    region2: Region = Field(description="Second region")
    similarity: float = Field(
        ge=0.0, le=1.0, description="Estimated Jaccard similarity (0.0 to 1.0)"
    )

    @property
    def is_self_similarity(self) -> bool:
        """True if both regions are from the same file."""
        return self.region1.path == self.region2.path

    def __repr__(self) -> str:
        return (
            f"SimilarRegionPair({self.region1!r} ↔ {self.region2!r} {self.similarity:.2%} similar)"
        )


class SimilarityResult(BaseModel):
    """Result of similarity detection."""

    signatures: list[RegionSignature] = Field(
        default_factory=list, description="MinHash signatures for all regions"
    )
    similar_pairs: list[SimilarRegionPair] = Field(
        default_factory=list, description="Pairs of similar regions above threshold"
    )
    failed_files: dict[Path, str] = Field(
        default_factory=dict, description="Files that failed processing"
    )

    @property
    def total_regions(self) -> int:
        """Total number of regions processed."""
        return len(self.signatures)

    @property
    def total_files(self) -> int:
        """Total number of unique files processed."""
        files = {sig.region.path for sig in self.signatures}
        return len(files) + len(self.failed_files)

    @property
    def success_count(self) -> int:
        """Number of successfully processed regions."""
        return len(self.signatures)

    @property
    def failure_count(self) -> int:
        """Number of files that failed."""
        return len(self.failed_files)

    @property
    def pair_count(self) -> int:
        """Number of similar pairs found."""
        return len(self.similar_pairs)

    @property
    def self_similarity_count(self) -> int:
        """Number of similar pairs within the same file."""
        return sum(1 for pair in self.similar_pairs if pair.is_self_similarity)
