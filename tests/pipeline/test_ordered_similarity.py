"""Order-sensitive shingle similarity used by group verification."""

import random

import pytest

from treepeat.pipeline.verification import _compute_ordered_similarity


def _lcs_length(a: list[str], b: list[str]) -> int:
    """Reference O(n*m) longest-common-subsequence length."""
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b):
            cur.append(prev[j] + 1 if x == y else max(prev[j + 1], cur[j]))
        prev = cur
    return prev[-1]


def test_identical_sequences_are_fully_similar():
    seq = ["a", "b", "c", "d"]
    assert _compute_ordered_similarity(seq, list(seq)) == 1.0


def test_disjoint_sequences_have_zero_similarity():
    assert _compute_ordered_similarity(["a", "b"], ["c", "d"]) == 0.0


@pytest.mark.parametrize("left,right", [([], ["a"]), (["a"], []), ([], [])])
def test_empty_sequences_have_zero_similarity(left, right):
    assert _compute_ordered_similarity(left, right) == 0.0


def test_order_matters():
    assert _compute_ordered_similarity(["a", "b", "c"], ["c", "b", "a"]) < 0.5


def test_insertion_is_tolerated():
    # LCS = 4, so 2 * 4 / (4 + 5)
    assert _compute_ordered_similarity(["a", "b", "c", "d"], ["a", "b", "x", "c", "d"]) == pytest.approx(8 / 9)


def test_is_symmetric():
    a, b = ["a", "b", "c", "a", "d"], ["b", "a", "c", "d", "d", "a"]
    assert _compute_ordered_similarity(a, b) == pytest.approx(_compute_ordered_similarity(b, a))


def test_matches_lcs_reference_on_random_inputs():
    rng = random.Random(1234)
    alphabet = ["tok_a", "tok_b", "tok_c", "tok_d", "tok_e"]
    for _ in range(200):
        a = [rng.choice(alphabet) for _ in range(rng.randint(1, 40))]
        b = [rng.choice(alphabet) for _ in range(rng.randint(1, 40))]
        expected = 2 * _lcs_length(a, b) / (len(a) + len(b))
        assert _compute_ordered_similarity(a, b) == pytest.approx(expected)


def test_handles_large_repetitive_inputs():
    a = ["x"] * 20_000 + ["y"] * 20_000
    b = ["x"] * 20_000 + ["z"] + ["y"] * 20_000
    assert _compute_ordered_similarity(a, b) == pytest.approx(80_000 / 80_001)
