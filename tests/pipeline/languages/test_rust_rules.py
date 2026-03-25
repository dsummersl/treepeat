from treepeat.pipeline.languages.rust import RustConfig


def test_macro_names_mode_separation(rule_tester):
    config = RustConfig()
    source = 'fn f() { println!("hello"); }'
    # preserved in default mode
    rule_tester._verify_with_rules(
        config, config.get_default_rules(),
        "Anonymize macro names", source, "println", None, "Default Rules"
    )
    # removed in loose mode
    rule_tester._verify_with_rules(
        config, config.get_loose_rules(),
        "Anonymize macro names", source, None, "println", "Loose Rules"
    )


def test_rust_rules_detailed(rule_tester):
    config = RustConfig()
    rule_tester.verify_rules(
        config,
        [
            {
                "rule_name": "Ignore use declarations",
                "source": "use std::collections::HashMap;",
                "expected_symbol": None,
                "unexpected_symbol": "use_declaration",
            },
            {
                "rule_name": "Ignore extern crate declarations",
                "source": "extern crate serde;",
                "expected_symbol": None,
                "unexpected_symbol": "extern_crate_declaration",
            },
            {
                "rule_name": "Ignore line comments",
                "source": "// line comment\n/// doc comment",
                "expected_symbol": None,
                "unexpected_symbol": "line_comment",
            },
            {
                "rule_name": "Ignore block comments",
                "source": "/* block\n   comment */",
                "expected_symbol": None,
                "unexpected_symbol": "block_comment",
            },
            {
                "rule_name": "Anonymize macro names",
                "source": 'fn f() { println!("hello"); }',
                "expected_symbol": None,
                "unexpected_symbol": "println",
            },
            {
                "rule_name": "Anonymize macro names",
                "source": "fn f() { log::info!(\"msg\"); log::debug!(\"msg\"); }",
                "expected_symbol": None,
                "unexpected_symbol": "info",
            },
            {
                "rule_name": "Ignore attribute items",
                "source": "#[derive(Debug, Clone)]\nstruct Foo {}",
                "expected_symbol": None,
                "unexpected_symbol": "attribute_item",
            },
            {
                "rule_name": "Ignore attribute items",
                "source": "#![allow(dead_code)]\nfn f() {}",
                "expected_symbol": None,
                "unexpected_symbol": "inner_attribute_item",
            },
            {
                "rule_name": "Ignore generic lifetimes",
                "source": "fn f<'a>(x: &'a i32) {}",
                "expected_symbol": None,
                "unexpected_symbol": "lifetime",
            },
            {
                "rule_name": "Ignore generic lifetimes",
                "source": "fn f(x: &'static i32) {}",
                "expected_symbol": "static",
                "unexpected_symbol": None,
            },
            {
                "rule_name": "Anonymize function names",
                "source": "fn my_func(a: i32) -> i32 { a }",
                "expected_symbol": "FUNC",
                "unexpected_symbol": "my_func",
            },
            {
                "rule_name": "Anonymize type names",
                "source": "struct MyStruct { x: i32 }",
                "expected_symbol": "TYPE",
                "unexpected_symbol": "MyStruct",
            },
            {
                "rule_name": "Anonymize type names",
                "source": "enum MyEnum { Red, Blue }",
                "expected_symbol": "TYPE",
                "unexpected_symbol": "MyEnum",
            },
            {
                "rule_name": "Anonymize type names",
                "source": "trait MyTrait { fn speak(&self) -> String; }",
                "expected_symbol": "TYPE",
                "unexpected_symbol": "MyTrait",
            },
            {
                "rule_name": "Anonymize type names",
                "source": "type MyAlias = Vec<i32>;",
                "expected_symbol": "TYPE",
                "unexpected_symbol": "MyAlias",
            },
            {
                "rule_name": "Anonymize type names",
                "source": "union MyUnion { x: i32, y: f32 }",
                "expected_symbol": "TYPE",
                "unexpected_symbol": "MyUnion",
            },
            {
                "rule_name": "Anonymize identifiers",
                "source": "static MYVAR: i32 = 1;",
                "expected_symbol": "VAR_1",
                "unexpected_symbol": "MYVAR",
            },
            {
                "rule_name": "Ignore string content",
                "source": 'fn f() { let s = "hello world"; }',
                "expected_symbol": None,
                "unexpected_symbol": "hello",
            },
            {
                "rule_name": "Anonymize string literals",
                "source": 'fn f() { let s = "hello"; }',
                "expected_symbol": "<STR>",
                "unexpected_symbol": None,
            },
            {
                "rule_name": "Anonymize string literals",
                "source": "fn f() { let c = 'x'; }",
                "expected_symbol": "<STR>",
                "unexpected_symbol": "x",
            },
            {
                "rule_name": "Anonymize numeric literals",
                "source": "fn f() { let n = 42; let pi = 3.14; }",
                "expected_symbol": "<NUM>",
                "unexpected_symbol": "42",
            },
            {
                "rule_name": "Anonymize boolean literals",
                "source": "fn f() { let b = true; }",
                "expected_symbol": "<BOOL>",
                "unexpected_symbol": None,
            },
            {
                "rule_name": "Anonymize binary expressions",
                "source": "fn f(a: i32, b: i32) -> i32 { a + b }",
                "expected_symbol": "<BINOP>",
                "unexpected_symbol": "binary_expression",
            },
            {
                "rule_name": "Anonymize unary expressions",
                "source": "fn f() { let x = -1; }",
                "expected_symbol": "<UNOP>",
                "unexpected_symbol": "unary_expression",
            },
        ],
    )
