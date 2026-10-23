from dataclasses import dataclass, field
from difflib import Match, SequenceMatcher


@dataclass(slots=True)
class _State:
    length: int = 0
    link: int = -1
    first_end: int = -1
    transitions: dict[str, int] = field(default_factory=dict)


class _SuffixAutomaton:
    """Index substrings and their earliest occurrence in linear space."""

    def __init__(self, sequence: list[str], start: int, end: int):
        self.states = [_State()]
        last = 0
        for position in range(start, end):
            last = self._extend(last, sequence[position], position)

    def _extend(self, last: int, token: str, position: int) -> int:
        current = len(self.states)
        self.states.append(_State(length=self.states[last].length + 1, first_end=position))
        previous = last
        while previous >= 0 and token not in self.states[previous].transitions:
            self.states[previous].transitions[token] = current
            previous = self.states[previous].link
        self.states[current].link = self._suffix_link(previous, token)
        return current

    def _suffix_link(self, previous: int, token: str) -> int:
        if previous < 0:
            return 0
        target = self.states[previous].transitions[token]
        if self.states[previous].length + 1 == self.states[target].length:
            return target
        clone = len(self.states)
        original = self.states[target]
        self.states.append(_State(
            length=self.states[previous].length + 1, link=original.link,
            first_end=original.first_end, transitions=original.transitions.copy(),
        ))
        self._redirect(previous, token, target, clone)
        original.link = clone
        return clone

    def _redirect(self, previous: int, token: str, target: int, clone: int) -> None:
        while previous >= 0 and self.states[previous].transitions.get(token) == target:
            self.states[previous].transitions[token] = clone
            previous = self.states[previous].link

    def _advance(self, state: int, length: int, token: str) -> tuple[int, int]:
        while state and token not in self.states[state].transitions:
            state = self.states[state].link
            length = self.states[state].length
        next_state = self.states[state].transitions.get(token)
        return (next_state, length + 1) if next_state is not None else (0, 0)

    def longest_match(self, sequence: list[str], start: int, end: int, b_start: int) -> Match:
        """Break ties by earliest start in a, then earliest start in b, like difflib."""
        best = Match(start, b_start, 0)
        state = length = 0
        for position in range(start, end):
            state, length = self._advance(state, length, sequence[position])
            if length > best.size:
                best = Match(position - length + 1, self.states[state].first_end - length + 1, length)
        return best


def _longest_match(a: list[str], b: list[str], bounds: tuple[int, int, int, int]) -> Match:
    a_start, a_end, b_start, b_end = bounds
    index = _SuffixAutomaton(b, b_start, b_end)
    return index.longest_match(a, a_start, a_end, b_start)


def ordered_ratio(a: list[str], b: list[str]) -> float:
    """Compute difflib's no-junk ratio without enumerating repeated-token pairs.

    Each partition uses a suffix automaton for the longest common substring.
    The partitioning and tie rules match SequenceMatcher(autojunk=False).
    This preserves its asymmetric score; it is not a longest-subsequence metric.
    """
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if max(len(a), len(b)) < 256:
        return SequenceMatcher(None, a, b, autojunk=False).ratio()
    return 2.0 * _matched_tokens(a, b) / (len(a) + len(b))


def _matched_tokens(a: list[str], b: list[str]) -> int:
    """Partition iteratively, so deeply fragmented matches cannot exhaust recursion."""
    pending = [(0, len(a), 0, len(b))]
    matched = 0
    while pending:
        bounds = pending.pop()
        match = _longest_match(a, b, bounds)
        if match.size:
            matched += match.size
            _queue_partitions(pending, bounds, match)
    return matched


def _queue_partitions(
    pending: list[tuple[int, int, int, int]], bounds: tuple[int, int, int, int], match: Match,
) -> None:
    a_start, a_end, b_start, b_end = bounds
    if a_start < match.a and b_start < match.b:
        pending.append((a_start, match.a, b_start, match.b))
    a_next, b_next = match.a + match.size, match.b + match.size
    if a_next < a_end and b_next < b_end:
        pending.append((a_next, a_end, b_next, b_end))
