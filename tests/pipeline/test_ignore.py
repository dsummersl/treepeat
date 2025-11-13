"""Tests for ignore patterns and ignore files functionality."""

import tempfile
from pathlib import Path

import pytest

from tssim.config import PipelineSettings, set_settings
from tssim.pipeline.parse import (
    collect_source_files,
    find_ignore_files,
    matches_pattern,
    parse_ignore_file,
    should_ignore_file,
)


class TestParseIgnoreFile:
    """Tests for parsing ignore files."""

    def test_parse_simple_patterns(self):
        """Test parsing a simple ignore file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gitignore", delete=False) as f:
            f.write("*.pyc\n")
            f.write("__pycache__/\n")
            f.write("# This is a comment\n")
            f.write("\n")
            f.write("*.log\n")
            f.flush()

            patterns = parse_ignore_file(Path(f.name))
            assert patterns == ["*.pyc", "__pycache__/", "*.log"]

        Path(f.name).unlink()

    def test_parse_empty_file(self):
        """Test parsing an empty ignore file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gitignore", delete=False) as f:
            f.write("# Only comments\n")
            f.write("\n")
            f.flush()

            patterns = parse_ignore_file(Path(f.name))
            assert patterns == []

        Path(f.name).unlink()


class TestMatchesPattern:
    """Tests for pattern matching."""

    def test_simple_wildcard(self, tmp_path):
        """Test simple wildcard patterns."""
        file = tmp_path / "test.pyc"
        file.touch()

        assert matches_pattern(file, "*.pyc", tmp_path)
        assert not matches_pattern(file, "*.py", tmp_path)

    def test_directory_pattern(self, tmp_path):
        """Test directory-only patterns."""
        dir_path = tmp_path / "node_modules"
        dir_path.mkdir()

        # Directory patterns should only match directories
        assert matches_pattern(dir_path, "node_modules/", tmp_path)

        # Files should not match directory patterns
        file = tmp_path / "node_modules.txt"
        file.touch()
        assert not matches_pattern(file, "node_modules/", tmp_path)

    def test_double_star_pattern(self, tmp_path):
        """Test ** (recursive) patterns."""
        subdir = tmp_path / "src" / "utils"
        subdir.mkdir(parents=True)
        file = subdir / "test.py"
        file.touch()

        # Pattern like **/test.py should match files in any subdirectory
        assert matches_pattern(file, "**/test.py", tmp_path)
        assert matches_pattern(file, "**/*.py", tmp_path)

    def test_prefix_pattern(self, tmp_path):
        """Test patterns with directory prefix."""
        subdir = tmp_path / "build" / "output"
        subdir.mkdir(parents=True)
        file = subdir / "test.py"
        file.touch()

        # Pattern like build/** should match anything under build/
        assert matches_pattern(file, "build/**", tmp_path)

    def test_absolute_pattern(self, tmp_path):
        """Test patterns starting with /."""
        file = tmp_path / "test.py"
        file.touch()

        subdir = tmp_path / "src"
        subdir.mkdir()
        file2 = subdir / "test.py"
        file2.touch()

        # /test.py should only match files directly in base, not in subdirs
        assert matches_pattern(file, "/test.py", tmp_path)
        assert not matches_pattern(file2, "/test.py", tmp_path)


class TestShouldIgnoreFile:
    """Tests for should_ignore_file function."""

    def test_ignore_with_cli_pattern(self, tmp_path):
        """Test ignoring files using CLI patterns."""
        file = tmp_path / "test.pyc"
        file.touch()

        ignore_patterns = ["*.pyc"]
        ignore_files_map = {}

        assert should_ignore_file(file, tmp_path, ignore_patterns, ignore_files_map)

    def test_ignore_with_ignore_file(self, tmp_path):
        """Test ignoring files using ignore file patterns."""
        # Create a .gitignore file
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.log\n")

        # Create a log file
        log_file = tmp_path / "test.log"
        log_file.touch()

        ignore_patterns = []
        ignore_files_map = {tmp_path: ["*.log"]}

        assert should_ignore_file(log_file, tmp_path, ignore_patterns, ignore_files_map)

    def test_hierarchical_ignore(self, tmp_path):
        """Test hierarchical ignore patterns."""
        # Create directory structure
        subdir = tmp_path / "src" / "utils"
        subdir.mkdir(parents=True)

        # Create ignore file in subdirectory
        subdir_ignore = subdir / ".gitignore"
        subdir_ignore.write_text("*.test.py\n")

        # Create files
        file_in_subdir = subdir / "test.test.py"
        file_in_subdir.touch()

        file_in_parent = tmp_path / "test.test.py"
        file_in_parent.touch()

        ignore_patterns = []
        ignore_files_map = {subdir: ["*.test.py"]}

        # File in subdirectory should be ignored
        assert should_ignore_file(file_in_subdir, tmp_path, ignore_patterns, ignore_files_map)

        # File in parent should not be ignored
        assert not should_ignore_file(file_in_parent, tmp_path, ignore_patterns, ignore_files_map)


class TestFindIgnoreFiles:
    """Tests for finding ignore files."""

    def test_find_gitignore(self, tmp_path):
        """Test finding .gitignore files."""
        # Create .gitignore files in different directories
        gitignore1 = tmp_path / ".gitignore"
        gitignore1.write_text("*.pyc\n")

        subdir = tmp_path / "src"
        subdir.mkdir()
        gitignore2 = subdir / ".gitignore"
        gitignore2.write_text("*.log\n")

        ignore_files_map = find_ignore_files(tmp_path, ["**/.gitignore"])

        assert tmp_path in ignore_files_map
        assert "*.pyc" in ignore_files_map[tmp_path]

        assert subdir in ignore_files_map
        assert "*.log" in ignore_files_map[subdir]

    def test_find_any_ignore_file(self, tmp_path):
        """Test finding any ignore file with pattern **/.*ignore."""
        # Create various ignore files
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.pyc\n")

        dockerignore = tmp_path / ".dockerignore"
        dockerignore.write_text("*.log\n")

        ignore_files_map = find_ignore_files(tmp_path, ["**/.*ignore"])

        # Should find both .gitignore and .dockerignore
        assert tmp_path in ignore_files_map
        assert "*.pyc" in ignore_files_map[tmp_path]
        assert "*.log" in ignore_files_map[tmp_path]


class TestCollectSourceFilesWithIgnore:
    """Tests for collect_source_files with ignore patterns."""

    def test_collect_with_cli_ignore(self, tmp_path):
        """Test collecting files with CLI ignore patterns."""
        # Create Python files
        file1 = tmp_path / "main.py"
        file1.write_text("print('hello')")

        file2 = tmp_path / "test.py"
        file2.write_text("print('test')")

        # Configure settings to ignore test files
        settings = PipelineSettings(ignore_patterns=["test.py"])
        set_settings(settings)

        files = collect_source_files(tmp_path)

        assert file1 in files
        assert file2 not in files

    def test_collect_with_ignore_file(self, tmp_path):
        """Test collecting files with ignore file patterns."""
        # Create .gitignore
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.test.py\n")

        # Create Python files
        file1 = tmp_path / "main.py"
        file1.write_text("print('hello')")

        file2 = tmp_path / "example.test.py"
        file2.write_text("print('test')")

        # Configure settings to use ignore files
        settings = PipelineSettings(ignore_file_patterns=["**/.gitignore"])
        set_settings(settings)

        files = collect_source_files(tmp_path)

        assert file1 in files
        assert file2 not in files

    def test_collect_with_nested_ignore_files(self, tmp_path):
        """Test collecting files with nested ignore files."""
        # Create directory structure
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        # Create .gitignore in tests directory
        tests_gitignore = tests_dir / ".gitignore"
        tests_gitignore.write_text("*.py\n")

        # Create Python files
        src_file = src_dir / "main.py"
        src_file.write_text("print('main')")

        test_file = tests_dir / "test.py"
        test_file.write_text("print('test')")

        # Configure settings
        settings = PipelineSettings(ignore_file_patterns=["**/.gitignore"])
        set_settings(settings)

        files = collect_source_files(tmp_path)

        # src file should be collected, test file should be ignored
        assert src_file in files
        assert test_file not in files

    def test_collect_with_no_ignore(self, tmp_path):
        """Test collecting files with no ignore patterns."""
        # Create Python files
        file1 = tmp_path / "main.py"
        file1.write_text("print('hello')")

        file2 = tmp_path / "test.py"
        file2.write_text("print('test')")

        # Configure settings with no ignore patterns
        settings = PipelineSettings(ignore_patterns=[], ignore_file_patterns=[])
        set_settings(settings)

        files = collect_source_files(tmp_path)

        assert file1 in files
        assert file2 in files
