# 1. Python project

Date: 2025-09-05

## Status

Accepted

## Context

A new project is being started that will be implemented in Python.

## Decision

Use a standard layout for the project with the following details:
- Use [uv](https://docs.astral.sh/uv/) as the package manager.
- Use [pytest](https://docs.pytest.org/en/stable/) as the test framework (with coverage).
- Use [adr-tools](https://github.com/npryce/adr-tools) to document architectural decisions.

Use the following layout for the python project:

```plaintext
project-root/
├── covey/
├── tests/
└── docs/
```

## Consequences

What becomes easier or more difficult to do and any risks introduced by the change that will need to be mitigated.
