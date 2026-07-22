"""Ruleset-aware signature verification behavior.

Two JavaScript functions with identical bodies but different names should be
reported as duplicates when the active ruleset anonymizes function names
(default/loose), and rejected when it does not (none) — because the function
name never enters the shingles, the signature check is the only differentiator.
"""

from pathlib import Path

import pytest

from treepeat.config import (
    LSHSettings,
    MinHashSettings,
    PipelineSettings,
    RulesSettings,
    ShingleSettings,
    set_settings,
)
from treepeat.pipeline.pipeline import run_pipeline

RENAMED_CLONE = Path(__file__).parent.parent / "fixtures" / "javascript" / "renamed_clone.js"


def _run_with_ruleset(ruleset: str, similarity_percent: float):
    set_settings(
        PipelineSettings(
            rules=RulesSettings(ruleset=ruleset),
            shingle=ShingleSettings(),
            minhash=MinHashSettings(),
            lsh=LSHSettings(similarity_percent=similarity_percent),
        )
    )
    return run_pipeline(str(RENAMED_CLONE))


@pytest.mark.parametrize("ruleset", ["default", "loose"])
def test_renamed_clone_matches_when_names_anonymized(ruleset):
    result = _run_with_ruleset(ruleset, similarity_percent=1.0)
    assert len(result.similar_groups) == 1
    assert result.similar_groups[0].similarity == pytest.approx(1.0)


def test_renamed_clone_penalized_when_names_not_anonymized():
    # Under 'none' the signature check fires: differing names -> not a match.
    result = _run_with_ruleset("none", similarity_percent=1.0)
    assert len(result.similar_groups) == 0
