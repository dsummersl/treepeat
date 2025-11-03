.PHONY: help setup test lint type adr new coverage

setup:
	uv venv
	uv sync --python .venv/bin/python

test:
	uv run pytest

lint:
	uv run ruff check .

fix:
	uv run ruff check . --fix

type:
	uv run mypy

radon:
	uv run .github/scripts/check_radon.sh

ci: lint type test radon
