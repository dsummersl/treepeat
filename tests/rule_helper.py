import re
from pathlib import Path
from treepeat.pipeline.rules.engine import RuleEngine
from treepeat.pipeline.parse import parse_source_code
from treepeat.pipeline.shingle import ASTShingler
from treepeat.pipeline.region_extraction import ExtractedRegion
from treepeat.models.similarity import Region


class RuleTester:
    """Helper for testing language rules."""

    def verify_rule(self, config, rule_name, source, expected_symbol, unexpected_symbol=None):
        """Verify a single rule's effect on source code."""
        # 1. Find the rule
        loose_rules = config.get_loose_rules()
        lang_name = config.get_language_name()

        # Try to find rule matching both name AND language
        rule = next(
            (r for r in loose_rules if r.name == rule_name and r.matches_language(lang_name)), None
        )

        # Fallback: find by name only (legacy/loose behavior)
        if not rule:
            rule = next((r for r in loose_rules if r.name == rule_name), None)

        if not rule:
            raise ValueError(f"Rule '{rule_name}' not found in {config.__class__.__name__}")

        # 2. Test with ONLY this rule
        self._verify_with_rules(
            config, [rule], rule_name, source, expected_symbol, unexpected_symbol, "Single Rule"
        )

        # 3. Test with ALL rules from the config
        # We use get_loose_rules as it contains everything
        self._verify_with_rules(
            config, loose_rules, rule_name, source, expected_symbol, unexpected_symbol, "All Rules"
        )

    def _verify_with_rules(
        self, config, rules, rule_name, source, expected_symbol, unexpected_symbol, context
    ):
        """Helper to run verification with a specific set of rules."""
        engine = RuleEngine(rules)

        lang_name = config.get_language_name()
        source_bytes = source.encode("utf-8")
        parsed = parse_source_code(source_bytes, lang_name, Path("test_file"))

        region = Region(
            path=Path("test_file"),
            language=lang_name,
            region_type="test",
            region_name="test",
            start_line=1,
            end_line=source.count("\n") + 1,
        )
        extracted_region = ExtractedRegion(region=region, node=parsed.root_node)

        shingler = ASTShingler(rule_engine=engine, k=1)
        engine.reset_identifiers()
        engine.precompute_queries(extracted_region.node, lang_name, source_bytes)
        shingled = shingler.shingle_region(extracted_region, source_bytes)

        tokens = shingled.shingles.get_contents()
        token_str = " ".join(tokens)

        def check_symbol(symbol, string, should_exist):
            if symbol is None:
                return

            pattern = rf"(?<!\w){re.escape(symbol)}(?!\w)"
            match = re.search(pattern, string)

            if should_exist and not match:
                raise AssertionError(
                    f"[{context}] Expected symbol '{symbol}' not found in tokens for rule '{rule_name}'.\nTokens: {tokens}"
                )
            if not should_exist and match:
                raise AssertionError(
                    f"[{context}] Unexpected symbol '{symbol}' found in tokens for rule '{rule_name}'.\nTokens: {tokens}"
                )

        check_symbol(expected_symbol, token_str, True)
        check_symbol(unexpected_symbol, token_str, False)

    def verify_rules(self, config, test_cases):
        """Verify multiple rules and check for full coverage."""
        tested_rule_names = set()
        for case in test_cases:
            self.verify_rule(
                config,
                case["rule_name"],
                case["source"],
                case.get("expected_symbol"),
                case.get("unexpected_symbol"),
            )
            tested_rule_names.add(case["rule_name"])

        # Coverage check: ensure all rules in loose_rules (which includes default) are tested
        all_rules = config.get_loose_rules()
        defined_rule_names = {r.name for r in all_rules}

        missing = defined_rule_names - tested_rule_names
        if missing:
            raise AssertionError(f"Missing test cases for rules: {missing}")
