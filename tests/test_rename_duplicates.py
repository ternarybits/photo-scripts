"""Tests for rename_duplicates.py"""

from pathlib import Path
from click.testing import CliRunner

from rename_duplicates import (
    main,
    find_duplicate_names,
    plan_renames,
    generate_unique_name,
)
from rich.console import Console


class TestRenameUtils:
    """Test utility functions."""

    def test_generate_unique_name(self):
        """Test unique name generation."""
        path = Path("/tmp/photo.jpg")
        assert generate_unique_name(path, 1) == Path("/tmp/photo-1.jpg")
        assert generate_unique_name(path, 2) == Path("/tmp/photo-2.jpg")

        # Test with different extensions
        path = Path("/tmp/document.pdf")
        assert generate_unique_name(path, 1) == Path("/tmp/document-1.pdf")

        # Test with no extension
        path = Path("/tmp/README")
        assert generate_unique_name(path, 1) == Path("/tmp/README-1")

    def test_find_duplicate_names(self, tmp_path):
        """Test finding duplicate filenames."""
        # Create test directory structure
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        # Create files with duplicate names
        (dir1 / "photo.jpg").write_text("content1")
        (dir2 / "photo.jpg").write_text("content2")
        (dir1 / "unique.txt").write_text("unique")

        console = Console()
        duplicates = find_duplicate_names([dir1, dir2], console)

        assert "photo.jpg" in duplicates
        assert len(duplicates["photo.jpg"]) == 2
        assert "unique.txt" not in duplicates

    def test_plan_renames(self, tmp_path):
        """Test rename planning."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        file1 = dir1 / "photo.jpg"
        file2 = dir2 / "photo.jpg"
        file1.write_text("1")
        file2.write_text("2")

        duplicates = {"photo.jpg": [file1, file2]}
        operations = plan_renames(duplicates)

        assert len(operations) == 1
        assert operations[0].old_path == file2
        assert operations[0].new_path.name == "photo-1.jpg"


class TestCLI:
    """Test command-line interface."""

    def test_list_mode(self, tmp_path):
        """Test list mode without making changes."""
        runner = CliRunner()

        # Create test files
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        (dir1 / "duplicate.jpg").write_text("1")
        (dir2 / "duplicate.jpg").write_text("2")

        result = runner.invoke(main, ["list", str(dir1), str(dir2)])

        assert result.exit_code == 0
        assert "duplicate.jpg" in result.output
        assert "Found 1 files to rename" in result.output

        # Verify files weren't renamed
        assert (dir1 / "duplicate.jpg").exists()
        assert (dir2 / "duplicate.jpg").exists()

    def test_run_mode(self, tmp_path):
        """Test run mode with actual renaming."""
        runner = CliRunner()

        # Create test files
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        file1 = dir1 / "duplicate.jpg"
        file2 = dir2 / "duplicate.jpg"
        file1.write_text("1")
        file2.write_text("2")

        result = runner.invoke(main, ["run", str(dir1), str(dir2)])

        assert result.exit_code == 0
        assert "Successfully renamed: 1" in result.output

        # Verify renaming
        assert file1.exists()  # First file kept as-is
        assert not file2.exists()  # Second file renamed
        assert (dir2 / "duplicate-1.jpg").exists()

    def test_no_duplicates(self, tmp_path):
        """Test when no duplicates are found."""
        runner = CliRunner()

        dir1 = tmp_path / "dir1"
        dir1.mkdir()
        (dir1 / "unique1.jpg").write_text("1")
        (dir1 / "unique2.jpg").write_text("2")

        result = runner.invoke(main, ["list", str(dir1)])

        assert result.exit_code == 0
        assert "No duplicate filenames found!" in result.output

    def test_missing_directory(self):
        """Test with non-existent directory."""
        runner = CliRunner()
        result = runner.invoke(main, ["list", "/nonexistent"])

        assert result.exit_code != 0

    def test_subdirectories(self, tmp_path):
        """Test scanning subdirectories."""
        runner = CliRunner()

        # Create nested structure
        dir1 = tmp_path / "dir1"
        subdir = dir1 / "subdir"
        dir2 = tmp_path / "dir2"

        dir1.mkdir()
        subdir.mkdir()
        dir2.mkdir()

        (subdir / "photo.jpg").write_text("1")
        (dir2 / "photo.jpg").write_text("2")

        result = runner.invoke(main, ["list", str(dir1), str(dir2)])

        assert result.exit_code == 0
        assert "photo.jpg" in result.output
        assert "Found 1 files to rename" in result.output
