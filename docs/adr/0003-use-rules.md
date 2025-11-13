# 3. Use Rules

Date: 2025-11-13

## Status

Accepted

## Context

The current architecture uses "normalizers"-Python classes that perform general text or AST normalization (e.g., IdentifierNormalizer, LiteralNormalizer, PythonImportNormalizer).

While functional, this model has several issues:

- Limited composability: Normalizers assume specific transformations rather than reusable, declarative rules.
- Language coupling: Logic for language-specific nodes and regions leaks into the normalization layer (LANGUAGE_REGION_MAPPINGS).
- Coarse granularity: The "one normalizer = one transformation" design doesn't align well with Tree-sitter's fine-grained node graph.

In practice, we need something closer to Exuberant Ctags or eslint rules - small, declarative, composable rules that describe what to do with which nodes, independent of specific implementations.

## Decision

We will replace "normalizers" with a Tree-sitter-specific rules engine that operates directly on node kinds.

Each rule will be a small, declarative unit applied to a syntax tree, defined either inline via CLI or loaded from a rules file.

CLI interface
- `--rules-file PATH` - load a text file containing rule definitions (one per line).
- `--rules RULE1,RULE2,...` - provide a comma-delimited list of rule specs directly.


## Consequences

What becomes easier or more difficult to do and any risks introduced by the change that will need to be mitigated.


We will replace "normalizers" with a **Tree-sitter-specific rules engine** that operates directly on node kinds.
Each rule will be a small, declarative unit applied to a syntax tree, defined either inline via CLI or loaded from a rules file.

### CLI interface

Only two switches will control rule behavior:

* `--rules-file PATH` - load a text file containing rule definitions (one per line).
* `--rules RULE1,RULE2,...` - provide a comma-delimited list of rule specs directly.

These override the built-in defaults; last one wins.

### Rule model

Rules are expressed in a simple, shell-safe DSL:

```
<lang|*> : <op> : nodes=<node1|node2|glob*> [,:k=v ...]
```

Examples:

```
python:skip:nodes=import_statement|import_from_statement|comment
python:replace_value:nodes=string|integer|float,value=<LIT>
*:anonymize_identifiers:nodes=identifier,scheme=flat,prefix=VAR
python:canonicalize_types:nodes=type_identifier|qualified_type,token=<TYPE>
```

Supported operations:

- **skip**: Exclude matching nodes entirely (e.g., imports, comments).
- **replace_name**: Replace node kinds/names with a constant token.
- **replace_value**: Replace literal values (strings, ints, floats) with a placeholder.
- **anonymize_identifiers**: Replace identifiers with stable non-unique names (e.g., `VAR_1`).
- **canonicalize_types**: Collapse type identifiers into a canonical `<TYPE>` token.


## Consequences

Benefits

* **Tree-sitter-native:** Operates directly on node graphs, language-agnostic but language-aware.
* **Composable:** Users combine small, declarative rules rather than extending classes.
* **Introspectable:** Rules can be printed (`--print-config`) and reasoned about as data.
* **Configurable:** Two simple CLI flags replace multiple `--enable/--disable` switches.
* **Extensible:** Easy to add new rule types without new command-line options.

Drawbacks

* Requires a parsing layer (`rules/parse.py`) to handle the DSL.
* May duplicate work if rules overlap; will rely on "last-wins" precedence.
* Slightly more opaque for users accustomed to explicit normalizer names.
