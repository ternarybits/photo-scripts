#!/usr/bin/env python3
"""Script to rename files with duplicate names across multiple directories."""

import os
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


class FileInfo(BaseModel):
    """Information about a file."""

    path: Path
    name: str
    size: int


class RenameOperation(BaseModel):
    """A single rename operation."""

    old_path: Path
    new_path: Path
    reason: str


def scan_directory(directory: Path) -> List[FileInfo]:
    """Scan a directory recursively and return file information."""
    files = []
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            filepath = Path(root) / filename
            try:
                stat = filepath.stat()
                files.append(FileInfo(path=filepath, name=filename, size=stat.st_size))
            except (OSError, IOError):
                # Skip files we can't access
                pass
    return files


def find_duplicate_names(
    directories: List[Path], console: Console
) -> Dict[str, List[Path]]:
    """Find all files with duplicate names across directories."""
    name_to_paths: Dict[str, List[Path]] = defaultdict(list)
    total_files = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        # Scan directories in parallel
        scan_task = progress.add_task("Scanning directories...", total=len(directories))

        with ProcessPoolExecutor() as executor:
            future_to_dir = {executor.submit(scan_directory, d): d for d in directories}

            for future in as_completed(future_to_dir):
                dir_path = future_to_dir[future]
                try:
                    files = future.result()
                    for file_info in files:
                        name_to_paths[file_info.name].append(file_info.path)
                        total_files += 1
                    progress.update(scan_task, advance=1)
                except Exception as e:
                    console.print(f"[red]Error scanning {dir_path}: {e}[/red]")

    # Filter to only duplicate names
    duplicates = {
        name: paths for name, paths in name_to_paths.items() if len(paths) > 1
    }

    console.print(f"\n[green]Scanned {total_files:,} files[/green]")
    console.print(
        f"[yellow]Found {len(duplicates):,} filenames with duplicates[/yellow]"
    )

    return duplicates


def generate_unique_name(base_path: Path, index: int) -> Path:
    """Generate a unique filename by adding a suffix."""
    stem = base_path.stem
    suffix = base_path.suffix
    parent = base_path.parent

    new_name = f"{stem}-{index}{suffix}"
    return parent / new_name


def plan_renames(duplicates: Dict[str, List[Path]]) -> List[RenameOperation]:
    """Plan rename operations for all duplicate files."""
    operations = []

    for filename, paths in duplicates.items():
        # Sort paths for consistent ordering
        sorted_paths = sorted(paths)

        # Keep the first file as-is, rename the rest
        for index, path in enumerate(sorted_paths[1:], start=1):
            new_path = generate_unique_name(path, index)

            # Ensure the new name doesn't already exist
            while new_path.exists():
                index += 1
                new_path = generate_unique_name(path, index)

            operations.append(
                RenameOperation(
                    old_path=path,
                    new_path=new_path,
                    reason=f"Duplicate of '{filename}'",
                )
            )

    return operations


def display_operations(operations: List[RenameOperation], console: Console) -> None:
    """Display planned rename operations in a table."""
    table = Table(title="Planned Rename Operations", show_lines=True)
    table.add_column("Original Path", style="cyan", no_wrap=False)
    table.add_column("New Path", style="green", no_wrap=False)
    table.add_column("Reason", style="yellow")

    # Show first 20 operations
    for op in operations[:20]:
        table.add_row(str(op.old_path), str(op.new_path), op.reason)

    if len(operations) > 20:
        table.add_row(f"... and {len(operations) - 20} more ...", "", "")

    console.print(table)


def execute_renames(
    operations: List[RenameOperation], console: Console
) -> Tuple[int, int]:
    """Execute rename operations and return success/failure counts."""
    success_count = 0
    failure_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Renaming files...", total=len(operations))

        for op in operations:
            try:
                op.old_path.rename(op.new_path)
                success_count += 1
            except Exception as e:
                console.print(f"[red]Failed to rename {op.old_path}: {e}[/red]")
                failure_count += 1

            progress.update(task, advance=1)

    return success_count, failure_count


def print_summary(
    mode: str,
    operations: List[RenameOperation],
    execution_time: float,
    console: Console,
    success_count: int = 0,
    failure_count: int = 0,
) -> None:
    """Print a summary of the operation."""
    console.print("\n[bold blue]Summary:[/bold blue]")
    console.print(f"Mode: [cyan]{mode}[/cyan]")
    console.print(f"Execution time: [green]{execution_time:.2f}s[/green]")
    console.print(f"Total files to rename: [yellow]{len(operations):,}[/yellow]")

    if mode == "run":
        console.print(f"Successfully renamed: [green]{success_count:,}[/green]")
        if failure_count > 0:
            console.print(f"Failed to rename: [red]{failure_count:,}[/red]")

    # Calculate duplicate groups
    groups = defaultdict(list)
    for op in operations:
        groups[op.reason].append(op)
    console.print(f"Duplicate filename groups: [cyan]{len(groups):,}[/cyan]")


@click.command()
@click.argument("mode", type=click.Choice(["list", "run"]))
@click.argument(
    "directories",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
)
def main(mode: str, directories: Tuple[Path, ...]) -> None:
    """Rename files with duplicate names across directories.

    MODE: Either 'list' to preview changes or 'run' to apply them.
    DIRECTORIES: One or more directories to scan for duplicate filenames.
    """
    console = Console()
    start_time = time.time()

    if len(directories) < 1:
        console.print("[red]Error: At least one directory must be specified[/red]")
        raise click.Abort()

    console.print(
        f"[bold]Scanning {len(directories)} directories for duplicate filenames...[/bold]\n"
    )

    # Find duplicates
    duplicates = find_duplicate_names(list(directories), console)

    if not duplicates:
        console.print("[green]No duplicate filenames found![/green]")
        return

    # Plan renames
    operations = plan_renames(duplicates)

    # Display operations
    console.print(f"\n[bold]Found {len(operations):,} files to rename[/bold]\n")
    display_operations(operations, console)

    # Execute if in run mode
    success_count = 0
    failure_count = 0

    if mode == "run":
        console.print("\n[bold]Executing rename operations...[/bold]\n")
        success_count, failure_count = execute_renames(operations, console)

    # Print summary
    execution_time = time.time() - start_time
    print_summary(
        mode, operations, execution_time, console, success_count, failure_count
    )


if __name__ == "__main__":
    main()
