import pytest
from treepeat.pipeline.languages.python import PythonConfig


def test_python_rules_detailed(rule_tester):
    config = PythonConfig()
    rule_tester.verify_rules(
        config,
        [
            {
                "rule_name": "Ignore import statements",
                "source": "import os\nfrom sys import path",
                "expected_symbol": None,
                "unexpected_symbol": "import_statement",
            },
            {
                "rule_name": "Ignore TYPE_CHECKING blocks",
                "source": "if typing.TYPE_CHECKING:\n    import foo",
                "expected_symbol": None,
                "unexpected_symbol": "if_statement",
            },
            {
                "rule_name": "Ignore TypeVar declarations",
                "source": "T = typing.TypeVar('T')",
                "expected_symbol": None,
                "unexpected_symbol": "assignment",
            },
            {
                "rule_name": "Ignore comments",
                "source": "# A comment",
                "expected_symbol": None,
                "unexpected_symbol": "comment",
            },
            {
                "rule_name": "Ignore docstrings",
                "source": 'def f():\n    """Docstring"""\n    pass',
                "expected_symbol": None,
                "unexpected_symbol": "string",
            },
            {
                "rule_name": "Anonymize function names",
                "source": "def my_func(): pass",
                "expected_symbol": "FUNC",
                "unexpected_symbol": "my_func",
            },
            {
                "rule_name": "Anonymize class names",
                "source": "class MyClass: pass",
                "expected_symbol": "CLASS",
                "unexpected_symbol": "MyClass",
            },
            {
                "rule_name": "Ignore string content",
                "source": 'x = "hello world"',
                "expected_symbol": None,
                "unexpected_symbol": "hello",
            },
            {
                "rule_name": "Anonymize identifiers",
                "source": "x = 1",
                "expected_symbol": "VAR_1",
                "unexpected_symbol": "x",
            },
            {
                "rule_name": "Anonymize literals",
                "source": "x = 123 + 1.23 + True + False + None",
                "expected_symbol": "<LIT>",
                "unexpected_symbol": "123",
            },
            {
                "rule_name": "Anonymize operators",
                "source": "x = a + b",
                "expected_symbol": "<OP>",
                "unexpected_symbol": "binary_operator",
            },
            {
                "rule_name": "Anonymize types",
                "source": "def f(x: int) -> str: pass",
                "expected_symbol": "<T>",
                "unexpected_symbol": "type",
            },
            {
                "rule_name": "Anonymize collections",
                "source": "x = [1, 2, 3] + {'a': 1} + (1, 2)",
                "expected_symbol": "<COLL>",
                "unexpected_symbol": "list",
            },
        ],
    )
