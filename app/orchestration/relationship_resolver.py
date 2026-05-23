from __future__ import annotations

import logging

from app.company.models import CollaborationEdge, RoutingRule
from app.orchestration.models import DiscussionPhase, DiscussionPlan

logger = logging.getLogger(__name__)

RELATION_WEIGHTS: dict[str, float] = {
    "escalates_to": 1.0,
    "delegates_to": 0.8,
    "collaborates_with": 0.5,
}


class RelationshipResolver:
    def __init__(self, edges: list[CollaborationEdge], rules: list[RoutingRule]) -> None:
        self._edges = edges
        self._rules = rules
        self._edge_index: dict[tuple[str, str], CollaborationEdge] = {}
        for edge in edges:
            self._edge_index[(edge.from_employee, edge.to_employee)] = edge
            if (edge.to_employee, edge.from_employee) not in self._edge_index:
                self._edge_index[(edge.to_employee, edge.from_employee)] = edge

    def get_collaboration_weight(self, from_id: str, to_id: str) -> float:
        edge = self._edge_index.get((from_id, to_id))
        if edge is None:
            return 0.0
        return RELATION_WEIGHTS.get(edge.relation_type, 0.0)

    def rank_participants(self, lead_id: str, participant_ids: list[str]) -> list[str]:
        def sort_key(pid: str) -> tuple[float, int]:
            weight = self.get_collaboration_weight(lead_id, pid)
            original_index = participant_ids.index(pid)
            return (-weight, original_index)

        return sorted(participant_ids, key=sort_key)

    def validate_phase_plan(self, plan: DiscussionPlan) -> list[str]:
        warnings: list[str] = []
        for phase in plan.phases:
            for p in phase.participants:
                weight = self.get_collaboration_weight(phase.lead_id, p.employee_id)
                if weight == 0.0:
                    warnings.append(
                        f"Phase '{phase.phase_id}': no relationship edge between lead "
                        f"'{phase.lead_id}' and participant '{p.employee_id}'"
                    )
        return warnings

    def get_relationship_context(self, speaker_id: str, phase: DiscussionPhase) -> str:
        parts: list[str] = []
        lead_edge = self._edge_index.get((speaker_id, phase.lead_id))
        if lead_edge is None:
            lead_edge = self._edge_index.get((phase.lead_id, speaker_id))
        if lead_edge:
            parts.append(
                f"你与主持人 {phase.lead_id} 的关系: {lead_edge.relation_type}"
                f"（{lead_edge.description}）" if lead_edge.description else
                f"你与主持人 {phase.lead_id} 的关系: {lead_edge.relation_type}"
            )
        for p in phase.participants:
            if p.employee_id == speaker_id:
                continue
            peer_edge = self._edge_index.get((speaker_id, p.employee_id))
            if peer_edge:
                parts.append(f"你与 {p.employee_id} 的关系: {peer_edge.relation_type}")
        if not parts:
            return ""
        return "=== 组织关系上下文 ===\n" + "\n".join(parts)
