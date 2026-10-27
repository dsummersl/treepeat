from pathlib import Path

import pytest

from treepeat.config import PipelineSettings
from treepeat.models.shingle import CompactShingleList
from treepeat.pipeline.minhash_stage import create_minhash_signature
from treepeat.pipeline.parse import parse_file
from treepeat.pipeline.preprocessing import preprocess
from treepeat.pipeline.region_extraction import extract_all_regions
from treepeat.pipeline.rules_factory import build_rule_engine
from treepeat.pipeline.shingle import ASTShingler, shingle_regions

FIXTURES = Path(__file__).parent.parent / "fixtures"


SUFFIXES = {".py", ".js", ".ts", ".java", ".rs", ".kt", ".lua", ".php", ".yaml", ".yml", ".md", ".astro"}


def _fixture_files() -> list[Path]:
    return sorted(p for p in FIXTURES.rglob("*") if p.suffix in SUFFIXES)


def test_compact_matches_annotated_shingles():
    engine = build_rule_engine(PipelineSettings())
    parsed = []
    for path in _fixture_files():
        try:
            parsed.append(parse_file(path))
        except Exception:
            continue
    regions = extract_all_regions(parsed, engine)
    assert regions

    annotated = shingle_regions(regions, parsed, engine, k=3)
    compact = shingle_regions(regions, parsed, engine, k=3, symbols={})

    assert len(annotated) == len(compact)
    for a, c in zip(annotated, compact, strict=True):
        assert isinstance(c.shingles, CompactShingleList)
        assert a.shingles.get_contents() == c.shingles.get_contents()


def test_symbols_share_equal_strings():
    engine = build_rule_engine(PipelineSettings())
    parsed = [parse_file(FIXTURES / "python" / "dataclass1.py")]
    regions = extract_all_regions(parsed, engine)
    symbols: dict[str, str] = {}
    shingled = shingle_regions(regions, parsed, engine, k=3, symbols=symbols)
    contents = [s for sr in shingled for s in sr.shingles.get_contents()]
    assert len(symbols) < len(contents)
    assert all(symbols[s] is s for s in contents)


def test_minhash_batching_matches_single_updates():
    from datasketch import MinHash

    shingles = {f"shingle-{i}" for i in range(1000)}
    expected = MinHash(num_perm=128)
    for s in shingles:
        expected.update(s.encode("utf-8"))
    assert (create_minhash_signature(shingles, 128).hashvalues == expected.hashvalues).all()


def test_preprocess_streams_and_fingerprints():
    settings = PipelineSettings()
    engine = build_rule_engine(settings)
    out = preprocess(FIXTURES / "python", engine, settings)
    assert out.files_parsed > 0
    assert len(out.signatures) == len(out.shingled_regions) > 0
    assert out.counts["shingle"] == len(out.signatures)


def test_k_must_be_positive():
    with pytest.raises(ValueError):
        ASTShingler(build_rule_engine(PipelineSettings()), k=0, symbols={})
