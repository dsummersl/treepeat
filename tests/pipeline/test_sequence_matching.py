import itertools
import random
from difflib import SequenceMatcher

from treepeat.pipeline.sequence_matching import _longest_match, ordered_ratio


def test_longest_match_matches_difflib_exhaustively_including_ties():
    sequences = [list(p) for n in range(6) for p in itertools.product("ab", repeat=n)]
    for a in sequences:
        for b in sequences:
            reference = SequenceMatcher(None, a, b, autojunk=False).find_longest_match()
            assert _longest_match(a, b, (0, len(a), 0, len(b))) == reference


def test_partition_bounds_preserve_earliest_occurrence():
    randomizer = random.Random(9283)
    for _ in range(500):
        a, b = [[randomizer.choice("abca") for _ in range(60)] for _ in range(2)]
        start_a, end_a = sorted(randomizer.sample(range(len(a) + 1), 2))
        start_b, end_b = sorted(randomizer.sample(range(len(b) + 1), 2))
        bounds = (start_a, end_a, start_b, end_b)
        expected = SequenceMatcher(None, a, b, autojunk=False).find_longest_match(*bounds)
        assert _longest_match(a, b, bounds) == expected


def test_partitioned_scores_match_reference_on_repetitive_and_unrelated_sequences():
    randomizer = random.Random(19)
    for index in range(150):
        a = [randomizer.choice("abcd") for _ in range(randomizer.randrange(256, 600))]
        b = [randomizer.choice("abcd") for _ in range(randomizer.randrange(256, 600))]
        if index % 2:
            b = a[:]
            for _ in range(20):
                b[randomizer.randrange(len(b))] = randomizer.choice("abcd")
        assert ordered_ratio(a, b) == SequenceMatcher(None, a, b, autojunk=False).ratio()


def test_large_repeated_sequences_keep_popular_tokens_and_exact_score():
    a, b = ["a", "b"] * 50000, ["b", "a"] * 50000
    assert ordered_ratio(a, b) == 0.99999
    assert ordered_ratio(["a"] * 100000, ["b"] * 100000) == 0.0
