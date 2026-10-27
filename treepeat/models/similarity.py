from pathlib import Path

from datasketch import MinHash  # type: ignore[import-untyped]
from pydantic import BaseModel, Field


class Region(BaseModel):
    path: Path = Field(description="Path to the source file")
    language: str = Field(description="Language (python, javascript, markdown, html, etc)")
    region_type: str = Field(description="Type of region (function, class, heading, section, etc)")
    region_name: str = Field(description="Name or identifier of the region")
    start_line: int = Field(ge=1, description="Start line number (1-indexed)")
    end_line: int = Field(ge=1, description="End line number (1-indexed)")

    def __repr__(self) -> str:

        path_str = str(self.path)[-10:]
        return f"Region({self.region_name} ({self.region_type}) at {path_str}:{self.start_line}-{self.end_line})"


class RegionSignature(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    region: Region = Field(description="The region")
    minhash: MinHash = Field(description="MinHash signature")
    shingle_count: int = Field(description="Number of shingles used to create signature")


class SimilarRegionGroup(BaseModel):
    regions: list[Region] = Field(description="List of similar regions")
    similarity: float = Field(ge=0.0, le=1.0, description="Estimated Jaccard similarity (0.0 to 1.0)")

    @property
    def is_self_similarity(self) -> bool:

        if not self.regions:
            return False
        first_path = self.regions[0].path
        return all(r.path == first_path for r in self.regions)

    @property
    def size(self) -> int:

        return len(self.regions)

    def __repr__(self) -> str:
        region_names = ", ".join(r.region_name for r in self.regions)
        return f"SimilarRegionGroup({self.size} regions: {region_names} {self.similarity:.2%} similar)"


class SimilarityResult(BaseModel):
    signatures: list[RegionSignature] = Field(default_factory=list, description="MinHash signatures for all regions")
    similar_groups: list[SimilarRegionGroup] = Field(
        default_factory=list, description="Groups of similar regions above threshold"
    )

    @property
    def total_files(self) -> int:

        files = {sig.region.path for sig in self.signatures}
        return len(files)

    @property
    def success_count(self) -> int:

        return len(self.signatures)

    @property
    def self_similarity_count(self) -> int:

        return sum(1 for group in self.similar_groups if group.is_self_similarity)
