"""Second file with a duplicate code section for testing line-level matching."""


def completely_different_function():
    """This function is completely different."""
    a = 100
    b = 200
    c = a - b
    d = c * 3
    return d / 2


# Some other unique code
name = "test"
version = "1.0"
description = "A test file"
author = "Anonymous"
print(f"File: {name} v{version}")


def yet_another_function():
    """Yet another different function."""
    result = "different"
    return result


# DUPLICATE_SECTION_START - matches with file A
# This is a distinctive duplicate section
numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
results_list = []
for num in numbers:
    doubled = num * 2
    results_list.append(doubled)
sum_of_results = sum(results_list)
print("Sum of doubled numbers:", sum_of_results)
# DUPLICATE_SECTION_END


# More unique content
unique_value = 999
unique_string = "This is unique"
