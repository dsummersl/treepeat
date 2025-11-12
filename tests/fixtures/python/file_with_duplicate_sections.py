"""File with duplicate code sections for testing line-level matching."""


def unique_function_one():
    """A unique function that won't match anything."""
    x = 1
    y = 2
    z = 3
    w = x + y
    v = w + z
    return v * 2


# Some unique code section
value_a = 10
value_b = 20
value_c = 30
value_d = 40
total = value_a + value_b
total += value_c + value_d
print("Total is:", total)


def another_function():
    """Another function to separate sections."""
    msg = "separator"
    return msg


# DUPLICATE_SECTION_START - will match with file B
# This is a distinctive duplicate section
numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
results_list = []
for num in numbers:
    doubled = num * 2
    results_list.append(doubled)
sum_of_results = sum(results_list)
print("Sum of doubled numbers:", sum_of_results)
# DUPLICATE_SECTION_END
