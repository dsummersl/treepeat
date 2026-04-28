"""Tests for display functions with special characters in file paths."""

import importlib
import io
from pathlib import Path

from rich.console import Console

from treepeat.models.similarity import Region, SimilarRegionGroup

detect_module = importlib.import_module("treepeat.cli.commands.detect")


def _make_region(path_str: str, start_line: int = 1, end_line: int = 10) -> Region:
    return Region(
        path=Path(path_str),
        language="typescript",
        region_type="function",
        region_name="handler",
        start_line=start_line,
        end_line=end_line,
    )


def _capture_display_group(group: SimilarRegionGroup, monkeypatch) -> str:
    buf = io.StringIO()
    test_console = Console(file=buf, markup=True, highlight=False, width=200)
    monkeypatch.setattr(detect_module, "console", test_console)
    detect_module._display_group(group)
    return buf.getvalue()


class TestDisplayGroupSpecialCharPaths:
    def test_bracket_path_id_segment_displayed_correctly(self, monkeypatch):
        """Path with [id] segment must not be swallowed by Rich markup parsing."""
        path = "packages/web/src/pages/api/collections/[id]/people/handler.ts"
        region1 = _make_region(path)
        region2 = _make_region("other/path/handler.ts")
        group = SimilarRegionGroup(regions=[region1, region2], similarity=0.9)

        output = _capture_display_group(group, monkeypatch)

        assert "[id]" in output
        assert "packages/web/src/pages/api/collections/[id]/people/handler.ts" in output

    def test_bracket_path_multiple_segments_displayed_correctly(self, monkeypatch):
        """Path with multiple bracket segments must render all of them."""
        path = "src/pages/[locale]/blog/[slug]/index.ts"
        region1 = _make_region(path)
        region2 = _make_region("other/handler.ts")
        group = SimilarRegionGroup(regions=[region1, region2], similarity=0.85)

        output = _capture_display_group(group, monkeypatch)

        assert "[locale]" in output
        assert "[slug]" in output
        assert "src/pages/[locale]/blog/[slug]/index.ts" in output

    def test_plain_path_still_displayed(self, monkeypatch):
        """Paths without special characters continue to display correctly."""
        path = "packages/web/src/handlers/api.ts"
        region1 = _make_region(path)
        region2 = _make_region("other/handler.ts")
        group = SimilarRegionGroup(regions=[region1, region2], similarity=0.9)

        output = _capture_display_group(group, monkeypatch)

        assert path in output
