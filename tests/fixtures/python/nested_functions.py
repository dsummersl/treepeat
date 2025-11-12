"""Fixture with nested functions to test region extraction."""


def outer_function():
    """An outer function with nested functions inside."""
    x = 10

    def inner_function_1():
        """First nested function."""
        return x * 2

    def inner_function_2():
        """Second nested function."""
        return x * 3

    result = inner_function_1() + inner_function_2()
    return result


def another_outer():
    """Another outer function with nested methods."""
    data = [1, 2, 3]

    def process():
        """Process the data."""
        return sum(data)

    def transform():
        """Transform the data."""
        return [i * 2 for i in data]

    return process(), transform()


class ClassWithMethods:
    """A class with methods."""

    def method_with_nested(self):
        """A method containing a nested function."""

        def helper():
            """Helper function nested in method."""
            return 42

        return helper() * 2

    def simple_method(self):
        """A simple method without nesting."""
        return 100
