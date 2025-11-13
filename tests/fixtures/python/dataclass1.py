# a file with two similar but not identical classes, and a function

CONSTANT_VALUE_42 = 42

class Model1(BaseModel):
    """ One model """

    region: Region = Field(description="Region metadata")
    node: Node = Field(description="AST node for this region")

class Model2(BaseModel):
    """ Another model """

    model_config = {"arbitrary_types_allowed": True}

    region: Region = Field(description="The region")
    minhash: MinHash = Field(description="MinHash signature")
    shingle_count: int = Field(description="Number of shingles used to create signature")


def my_adapted_one():
    """ A function that computes the sum of first ten natural numbers """
    total = 0
    for i in range(1, 11):
        total += i
    return total
