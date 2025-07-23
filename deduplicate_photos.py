#!/usr/bin/env python3
"""Script to find and move duplicate files based on content."""

import hashlib
import os
import shutil
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple

import click
from pydantic import BaseModel
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeRemainingColumn,
)
from rich.table import Table


class FileHash(BaseModel):
    """File hash information."""

    path: Path
    size: int
    partial_hash: str | None = None
    full_hash: str | None = None


class DuplicateGroup(BaseModel):
    """Group of duplicate files."""

    hash_value: str
    size: int
    files: List[Path]
    keep_file: Path
    duplicate_files: List[Path]


CHUNK_SIZE = 1024 * 1024  # 1MB chunks for partial hashing


def calculate_partial_hash(filepath: Path, size: int) -> str:
    """Calculate hash of first and last chunks of a file."""
    hasher = hashlib.sha256()

    with open(filepath, "rb") as f:
        # Hash first chunk
        hasher.update(f.read(CHUNK_SIZE))

        # Hash last chunk if file is large enough
        if size > CHUNK_SIZE * 2:
            f.seek(-CHUNK_SIZE, 2)  # Seek to last chunk
            hasher.update(f.read(CHUNK_SIZE))

    return hasher.hexdigest()


def calculate_full_hash(filepath: Path) -> str:
    """Calculate full SHA256 hash of a file."""
    hasher = hashlib.sha256()

    with open(filepath, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            hasher.update(chunk)

    return hasher.hexdigest()


def process_file(filepath: Path) -> FileHash | None:
    """Process a single file and return its hash information."""
    try:
        stat = filepath.stat()
        if stat.st_size == 0:
            return None

        file_hash = FileHash(path=filepath, size=stat.st_size)

        # Calculate partial hash for files larger than 2MB
        if stat.st_size > CHUNK_SIZE * 2:
            file_hash.partial_hash = calculate_partial_hash(filepath, stat.st_size)
        else:
            # For small files, full hash is the partial hash
            file_hash.full_hash = calculate_full_hash(filepath)
            file_hash.partial_hash = file_hash.full_hash

        return file_hash
    except (OSError, IOError):
        return None


def scan_directories(directories: List[Path], console: Console) -> List[FileHash]:
    """Scan directories and calculate file hashes in parallel."""
    all_files = []

    # First, collect all file paths
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Discovering files...", total=None)

        for directory in directories:
            for root, _, filenames in os.walk(directory):
                for filename in filenames:
                    filepath = Path(root) / filename
                    all_files.append(filepath)

        progress.update(task, completed=len(all_files))

    console.print(f"[green]Found {len(all_files):,} files to process[/green]\n")

    # Process files in parallel
    file_hashes = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Calculating file hashes...", total=len(all_files))

        with ProcessPoolExecutor() as executor:
            future_to_file = {executor.submit(process_file, f): f for f in all_files}

            for future in as_completed(future_to_file):
                result = future.result()
                if result:
                    file_hashes.append(result)
                progress.update(task, advance=1)

    return file_hashes


def find_duplicates(
    file_hashes: List[FileHash], console: Console
) -> List[DuplicateGroup]:
    """Find duplicate files using smart hashing."""
    # Group by size first
    size_groups: Dict[int, List[FileHash]] = defaultdict(list)
    for fh in file_hashes:
        size_groups[fh.size].append(fh)

    # Only process groups with multiple files
    potential_duplicates = {
        size: files for size, files in size_groups.items() if len(files) > 1
    }

    console.print(
        f"[yellow]Found {len(potential_duplicates):,} size groups with potential duplicates[/yellow]\n"
    )

    # Find actual duplicates
    duplicate_groups = []
    total_files = sum(len(files) for files in potential_duplicates.values())

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Finding duplicates...", total=total_files)

        for size, files in potential_duplicates.items():
            # Group by partial hash
            partial_hash_groups: Dict[str, List[FileHash]] = defaultdict(list)

            for fh in files:
                if fh.partial_hash:
                    partial_hash_groups[fh.partial_hash].append(fh)
                progress.update(task, advance=1)

            # For files with matching partial hashes, calculate full hash
            for partial_hash, matching_files in partial_hash_groups.items():
                if len(matching_files) > 1:
                    # Calculate full hashes for files that don't have them yet
                    full_hash_groups: Dict[str, List[Path]] = defaultdict(list)

                    for fh in matching_files:
                        if not fh.full_hash:
                            try:
                                fh.full_hash = calculate_full_hash(fh.path)
                            except (OSError, IOError):
                                continue

                        if fh.full_hash:
                            full_hash_groups[fh.full_hash].append(fh.path)

                    # Create duplicate groups
                    for full_hash, paths in full_hash_groups.items():
                        if len(paths) > 1:
                            group = DuplicateGroup(
                                hash_value=full_hash,
                                size=size,
                                files=paths,
                                keep_file=paths[0],  # Keep the first file
                                duplicate_files=paths[1:],  # Mark rest as duplicates
                            )
                            duplicate_groups.append(group)

    return duplicate_groups


def display_duplicates(groups: List[DuplicateGroup], console: Console) -> None:
    """Display found duplicates in a table."""
    table = Table(title="Duplicate Files Found", show_lines=True)
    table.add_column("Keep", style="green", no_wrap=False)
    table.add_column("Remove", style="red", no_wrap=False)
    table.add_column("Size", style="cyan")
    table.add_column("Hash", style="yellow", max_width=16)

    # Show first 10 groups
    for group in groups[:10]:
        size_mb = group.size / (1024 * 1024)
        duplicates_str = "\n".join(str(p) for p in group.duplicate_files[:3])
        if len(group.duplicate_files) > 3:
            duplicates_str += f"\n... and {len(group.duplicate_files) - 3} more"

        table.add_row(
            str(group.keep_file),
            duplicates_str,
            f"{size_mb:.2f} MB",
            group.hash_value[:16] + "...",
        )

    if len(groups) > 10:
        table.add_row(f"... and {len(groups) - 10} more groups ...", "", "", "")

    console.print(table)


def move_duplicates(
    groups: List[DuplicateGroup], duplicates_dir: Path, console: Console
) -> Tuple[int, int, int]:
    """Move duplicate files to the specified directory."""
    success_count = 0
    failure_count = 0
    bytes_saved = 0

    # Create duplicates directory if it doesn't exist
    duplicates_dir.mkdir(parents=True, exist_ok=True)

    total_files = sum(len(g.duplicate_files) for g in groups)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Moving duplicates...", total=total_files)

        for group in groups:
            for dup_file in group.duplicate_files:
                try:
                    # Keep the original filename and directory structure
                    dest_path = duplicates_dir / dup_file.name
                    
                    # If a file with the same name already exists, add a counter
                    counter = 1
                    while dest_path.exists():
                        stem = dup_file.stem
                        suffix = dup_file.suffix
                        dest_path = duplicates_dir / f"{stem}_{counter}{suffix}"
                        counter += 1
                    
                    # Move the file
                    shutil.move(str(dup_file), str(dest_path))
                    success_count += 1
                    bytes_saved += group.size
                except Exception as e:
                    console.print(f"[red]Failed to move {dup_file}: {e}[/red]")
                    failure_count += 1

                progress.update(task, advance=1)

    return success_count, failure_count, bytes_saved


def print_summary(
    mode: str,
    groups: List[DuplicateGroup],
    execution_time: float,
    console: Console,
    success_count: int = 0,
    failure_count: int = 0,
    bytes_saved: int = 0,
) -> None:
    """Print a summary of the operation."""
    total_duplicates = sum(len(g.duplicate_files) for g in groups)
    total_bytes = sum(g.size * len(g.duplicate_files) for g in groups)

    console.print("\n[bold blue]Summary:[/bold blue]")
    console.print(f"Mode: [cyan]{mode}[/cyan]")
    console.print(f"Execution time: [green]{execution_time:.2f}s[/green]")
    console.print(f"Duplicate groups found: [yellow]{len(groups):,}[/yellow]")
    console.print(f"Total duplicate files: [yellow]{total_duplicates:,}[/yellow]")
    console.print(
        f"Space that can be saved: [green]{total_bytes / (1024**3):.2f} GB[/green]"
    )

    if mode == "run":
        console.print(f"Successfully moved: [green]{success_count:,}[/green]")
        if failure_count > 0:
            console.print(f"Failed to move: [red]{failure_count:,}[/red]")
        console.print(
            f"Space actually saved: [green]{bytes_saved / (1024**3):.2f} GB[/green]"
        )


@click.command()
@click.argument("mode", type=click.Choice(["list", "run"]))
@click.argument(
    "directories",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
)
@click.option(
    "--duplicates-directory",
    type=click.Path(path_type=Path),
    default=Path("duplicates"),
    help="Directory to move duplicate files to (default: ./duplicates)",
)
def main(mode: str, directories: Tuple[Path, ...], duplicates_directory: Path) -> None:
    """Find and move duplicate files based on content.

    MODE: Either 'list' to preview duplicates or 'run' to move them.
    DIRECTORIES: One or more directories to scan for duplicate files.
    """
    console = Console()
    start_time = time.time()

    if len(directories) < 1:
        console.print("[red]Error: At least one directory must be specified[/red]")
        raise click.Abort()

    console.print(
        f"[bold]Scanning {len(directories)} directories for duplicate files...[/bold]\n"
    )

    # Scan directories and calculate hashes
    file_hashes = scan_directories(list(directories), console)

    if not file_hashes:
        console.print("[green]No files found to process![/green]")
        return

    # Find duplicates
    duplicate_groups = find_duplicates(file_hashes, console)

    if not duplicate_groups:
        console.print("[green]No duplicate files found![/green]")
        return

    # Display duplicates
    console.print(
        f"\n[bold]Found {len(duplicate_groups):,} groups of duplicate files[/bold]\n"
    )
    display_duplicates(duplicate_groups, console)

    # Execute if in run mode
    success_count = 0
    failure_count = 0
    bytes_saved = 0

    if mode == "run":
        console.print(f"\n[bold]Moving duplicates to: {duplicates_directory}[/bold]\n")
        success_count, failure_count, bytes_saved = move_duplicates(
            duplicate_groups, duplicates_directory, console
        )

    # Print summary
    execution_time = time.time() - start_time
    print_summary(
        mode,
        duplicate_groups,
        execution_time,
        console,
        success_count,
        failure_count,
        bytes_saved,
    )


if __name__ == "__main__":
    main()
