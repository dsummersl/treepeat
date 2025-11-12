"""Second file with small functions to test min_lines filtering."""


def small_duplicate():
    """Small function - duplicate but should be filtered out by min_lines."""
    return 1


def large_duplicate():
    """Large function - duplicate and should pass min_lines threshold."""
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    result = []
    for item in data:
        if item % 2 == 0:
            result.append(item * 2)
        else:
            result.append(item)
    return result


def different_small():
    """Different small function."""
    y = 20
    return y
