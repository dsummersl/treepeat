from pydantic import BaseModel, Field


class NodeRepresentation(BaseModel):
    name: str = Field(description="Node type name (e.g., 'function_definition', 'identifier')")
    value: str | None = Field(
        default=None, description="Node value (e.g., 'my_func', '42') or None for structural nodes"
    )

    def __str__(self) -> str:

        if self.value:
            return f"{self.name}({self.value})"
        return self.name


class SkipNode(Exception):
    pass
