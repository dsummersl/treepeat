import json
import random
import weakref
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pytest
from click.testing import CliRunner
from datasketch import MinHash

from treepeat.cli.cli import main
from treepeat.config import LSHSettings, PipelineSettings, RulesSettings, get_settings, set_settings
from treepeat.models.shingle import CompactShingleList, ShingledRegion
from treepeat.models.similarity import Region, ScanIssue, SimilarityResult, SimilarRegionGroup
from treepeat.pipeline import preprocessing
from treepeat.pipeline.bounded_verification import BoundedVerifier
from treepeat.pipeline.lsh_stage import detect_similarity
from treepeat.pipeline.minhash_stage import compute_region_signatures, create_minhash_signature
from treepeat.pipeline.parse import detect_language, parse_file
from treepeat.pipeline.pipeline import run_pipeline
from treepeat.pipeline.region_extraction import extract_all_regions
from treepeat.pipeline.rules_factory import build_rule_engine
from treepeat.pipeline.shingle import shingle_regions
from treepeat.pipeline.verification import _compute_ordered_similarity, verify_similar_groups

FIXTURES = Path(__file__).parent.parent / "fixtures"
SOURCES = [p for p in sorted(FIXTURES.rglob("*")) if p.is_file() and detect_language(p)]


@pytest.fixture(autouse=True)
def restore_settings():
    previous = get_settings()
    set_settings(PipelineSettings())
    yield
    set_settings(previous)


@pytest.mark.parametrize("ruleset", ["none", "default", "loose"])
@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(FIXTURES)))
def test_compact_sequences_match_original_for_every_fixture(path, ruleset):
    parsed = parse_file(path)
    engine = build_rule_engine(PipelineSettings(rules=RulesSettings(ruleset=ruleset)))
    regions = extract_all_regions([parsed], engine)
    original = shingle_regions(regions, [parsed], engine)
    symbols = {}
    compact = shingle_regions(regions, [parsed], engine, symbols=symbols)
    assert [r.region for r in compact] == [r.region for r in original]
    for before, after in zip(original, compact, strict=True):
        assert after.shingles.get_contents() == before.shingles.get_contents()
        assert all(token is symbols[token] for token in after.shingles.get_contents())


def test_streaming_releases_previous_parsed_file_and_query_captures(tmp_path, monkeypatch):
    for index in range(8):
        (tmp_path / f"{index}.php").write_text("<?php\nfunction f() { return 1; }\n")
    references = []
    original_parse = preprocessing.parse_file

    def checked_parse(path):
        assert all(reference() is None for reference in references)
        parsed = original_parse(path)
        references.append(weakref.ref(parsed))
        return parsed

    monkeypatch.setattr(preprocessing, "parse_file", checked_parse)
    settings = PipelineSettings(lsh=LSHSettings(min_lines=1))
    engine = build_rule_engine(settings)
    data = preprocessing.preprocess(tmp_path, engine, settings)
    assert data.counts["parse"] == 8
    assert len(data.signatures) == 8
    assert engine._source is None
    assert not engine._query_matches_cache
    assert all(reference() is None for reference in references)


@pytest.mark.parametrize("count", [0, 1, 256, 257, 1100])
def test_batched_minhash_is_bit_identical(count):
    contents = {f"node→identifier(value_{i})" for i in range(count)}
    expected = MinHash(num_perm=128)
    for token in contents:
        expected.update(token.encode("utf-8"))
    actual = create_minhash_signature(contents)
    np.testing.assert_array_equal(actual.hashvalues, expected.hashvalues)


def test_optimized_verifier_preserves_difflib_scores():
    randomizer = random.Random(123)
    for _ in range(100):
        a = [str(randomizer.randrange(6)) for _ in range(randomizer.randrange(1, 300))]
        b = a[:]
        for _ in range(15):
            b[randomizer.randrange(len(b))] = str(randomizer.randrange(6))
        expected = SequenceMatcher(None, a, b, autojunk=False).ratio()
        assert _compute_ordered_similarity(a, b) == expected
    assert _compute_ordered_similarity([], []) == 0.0


def _shingled(name, tokens):
    return ShingledRegion(
        region=Region(
            path=Path(f"{name}.php"), language="php", region_type="method", region_name=name,
            start_line=1, end_line=20,
        ),
        shingles=CompactShingleList.from_contents(tokens),
    )


def test_identical_sequences_skip_the_matcher_but_keep_signature_checks(monkeypatch):
    from treepeat.pipeline import sequence_matching, verification

    def unexpected_matcher(*args, **kwargs):
        raise AssertionError("Identical sequences must not invoke SequenceMatcher")

    monkeypatch.setattr(sequence_matching, "SequenceMatcher", unexpected_matcher)
    monkeypatch.setattr(sequence_matching, "_longest_match", unexpected_matcher)
    assert _compute_ordered_similarity(["repeated"] * 100000, ["repeated"] * 100000) == 1.0
    monkeypatch.setattr(verification, "_check_signature_match", lambda *args: False)
    regions = [_shingled("first", ["a"]), _shingled("second", ["a"])]
    group = SimilarRegionGroup(regions=[r.region for r in regions], similarity=1.0)
    assert verify_similar_groups([group], regions, rules=[])[0].similarity == 0.0


def test_timeout_is_reported_and_worker_can_restart():
    long = [_shingled("a", ["a", "b"] * 250000), _shingled("b", ["b", "a"] * 250000)]
    group = SimilarRegionGroup(regions=[r.region for r in long], similarity=1.0)
    worker = BoundedVerifier(0.01, [])
    try:
        with pytest.raises(TimeoutError):
            worker.verify(group, long)
        assert worker.process is None
        worker.timeout = 5
        short = [_shingled("a", ["a"]), _shingled("b", ["a"])]
        assert worker.verify(group, short) == 1.0
    finally:
        worker.close()
    assert worker.process is None


def test_timeout_preserves_other_verified_groups():
    long = [_shingled("a", ["a", "b"] * 250000), _shingled("b", ["b", "a"] * 250000)]
    short = [_shingled("c", ["a"]), _shingled("d", ["a"])]
    groups = [SimilarRegionGroup(regions=[r.region for r in pair], similarity=1.0) for pair in [long, short]]
    issues = []
    verified = verify_similar_groups(groups, long + short, [], timeout=0.1, issues=issues)
    assert len(verified) == 1
    assert verified[0].regions == groups[1].regions
    assert issues[0].code == "verification-timeout"
    assert issues[0].regions == groups[0].regions


def test_candidate_cap_marks_unresolved_instead_of_returning_a_clean_scan():
    shingles = [_shingled(str(i), ["a", "b", "c"]) for i in range(6)]
    signatures = compute_region_signatures(shingles)
    result = detect_similarity(signatures, 0.9, shingles, max_group_pairs=10)
    assert not result.complete
    assert not result.similar_groups
    assert result.issues[0].code == "candidate-limit"
    assert len(result.issues[0].regions) == 6


def test_failed_file_is_retained_as_a_diagnostic(tmp_path):
    missing = tmp_path / "missing.php"
    result = run_pipeline(missing)
    assert not result.complete
    assert result.issues[0].path == missing


def test_cli_writes_partial_sarif_before_exiting_two(tmp_path, monkeypatch):
    from importlib import import_module

    command = import_module("treepeat.cli.commands.detect")

    result = SimilarityResult(issues=[ScanIssue(code="verification-timeout", message="Budget exceeded")])
    monkeypatch.setattr(command, "_run_pipeline_with_ui", lambda *args, **kwargs: result)
    output = tmp_path / "report.sarif"
    invocation = CliRunner().invoke(main, ["detect", str(tmp_path), "--format", "sarif", "-o", str(output), "--fail"])
    assert invocation.exit_code == 2, invocation.output
    report = json.loads(output.read_text())["runs"][0]
    assert report["invocations"][0]["executionSuccessful"] is False
    assert report["properties"]["issues"][0]["code"] == "verification-timeout"


def test_empty_scan_is_a_successful_empty_report(tmp_path):
    invocation = CliRunner().invoke(main, ["detect", str(tmp_path), "--format", "sarif"])
    assert invocation.exit_code == 0, invocation.output
    assert json.loads(invocation.stdout)["runs"][0]["results"] == []
