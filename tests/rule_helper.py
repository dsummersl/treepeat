import re
from pathlib import Path

from treepeat.models.similarity import Region
from treepeat.pipeline.parse import parse_source_code
from treepeat.pipeline.region_extraction import ExtractedRegion
from treepeat.pipeline.rules.engine import RuleEngine
from treepeat.pipeline.shingle import ASTShingler


class RuleTester:
    def _get_language_name(self, config) -> str:

        class_name = config.__class__.__name__

        return class_name.replace("Config", "").lower()

    def verify_rule(self, config, rule_name, source, expected_symbol, unexpected_symbol=None):

        loose_rules = config.get_loose_rules()
        lang_name = self._get_language_name(config)

        rule = next((r for r in loose_rules if r.name == rule_name and r.matches_language(lang_name)), None)

        if not rule:
            rule = next((r for r in loose_rules if r.name == rule_name), None)

        if not rule:
            raise ValueError(f"Rule '{rule_name}' not found in {config.__class__.__name__}")

        self._verify_with_rules(config, [rule], rule_name, source, expected_symbol, unexpected_symbol, "Single Rule")

        self._verify_with_rules(config, loose_rules, rule_name, source, expected_symbol, unexpected_symbol, "All Rules")

    def _verify_with_rules(self, config, rules, rule_name, source, expected_symbol, unexpected_symbol, context):

        engine = RuleEngine(rules)

        lang_name = self._get_language_name(config)
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
                    f"[{context}] Expected symbol '{symbol}' not found in tokens for rule "
                    f"'{rule_name}'.\nTokens: {tokens}"
                )
            if not should_exist and match:
                raise AssertionError(
                    f"[{context}] Unexpected symbol '{symbol}' found in tokens for rule "
                    f"'{rule_name}'.\nTokens: {tokens}"
                )

        check_symbol(expected_symbol, token_str, True)
        check_symbol(unexpected_symbol, token_str, False)

    def verify_rules(self, config, test_cases):

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

        all_rules = config.get_loose_rules()
        defined_rule_names = {r.name for r in all_rules}

        missing = defined_rule_names - tested_rule_names
        if missing:
            raise AssertionError(f"Missing test cases for rules: {missing}")
