from treepeat.pipeline.rules.models import Rule, RuleAction

from .base import LanguageConfig, RegionExtractionRule

_DIAGRAM_NODES = (
    "diagram_flow",
    "diagram_sequence",
    "diagram_class",
    "diagram_state",
    "diagram_er",
    "diagram_gantt",
    "diagram_pie",
    "diagram_mindmap",
)

_IDENTIFIER_NODES = (
    "flow_vertex_id",
    "sequence_actor",
    "class_name_body",
    "state_name",
    "state_id",
    "er_entity_name",
    "er_attribute_name",
    "mmap_node_id",
)

_TEXT_NODES = (
    "flow_text_literal",
    "flow_text_quoted",
    "flow_arrow_text",
    "flow_vertex_text",
    "sequence_text",
    "note_content",
    "state_description",
    "er_role",
    "class_label",
    "gantt_task_text",
    "gantt_task_data",
    "gantt_title",
    "gantt_section",
    "pie_label",
    "pie_value",
    "pie_title",
    "mmap_text",
    "title",
)


def _alternation(nodes: tuple[str, ...], capture: str) -> str:
    return "[" + " ".join(f"({n})" for n in nodes) + f"] @{capture}"


class MermaidConfig(LanguageConfig):
    def get_default_rules(self) -> list[Rule]:
        return [
            Rule(
                name="Ignore comments",
                languages=["mermaid"],
                query="(comment) @comment",
                action=RuleAction.REMOVE,
            ),
        ]

    def get_loose_rules(self) -> list[Rule]:
        return [
            *self.get_default_rules(),
            Rule(
                name="Anonymize node, actor, class and entity names",
                languages=["mermaid"],
                query=_alternation(_IDENTIFIER_NODES, "id"),
                action=RuleAction.ANONYMIZE,
                params={"prefix": "ID"},
            ),
            Rule(
                name="Anonymize labels and text",
                languages=["mermaid"],
                query=_alternation(_TEXT_NODES, "text"),
                action=RuleAction.REPLACE_VALUE,
                params={"value": "<TEXT>"},
            ),
        ]

    def get_region_extraction_rules(self) -> list[RegionExtractionRule]:
        return [
            RegionExtractionRule(query=_alternation(_DIAGRAM_NODES, "region"), label="diagram"),
            RegionExtractionRule.from_node_type("flow_stmt_subgraph"),
            RegionExtractionRule.from_node_type("state_stmt_composite"),
        ]
