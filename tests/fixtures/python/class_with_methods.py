"""Fixture demonstrating classes with some duplicate and some different methods."""


class ClassA:
    """Original class with three methods."""

    def method1(self):
        """First method - will be rewritten in ClassB."""
        x = 10
        y = 20
        return x + y

    def method2(self):
        """Second method - will be duplicated in ClassB."""
        data = [1, 2, 3, 4, 5]
        total = 0
        for item in data:
            total += item
        return total

    def method3(self):
        """Third method - will be duplicated in ClassB."""
        result = []
        for i in range(10):
            if i % 2 == 0:
                result.append(i)
        return result


class ClassB:
    """Copy of ClassA with method1 rewritten."""

    def method1_renamed(self):
        """Rewritten version of method1 - different implementation."""
        a = 5
        b = 10
        c = 15
        return a + b + c

    def method2(self):
        """Second method - duplicate of ClassA.method2."""
        data = [1, 2, 3, 4, 5]
        total = 0
        for item in data:
            total += item
        return total

    def method3(self):
        """Third method - duplicate of ClassA.method3."""
        result = []
        for i in range(10):
            if i % 2 == 0:
                result.append(i)
        return result


class ClassC:
    """Completely different class."""

    def different_method(self):
        """A completely different method."""
        return "This is different"

    def another_different_method(self):
        """Another different method."""
        value = 100
        return value * 2
