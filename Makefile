.PHONY: help setup test lint type adr new coverage

help:
	@echo "Available targets:"
	@echo "  setup            - Set up development environment"
	@echo "  test             - Run tests with pytest"
	@echo "  lint             - Run linting checks"
	@echo "  fix              - Auto-fix linting issues"
	@echo "  type             - Run type checking with mypy"
	@echo "  radon            - Run radon complexity checks"
	@echo "  ci               - Run all CI checks (lint, type, test, radon)"

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
