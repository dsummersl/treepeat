.PHONY: help setup test lint type adr new coverage

help:
	@echo "Available targets:"
	@echo "  setup            - Set up development environment"
	@echo "  test             - Run tests with pytest"
	@echo "  lint             - Run linting checks"
	@echo "  fix              - Auto-fix linting issues"
	@echo "  type             - Run type checking with mypy"
	@echo "  radon            - Run radon complexity checks"
	@echo "  vulture          - Run vulture to find dead code"
	@echo "  ci               - Run all CI checks (lint, type, test, radon)"

setup:
	uv venv
	uv sync --python .venv/bin/python

test:
	uv run pytest

lint:
	uv run ruff check .

vulture:
  # vulture erroneously flags pydantic model_config settings as unused.
	uv run vulture --min-confidence 55 --ignore-names 'model_config' treepeat

fix:
	uv run ruff check . --fix

type:
	uv run mypy

radon:
	uv run .github/scripts/check_radon.sh

ci: lint type test radon vulture
