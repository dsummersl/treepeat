

from typing import Sequence, cast

from pydantic import BaseModel, Field

from treepeat.models.similarity import Region


class Shingle(BaseModel):


    content: str = Field(description="The shingle content (stringified k-gram path)")
    start_line: int = Field(description="Starting line number (1-indexed)")
    end_line: int = Field(description="Ending line number (1-indexed, inclusive)")

    def __str__(self) -> str:
        return self.content

    def __repr__(self) -> str:
        return f"Shingle({self.content!r}, lines {self.start_line}-{self.end_line})"


class ShingleList(BaseModel):


    shingles: Sequence[Shingle | str] = Field(
        description="Set of shingles (with line ranges or legacy strings)"
    )

    @property
    def size(self) -> int:

        return len(self.shingles)

    def get_contents(self) -> list[str]:

        return [s.content if isinstance(s, Shingle) else s for s in self.shingles]

    def __repr__(self) -> str:
        return f"ShingleList(size={self.size})"


class ShingledRegion(BaseModel):


    region: Region = Field(description="The code region")
    shingles: ShingleList = Field(description="Set of shingles extracted from the region")

    @property
    def shingle_count(self) -> int:

        return self.shingles.size


class CompactShingleList(ShingleList):


    @classmethod
    def from_contents(cls, contents: list[str]) -> "CompactShingleList":
        return cls.model_construct(shingles=contents)

    def get_contents(self) -> list[str]:
        return cast(list[str], self.shingles)
