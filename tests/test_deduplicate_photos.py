"""Tests for deduplicate_photos.py"""

from click.testing import CliRunner

from deduplicate_photos import (
    main,
    calculate_partial_hash,
    calculate_full_hash,
    find_duplicates,
    FileHash,
)
from rich.console import Console


class TestHashFunctions:
    """Test hashing functions."""

    def test_calculate_full_hash(self, tmp_path):
        """Test full file hashing."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file3 = tmp_path / "file3.txt"

        # Same content should have same hash
        file1.write_text("Hello, World!")
        file2.write_text("Hello, World!")
        file3.write_text("Different content")

        hash1 = calculate_full_hash(file1)
        hash2 = calculate_full_hash(file2)
        hash3 = calculate_full_hash(file3)

        assert hash1 == hash2
        assert hash1 != hash3

    def test_calculate_partial_hash(self, tmp_path):
        """Test partial file hashing."""
        # Create a large file
        large_file = tmp_path / "large.bin"
        content = b"A" * (2 * 1024 * 1024 + 100)  # >2MB
        large_file.write_bytes(content)

        partial_hash = calculate_partial_hash(large_file, len(content))

        # Should produce consistent hash
        assert partial_hash == calculate_partial_hash(large_file, len(content))

        # Different file should have different hash
        other_file = tmp_path / "other.bin"
        other_file.write_bytes(b"B" * (2 * 1024 * 1024 + 100))
        other_hash = calculate_partial_hash(other_file, len(content))

        assert partial_hash != other_hash

    def test_find_duplicates(self, tmp_path):
        """Test duplicate detection logic."""
        # Create test files
        file1 = tmp_path / "dup1.jpg"
        file2 = tmp_path / "dup2.jpg"
        file3 = tmp_path / "unique.jpg"

        content = b"duplicate content"
        file1.write_bytes(content)
        file2.write_bytes(content)
        file3.write_bytes(b"unique content")

        # Create FileHash objects
        file_hashes = [
            FileHash(
                path=file1,
                size=len(content),
                partial_hash=calculate_partial_hash(file1, len(content)),
                full_hash=calculate_full_hash(file1),
            ),
            FileHash(
                path=file2,
                size=len(content),
                partial_hash=calculate_partial_hash(file2, len(content)),
                full_hash=calculate_full_hash(file2),
            ),
            FileHash(
                path=file3,
                size=14,  # "unique content"
                partial_hash="unique",
                full_hash="unique_full",
            ),
        ]

        console = Console()
        duplicates = find_duplicates(file_hashes, console)

        assert len(duplicates) == 1
        assert len(duplicates[0].files) == 2
        assert duplicates[0].keep_file in [file1, file2]
        assert len(duplicates[0].duplicate_files) == 1


class TestCLI:
    """Test command-line interface."""

    def test_list_mode(self, tmp_path):
        """Test list mode without moving files."""
        runner = CliRunner()

        # Create duplicate files
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        content = b"duplicate photo data"
        (dir1 / "photo1.jpg").write_bytes(content)
        (dir2 / "photo2.jpg").write_bytes(content)
        (dir1 / "unique.jpg").write_bytes(b"unique photo")

        result = runner.invoke(main, ["list", str(dir1), str(dir2)])

        assert result.exit_code == 0
        assert "Found 1 groups of duplicate files" in result.output
        assert "Total duplicate files: 1" in result.output

        # Verify files weren't moved
        assert (dir1 / "photo1.jpg").exists()
        assert (dir2 / "photo2.jpg").exists()

    def test_run_mode(self, tmp_path):
        """Test run mode with actual file moving."""
        runner = CliRunner()

        # Create duplicate files
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        content = b"duplicate data"
        file1 = source_dir / "dup1.jpg"
        file2 = source_dir / "dup2.jpg"
        file1.write_bytes(content)
        file2.write_bytes(content)

        duplicates_dir = tmp_path / "duplicates"

        result = runner.invoke(
            main,
            ["run", str(source_dir), "--duplicates-directory", str(duplicates_dir)],
        )

        assert result.exit_code == 0
        assert "Successfully moved: 1" in result.output

        # Verify file was moved
        assert file1.exists()  # First file kept
        assert not file2.exists()  # Second file moved
        assert (duplicates_dir / "dup2.jpg").exists()

    def test_no_duplicates(self, tmp_path):
        """Test when no duplicates are found."""
        runner = CliRunner()

        dir1 = tmp_path / "dir1"
        dir1.mkdir()
        (dir1 / "unique1.jpg").write_bytes(b"content1")
        (dir1 / "unique2.jpg").write_bytes(b"content2")

        result = runner.invoke(main, ["list", str(dir1)])

        assert result.exit_code == 0
        assert "No duplicate files found!" in result.output

    def test_empty_files(self, tmp_path):
        """Test handling of empty files."""
        runner = CliRunner()

        dir1 = tmp_path / "dir1"
        dir1.mkdir()
        (dir1 / "empty1.txt").touch()
        (dir1 / "empty2.txt").touch()
        (dir1 / "nonempty.txt").write_text("content")

        result = runner.invoke(main, ["list", str(dir1)])

        assert result.exit_code == 0
        # Empty files should be skipped

    def test_large_files(self, tmp_path):
        """Test handling of large files with partial hashing."""
        runner = CliRunner()

        dir1 = tmp_path / "dir1"
        dir1.mkdir()

        # Create large duplicate files (>2MB)
        large_content = b"X" * (3 * 1024 * 1024)
        (dir1 / "large1.bin").write_bytes(large_content)
        (dir1 / "large2.bin").write_bytes(large_content)

        result = runner.invoke(main, ["list", str(dir1)])

        assert result.exit_code == 0
        assert "Found 1 groups of duplicate files" in result.output

    def test_custom_duplicates_directory(self, tmp_path):
        """Test custom duplicates directory option."""
        runner = CliRunner()

        source = tmp_path / "source"
        source.mkdir()
        custom_dup_dir = tmp_path / "my_duplicates"

        content = b"dup"
        (source / "file1.txt").write_bytes(content)
        (source / "file2.txt").write_bytes(content)

        result = runner.invoke(
            main, ["run", str(source), "--duplicates-directory", str(custom_dup_dir)]
        )

        assert result.exit_code == 0
        assert custom_dup_dir.exists()
        assert (custom_dup_dir / "file2.txt").exists()
