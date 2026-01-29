# Java and Kotlin Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add support for Java and Kotlin similarity detection in `treepeat`.

**Architecture:** Extend `LanguageConfig` for Java and Kotlin, define normalization rules (imports, comments, anonymization), and add region extraction rules.

**Tech Stack:** Python, Tree-sitter

---

### Task 1: Add Java Configuration

**Files:**
- Create: `treepeat/pipeline/languages/java.py`
- Modify: `treepeat/pipeline/languages/__init__.py`

**Step 1: Create `treepeat/pipeline/languages/java.py`**

```python
from treepeat.pipeline.rules.models import Rule, RuleAction
from .base import LanguageConfig, RegionExtractionRule

class JavaConfig(LanguageConfig):
    """Configuration for Java language."""

    def get_language_name(self) -> str:
        return "java"

    def get_default_rules(self) -> list[Rule]:
        return [
            Rule(
                name="Ignore import statements",
                languages=["java"],
                query="(import_declaration) @import",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Ignore comments",
                languages=["java"],
                query="[(line_comment) (block_comment)] @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize method names",
                languages=["java"],
                query="(method_declaration name: (identifier) @name)",
                action=RuleAction.ANONYMIZE,
                params={"prefix": "METHOD"},
            ),
            Rule(
                name="Anonymize class names",
                languages=["java"],
                query="(class_declaration name: (identifier) @name)",
                action=RuleAction.ANONYMIZE,
                params={"prefix": "CLASS"},
            ),
        ]

    def get_loose_rules(self) -> list[Rule]:
        return [
            *self.get_default_rules(),
            Rule(
                name="Anonymize identifiers",
                languages=["java"],
                query="(identifier) @id",
                action=RuleAction.ANONYMIZE,
                params={"prefix": "VAR"},
            ),
            Rule(
                name="Anonymize literals",
                languages=["java"],
                query="[(string_literal) (decimal_integer_literal) (decimal_floating_point_literal) (boolean_literal) (null_literal)] @lit",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<LIT>"},
            ),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            RegionExtractionRule.from_node_type("method_declaration"),
            RegionExtractionRule.from_node_type("class_declaration"),
        ]
```

**Step 2: Update `treepeat/pipeline/languages/__init__.py`**

Add `java` to `LANGUAGE_CONFIGS` and `LANGUAGE_EXTENSIONS`.

### Task 2: Add Kotlin Configuration

**Files:**
- Create: `treepeat/pipeline/languages/kotlin.py`
- Modify: `treepeat/pipeline/languages/__init__.py`

**Step 1: Create `treepeat/pipeline/languages/kotlin.py`**

```python
from treepeat.pipeline.rules.models import Rule, RuleAction
from .base import LanguageConfig, RegionExtractionRule

class KotlinConfig(LanguageConfig):
    """Configuration for Kotlin language."""

    def get_language_name(self) -> str:
        return "kotlin"

    def get_default_rules(self) -> list[Rule]:
        return [
            Rule(
                name="Ignore import statements",
                languages=["kotlin"],
                query="(import_directive) @import",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Ignore comments",
                languages=["kotlin"],
                query="[(line_comment) (multiline_comment)] @comment",
                action=RuleAction.REMOVE,
            ),
            Rule(
                name="Anonymize function names",
                languages=["kotlin"],
                query="(function_declaration identifier: (simple_identifier) @name)",
                action=RuleAction.ANONYMIZE,
                params={"prefix": "FUNC"},
            ),
            Rule(
                name="Anonymize class names",
                languages=["kotlin"],
                query="(class_declaration identifier: (simple_identifier) @name)",
                action=RuleAction.ANONYMIZE,
                params={"prefix": "CLASS"},
            ),
        ]

    def get_loose_rules(self) -> list[Rule]:
        return [
            *self.get_default_rules(),
            Rule(
                name="Anonymize identifiers",
                languages=["kotlin"],
                query="(simple_identifier) @id",
                action=RuleAction.ANONYMIZE,
                params={"prefix": "VAR"},
            ),
            Rule(
                name="Anonymize literals",
                languages=["kotlin"],
                query="[(string_literal) (integer_literal) (real_literal) (boolean_literal) (null_literal)] @lit",
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<LIT>"},
            ),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            RegionExtractionRule.from_node_type("function_declaration"),
            RegionExtractionRule.from_node_type("class_declaration"),
        ]
```

**Step 2: Update `treepeat/pipeline/languages/__init__.py`**

Add `kotlin` to `LANGUAGE_CONFIGS` and `LANGUAGE_EXTENSIONS`.

### Task 3: Add Fixtures and Tests

**Files:**
- Create: `tests/fixtures/java/comprehensive.java`
- Create: `tests/fixtures/kotlin/comprehensive.kt`
- Create: `tests/pipeline/languages/test_java.py`
- Create: `tests/pipeline/languages/test_kotlin.py`

**Step 1: Create `tests/fixtures/java/comprehensive.java`**

```java
package com.example;

import java.util.List;
import java.util.ArrayList;

/**
 * A comprehensive Java sample for testing similarity detection.
 */
public class Comprehensive {
    private String name;

    public Comprehensive(String name) {
        this.name = name;
    }

    // A method that will have a duplicate
    public int calculateSum(int a, int b) {
        int result = a + b;
        System.out.println("Calculating sum: " + result);
        return result;
    }

    public void greet() {
        System.out.println("Hello, " + name);
    }
}

class AnotherClass {
    // Duplicate of calculateSum in Comprehensive
    public int mySum(int x, int y) {
        int z = x + y;
        System.out.println("Calculating sum: " + z);
        return z;
    }
}
```

**Step 2: Create `tests/fixtures/kotlin/comprehensive.kt`**

```kotlin
package com.example

import java.util.*

/**
 * A comprehensive Kotlin sample for testing similarity detection.
 */
class Comprehensive(val name: String) {

    // A method that will have a duplicate
    fun calculateSum(a: Int, b: Int): Int {
        val result = a + b
        println("Calculating sum: $result")
        return result
    }

    fun greet() {
        println("Hello, $name")
    }
}

class AnotherClass {
    // Duplicate of calculateSum in Comprehensive
    fun mySum(x: Int, y: Int): Int {
        val z = x + y
        println("Calculating sum: $z")
        return z
    }
}
```

**Step 3: Create tests**

Create `tests/pipeline/languages/test_java.py` and `tests/pipeline/languages/test_kotlin.py` following the pattern of `test_python.py`.

### Task 4: E2E Verification

**Step 1: Run tests**

Run: `pytest tests/pipeline/languages/test_java.py tests/pipeline/languages/test_kotlin.py`

**Step 2: Verify with `treepeat detect`**

Run: `python3.11 -m treepeat.cli.cli detect --min-lines 3 tests/fixtures/java`
Expected: Should find the duplicate methods.

Run: `python3.11 -m treepeat.cli.cli detect --min-lines 3 tests/fixtures/kotlin`
Expected: Should find the duplicate methods.
