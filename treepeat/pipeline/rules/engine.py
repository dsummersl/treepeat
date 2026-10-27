from collections import defaultdict
from typing import Any, Callable, DefaultDict, Iterable, Optional

from tree_sitter import Node, Query, QueryCursor
from tree_sitter_language_pack import get_language

from ..languages import LANGUAGE_CONFIGS, get_grammar
from .models import Rule, RuleAction, SkipNodeException


def _extract_node_text(node: Node, source: bytes) -> str:

    return source[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")


class RuleEngine:


    def __init__(self, rules: list[Rule]):

        self.rules = rules
        self._identifier_counters: dict[str, int] = {}
        self._identifier_mapping: dict[str, str] = {}
        self._action_handlers = self._build_action_handlers()
        self._compiled_queries: dict[tuple[str, str], Query] = {}
        self._query_matches_cache: dict[int, list[dict[str, Any]]] = {}


        self._rules_by_language: dict[str, list[Rule]] = {}
        for rule in rules:
            for lang in set(rule.languages):
                self._rules_by_language.setdefault(lang, []).append(rule)
        self._source: bytes | None = None

    def _build_action_handlers(
        self,
    ) -> dict[
        RuleAction,
        Callable[
            [Rule, Node, str, str, Optional[str], Optional[str]],
            tuple[Optional[str], Optional[str]],
        ],
    ]:

        return {
            RuleAction.REMOVE: self._handle_remove,
            RuleAction.REPLACE_NODE_TYPE: self._handle_replace_node_type,
            RuleAction.REPLACE_VALUE: self._handle_replace_value,
            RuleAction.ANONYMIZE: self._handle_anonymize,
        }

    def _get_anonymized_identifier(self, prefix: str, original_value: str) -> str:


        key = f"{prefix}:{original_value}"
        if key not in self._identifier_mapping:

            if prefix not in self._identifier_counters:
                self._identifier_counters[prefix] = 0
            self._identifier_counters[prefix] += 1
            self._identifier_mapping[key] = f"{prefix}_{self._identifier_counters[prefix]}"
        return self._identifier_mapping[key]

    def _get_compiled_query(self, language: str, query_str: str) -> Query:

        key = (language, query_str)
        if key not in self._compiled_queries:
            grammar = get_grammar(language)
            lang = get_language(grammar)  # type: ignore[arg-type]
            self._compiled_queries[key] = Query(lang, query_str)
        return self._compiled_queries[key]

    def _index_query_captures(
        self,
        all_matches: dict[int, list[dict[str, Any]]],
        query_str: str,
        match_id: int,
        captures_dict: dict[str, list[Node]],
        rule: Rule,
    ) -> None:

        for capture_name, nodes in captures_dict.items():


            if rule.target and capture_name != rule.target:
                continue

            for node in nodes:


                all_matches[node.id].append(
                    {
                        "query": query_str,
                        "match_id": match_id,
                        "captures": captures_dict,
                        "capture_name": capture_name,
                        "rule": rule,
                    }
                )

    def _get_all_matches(
        self, root_node: Node, rules: list[Rule], language: str
    ) -> dict[int, list[dict[str, Any]]]:

        all_matches: DefaultDict[int, list[dict[str, Any]]] = defaultdict(list)


        for rule in rules:
            query_str = rule.query
            query = self._get_compiled_query(language, query_str)
            cursor = QueryCursor(query)

            for match_id, captures_dict in cursor.matches(root_node):
                self._index_query_captures(all_matches, query_str, match_id, captures_dict, rule)

        return dict(all_matches)

    def _get_query_match_result(self, match_info: dict[str, Any]) -> str:

        rule = match_info["rule"]
        return str(rule.target) or match_info["capture_name"]

    def _check_node_matches_query(
        self, node: Node, rule: Rule, language: str, root_node: Node
    ) -> Optional[str]:


        if node.id in self._query_matches_cache:

            for match_info in self._query_matches_cache[node.id]:
                if match_info["query"] == rule.query:
                    return self._get_query_match_result(match_info)

        return None

    def _handle_remove(
        self,
        rule: Rule,
        node: Node,
        node_type: str,
        language: str,
        name: Optional[str],
        value: Optional[str],
    ) -> tuple[Optional[str], Optional[str]]:

        raise SkipNodeException(
            f"Node type '{node_type}' matched remove rule for language '{language}'"
        )

    def _handle_replace_node_type(
        self,
        rule: Rule,
        node: Node,
        node_type: str,
        language: str,
        name: Optional[str],
        value: Optional[str],
    ) -> tuple[Optional[str], Optional[str]]:

        return rule.params.get("token", "<NODE>"), value

    def _handle_replace_value(
        self,
        rule: Rule,
        node: Node,
        node_type: str,
        language: str,
        name: Optional[str],
        value: Optional[str],
    ) -> tuple[Optional[str], Optional[str]]:

        return name, rule.params.get("value", "<LIT>")

    def _handle_anonymize(
        self,
        rule: Rule,
        node: Node,
        node_type: str,
        language: str,
        name: Optional[str],
        value: Optional[str],
    ) -> tuple[Optional[str], Optional[str]]:

        prefix = rule.params.get("prefix", "VAR")

        if self._source is not None:
            original_value = _extract_node_text(node, self._source)
        else:
            original_value = value or "unknown"
        return name, self._get_anonymized_identifier(prefix, original_value)

    def _apply_action(
        self,
        rule: Rule,
        node: Node,
        node_type: str,
        language: str,
        name: Optional[str],
        value: Optional[str],
    ) -> tuple[Optional[str], Optional[str]]:

        if not rule.action:
            return name, value

        handler = self._action_handlers.get(rule.action)
        if handler:
            return handler(rule, node, node_type, language, name, value)

        return name, value

    def _apply_matching_rule(
        self,
        rule: Rule,
        node: Node,
        node_type: str,
        language: str,
        root_node: Node,
        name: Optional[str],
        value: Optional[str],
    ) -> tuple[Optional[str], Optional[str]]:

        capture_name = self._check_node_matches_query(node, rule, language, root_node)
        if capture_name:
            return self._apply_action(rule, node, node_type, language, name, value)
        return name, value

    def _iter_matching_rules(self, language: str) -> Iterable[Rule]:



        wildcard_rules = self._rules_by_language.get("*", [])
        if not wildcard_rules:
            yield from self._rules_by_language.get(language, [])
            return
        seen: set[int] = set()
        for rule in wildcard_rules:
            seen.add(id(rule))
            yield rule
        for rule in self._rules_by_language.get(language, []):
            if id(rule) not in seen:
                yield rule

    def _apply_rule_state(
        self,
        rule: Rule,
        node: Node,
        node_type: str,
        language: str,
        root_node: Node,
        name: Optional[str],
        value: Optional[str],
    ) -> tuple[Optional[str], Optional[str]]:
        res_name, res_value = self._apply_matching_rule(
            rule, node, node_type, language, root_node, name, value
        )
        return (
            res_name if res_name is not None else name,
            res_value if res_value is not None else value,
        )

    def apply_rules(
        self,
        node: Node,
        language: str,
        node_name: Optional[str] = None,
        root_node: Optional[Node] = None,
    ) -> tuple[Optional[str], Optional[str]]:

        node_type = node_name or node.type
        name = None
        value = None
        root_node = root_node or node



        if node.id not in self._query_matches_cache:
            return None, None



        for rule in self._iter_matching_rules(language):
            name, value = self._apply_rule_state(
                rule, node, node_type, language, root_node, name, value
            )

        return name, value

    def reset_identifiers(self) -> None:

        self._identifier_counters.clear()
        self._identifier_mapping.clear()
        self._query_matches_cache.clear()

    def release_source(self) -> None:

        self._source = None

    def precompute_queries(
        self, root_node: Node, language: str, source: bytes | None = None
    ) -> None:


        self._source = source


        self._query_matches_cache = self._get_all_matches(
            root_node, list(self._iter_matching_rules(language)), language
        )

    def get_region_extraction_rules(self, language: str) -> list[tuple[str, str]]:

        region_rules = []
        for rule in self._iter_matching_rules(language):
            if rule.action == RuleAction.EXTRACT_REGION:
                region_type = rule.params.get("region_type")
                if region_type:
                    region_rules.append((rule.query, region_type))
        return region_rules

    def get_region_extraction_rule_objects(self, language: str) -> list[Rule]:

        return [
            rule
            for rule in self.rules
            if rule.action == RuleAction.EXTRACT_REGION and rule.matches_language(language)
        ]

    def get_nodes_matching_query(
        self, root_node: Node, query_str: str, language: str
    ) -> list[Node]:

        query = self._get_compiled_query(language, query_str)
        cursor = QueryCursor(query)
        matching_nodes = []

        for _match_id, captures_dict in cursor.matches(root_node):

            for _capture_name, nodes in captures_dict.items():
                matching_nodes.extend(nodes)

        return matching_nodes


def build_region_extraction_rules() -> list[tuple[Rule, str]]:

    rules = []
    for lang_name, lang_config in LANGUAGE_CONFIGS.items():
        for region_rule in lang_config.get_region_extraction_rules():
            rule = Rule(
                name=f"Extract {region_rule.label} regions for {lang_name}",
                languages=[lang_name],
                query=region_rule.query,
                action=RuleAction.EXTRACT_REGION,
                params={"region_type": region_rule.label},
                injection_language=region_rule.target_language,
                injection_content_query=region_rule.content_query,
            )
            rules.append((rule, rule.name))
    return rules


def build_default_rules() -> list[tuple[Rule, str]]:

    rules = []
    rules.extend(build_region_extraction_rules())

    for _lang_name, lang_config in LANGUAGE_CONFIGS.items():
        for rule in lang_config.get_default_rules():
            rules.append((rule, rule.name))

    return rules


def build_loose_rules() -> list[tuple[Rule, str]]:

    rules = []
    rules.extend(build_region_extraction_rules())

    for _lang_name, lang_config in LANGUAGE_CONFIGS.items():

        for rule in lang_config.get_loose_rules():
            rules.append((rule, rule.name))

    return rules
