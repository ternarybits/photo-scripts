### Python Commands

- Run tests: `uv run pytest`
- Run single test: `uv run pytest tests/path/to/test_file.py::test_function_name`
- Run linting: `uv run ruff check --fix`
- Format code: `uv run ruff format`
- Type checking: `uv run pyright`

### Python Notes

- Version dependencies appropriately in pyproject.toml
- Use snake_case for all variables, functions, and SQLAlchemy model attributes
- Use modern type hints (Python 3.12+): `int | None` instead of `Optional[int]`
- Use uv for dependency management, not pip or poetry
- Imports should ALWAYS go at the top of files. The only time imports should ever be inline is if that's necessary to prevent circular dependencies.
- After making changes, check the relevant README.md files and update them with the latest information as necessary.
- When updating pull requests with additional commits, make sure to update the pull request description to include the latest changes.
