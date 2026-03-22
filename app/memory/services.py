from __future__ import annotations

from uuid import uuid4

from app.company.bootstrap import get_company_profile, get_departments, get_employees
from app.company.models import WorkTicket
from app.control_plane.models import Checkpoint, RunTrace, TaskGraph
from app.executive_office.models import CEOCommand, CommandClassificationResult, InteractionMode
from app.memory.models import (
    MemoryKind,
    MemoryNamespace,
    MemoryRecord,
    MemoryScope,
    MemoryWriteRequest,
    RecallQuery,
)
from app.store import ModelStore, build_model_store


class MemoryService:
    def __init__(
        self,
        namespace_store: ModelStore[MemoryNamespace],
        record_store: ModelStore[MemoryRecord],
    ) -> None:
        self._namespaces = namespace_store
        self._records = record_store
        self._bootstrap_namespaces()

    def list_namespaces(self) -> list[MemoryNamespace]:
        return self._namespaces.list()

    def list_records(self) -> list[MemoryRecord]:
        return self._records.list()

    def list_records_for_ticket(self, ticket_id: str) -> list[MemoryRecord]:
        return [record for record in self._records.list() if record.work_ticket_ref == ticket_id]

    def write(self, request: MemoryWriteRequest) -> MemoryRecord:
        namespace = self.get_namespace(request.namespace_id)
        memory = MemoryRecord(
            memory_id=f"mem-{uuid4().hex[:8]}",
            namespace_id=namespace.namespace_id,
            scope=namespace.scope,
            scope_id=namespace.owner,
            owner_id=request.owner_id,
            kind=request.kind,
            visibility=self._default_visibility(namespace.scope, namespace.owner),
            content=request.content,
            tags=request.tags,
            confidence=request.confidence,
            promotion_state=request.promotion_state,
            checkpoint_ref=request.checkpoint_ref,
            artifact_refs=request.artifact_refs,
            retention=request.retention,
            source_trace=request.source_trace,
            work_ticket_ref=request.work_ticket_ref,
            thread_ref=request.thread_ref,
        )
        return self._records.save(memory)

    def recall(self, query: RecallQuery) -> list[MemoryRecord]:
        records = self._records.list()
        results: list[MemoryRecord] = []
        for record in records:
            if record.superseded_by is not None:
                continue
            if query.scope_filter and record.scope not in query.scope_filter:
                continue
            if query.kind_filter and record.kind not in query.kind_filter:
                continue
            if query.tags and not set(query.tags).issubset(set(record.tags)):
                continue
            if query.department and query.department not in record.tags and query.department != record.scope_id:
                continue
            if query.project and query.project not in record.tags:
                continue
            if record.confidence < query.min_confidence:
                continue
            if not self._is_read_allowed(record, query):
                continue
            results.append(record)
        return results

    def mark_superseded(self, memory_ids: list[str], decision_id: str) -> list[MemoryRecord]:
        updated: list[MemoryRecord] = []
        for memory_id in memory_ids:
            record = self._records.get(memory_id)
            if record is None:
                continue
            updated_record = self._records.save(record.model_copy(update={"superseded_by": decision_id}))
            updated.append(updated_record)
        return updated

    def create_intake_memories(
        self,
        command: CEOCommand,
        classification: CommandClassificationResult,
        work_ticket: WorkTicket,
        run_trace: RunTrace,
        checkpoint: Checkpoint | None,
        task_graph: TaskGraph | None,
    ) -> list[MemoryRecord]:
        mode = classification.interaction_mode
        records: list[MemoryRecord] = []

        if mode == InteractionMode.IDEA_CAPTURE:
            records.append(
                self.write(
                    MemoryWriteRequest(
                        namespace_id="company:default",
                        owner_id="ceo",
                        kind=MemoryKind.SEMANTIC,
                        content=f"CEO intent captured: {command.intent}",
                        tags=["ceo_intent", "idea_capture"],
                        checkpoint_ref=checkpoint.checkpoint_id if checkpoint else None,
                        source_trace=run_trace.runtrace_id,
                        work_ticket_ref=work_ticket.ticket_id,
                        thread_ref=work_ticket.thread_ref,
                    )
                )
            )
            return records

        if mode == InteractionMode.QUICK_CONSULT:
            primary_department = classification.recommended_departments[0]
            employee_id = self._employee_for_department(primary_department)
            records.append(
                self.write(
                    MemoryWriteRequest(
                        namespace_id=f"employee:{employee_id}",
                        owner_id=employee_id,
                        kind=MemoryKind.EPISODIC,
                        content=f"Quick consult summary for {primary_department}: {command.intent}",
                        tags=["quick_consult", primary_department],
                        source_trace=run_trace.runtrace_id,
                        work_ticket_ref=work_ticket.ticket_id,
                        thread_ref=work_ticket.thread_ref,
                    )
                )
            )
            records.append(
                self.write(
                    MemoryWriteRequest(
                        namespace_id="company:default",
                        owner_id="chief-of-staff",
                        kind=MemoryKind.EPISODIC,
                        content=f"Sync-back from quick consult: {command.intent}",
                        tags=["quick_consult", "sync_back", primary_department],
                        source_trace=run_trace.runtrace_id,
                        work_ticket_ref=work_ticket.ticket_id,
                        thread_ref=work_ticket.thread_ref,
                    )
                )
            )
            return records

        if mode == InteractionMode.DEPARTMENT_TASK:
            primary_department = classification.recommended_departments[0]
            records.append(
                self.write(
                    MemoryWriteRequest(
                        namespace_id=self._department_namespace(primary_department),
                        owner_id="chief-of-staff",
                        kind=MemoryKind.SEMANTIC,
                        content=f"Department task summary for {primary_department}: {command.intent}",
                        tags=["department_task", primary_department],
                        checkpoint_ref=checkpoint.checkpoint_id if checkpoint else None,
                        source_trace=run_trace.runtrace_id,
                        work_ticket_ref=work_ticket.ticket_id,
                        thread_ref=work_ticket.thread_ref,
                    )
                )
            )
            records.append(
                self.write(
                    MemoryWriteRequest(
                        namespace_id="company:default",
                        owner_id="chief-of-staff",
                        kind=MemoryKind.EPISODIC,
                        content=f"Company sync-back summary from {primary_department}: {command.intent}",
                        tags=["department_task", "sync_back", primary_department],
                        checkpoint_ref=checkpoint.checkpoint_id if checkpoint else None,
                        source_trace=run_trace.runtrace_id,
                        work_ticket_ref=work_ticket.ticket_id,
                        thread_ref=work_ticket.thread_ref,
                    )
                )
            )
            return records

        if mode == InteractionMode.FORMAL_PROJECT:
            records.extend(
                [
                    self.write(
                        MemoryWriteRequest(
                            namespace_id="employee:chief-of-staff",
                            owner_id="chief-of-staff",
                            kind=MemoryKind.EPISODIC,
                            content=f"Formal project intake routed: {command.intent}",
                            tags=["formal_project", "executive_office"],
                            checkpoint_ref=checkpoint.checkpoint_id if checkpoint else None,
                            source_trace=run_trace.runtrace_id,
                            work_ticket_ref=work_ticket.ticket_id,
                            thread_ref=work_ticket.thread_ref,
                        )
                    ),
                    self.write(
                        MemoryWriteRequest(
                            namespace_id="department:executive-office",
                            owner_id="chief-of-staff",
                            kind=MemoryKind.SEMANTIC,
                            content=f"Executive Office project summary: {command.intent}",
                            tags=["formal_project", "Executive Office"],
                            checkpoint_ref=checkpoint.checkpoint_id if checkpoint else None,
                            source_trace=run_trace.runtrace_id,
                            work_ticket_ref=work_ticket.ticket_id,
                            thread_ref=work_ticket.thread_ref,
                        )
                    ),
                    self.write(
                        MemoryWriteRequest(
                            namespace_id="company:default",
                            owner_id="chief-of-staff",
                            kind=MemoryKind.SEMANTIC,
                            content=f"Company project summary: {command.intent}",
                            tags=["formal_project", "company_summary"],
                            checkpoint_ref=checkpoint.checkpoint_id if checkpoint else None,
                            source_trace=run_trace.runtrace_id,
                            work_ticket_ref=work_ticket.ticket_id,
                            thread_ref=work_ticket.thread_ref,
                        )
                    ),
                ]
            )
            if task_graph is not None:
                records.append(
                    self.write(
                        MemoryWriteRequest(
                            namespace_id="company:default",
                            owner_id="chief-of-staff",
                            kind=MemoryKind.EPISODIC,
                            content=f"TaskGraph created with {len(task_graph.nodes)} nodes for {command.intent}",
                            tags=["formal_project", "task_graph"],
                            checkpoint_ref=checkpoint.checkpoint_id if checkpoint else None,
                            source_trace=run_trace.runtrace_id,
                            work_ticket_ref=work_ticket.ticket_id,
                            thread_ref=work_ticket.thread_ref,
                        )
                    )
                )
            return records

        if mode == InteractionMode.ESCALATION:
            records.append(
                self.write(
                    MemoryWriteRequest(
                        namespace_id="company:default",
                        owner_id="chief-of-staff",
                        kind=MemoryKind.EPISODIC,
                        content=f"Escalation intake summary: {command.intent}",
                        tags=["escalation"],
                        checkpoint_ref=checkpoint.checkpoint_id if checkpoint else None,
                        source_trace=run_trace.runtrace_id,
                        work_ticket_ref=work_ticket.ticket_id,
                        thread_ref=work_ticket.thread_ref,
                    )
                )
            )
        return records

    def create_quality_memories(
        self,
        work_ticket: WorkTicket,
        run_trace: RunTrace,
        checkpoint: Checkpoint | None,
        verdict: str,
        summary: str,
        artifact_refs: list[str],
    ) -> list[MemoryRecord]:
        return [
            self.write(
                MemoryWriteRequest(
                    namespace_id="department:quality",
                    owner_id="quality-lead",
                    kind=MemoryKind.EVIDENCE,
                    content=f"Quality {verdict.upper()} summary: {summary}",
                    tags=["quality", verdict],
                    checkpoint_ref=checkpoint.checkpoint_id if checkpoint else None,
                    artifact_refs=artifact_refs,
                    source_trace=run_trace.runtrace_id,
                    work_ticket_ref=work_ticket.ticket_id,
                    thread_ref=work_ticket.thread_ref,
                )
            ),
            self.write(
                MemoryWriteRequest(
                    namespace_id="company:default",
                    owner_id="quality-lead",
                    kind=MemoryKind.EVIDENCE,
                    content=f"Board-style quality evidence package: {summary}",
                    tags=["quality", verdict, "board_evidence"],
                    checkpoint_ref=checkpoint.checkpoint_id if checkpoint else None,
                    artifact_refs=artifact_refs,
                    source_trace=run_trace.runtrace_id,
                    work_ticket_ref=work_ticket.ticket_id,
                    thread_ref=work_ticket.thread_ref,
                )
            ),
        ]

    def create_review_memories(
        self,
        work_ticket: WorkTicket,
        run_trace: RunTrace,
        checkpoint: Checkpoint | None,
        verdict: str,
        summary: str,
        evidence_refs: list[str],
    ) -> list[MemoryRecord]:
        return [
            self.write(
                MemoryWriteRequest(
                    namespace_id="company:default",
                    owner_id="ceo",
                    kind=MemoryKind.EVIDENCE,
                    content=f"Review decision {verdict}: {summary}",
                    tags=["review_decision", verdict],
                    checkpoint_ref=checkpoint.checkpoint_id if checkpoint else None,
                    artifact_refs=evidence_refs,
                    source_trace=run_trace.runtrace_id,
                    work_ticket_ref=work_ticket.ticket_id,
                    thread_ref=work_ticket.thread_ref,
                )
            )
        ]

    def create_override_memories(
        self,
        work_ticket: WorkTicket,
        run_trace: RunTrace,
        checkpoint: Checkpoint,
        new_direction: str,
        supersede_refs: list[str],
    ) -> list[MemoryRecord]:
        return [
            self.write(
                MemoryWriteRequest(
                    namespace_id="company:default",
                    owner_id="ceo",
                    kind=MemoryKind.EPISODIC,
                    content=f"Override recovery summary: {new_direction}",
                    tags=["override_recovery", "rollback"],
                    checkpoint_ref=checkpoint.checkpoint_id,
                    artifact_refs=supersede_refs,
                    source_trace=run_trace.runtrace_id,
                    work_ticket_ref=work_ticket.ticket_id,
                    thread_ref=work_ticket.thread_ref,
                )
            )
        ]

    def create_escalation_memories(
        self,
        work_ticket: WorkTicket,
        run_trace: RunTrace,
        checkpoint: Checkpoint | None,
        reason: str,
        risk_notes: list[str],
    ) -> list[MemoryRecord]:
        content = f"Escalation summary: {reason}"
        if risk_notes:
            content = f"{content}; risks: {', '.join(risk_notes)}"
        return [
            self.write(
                MemoryWriteRequest(
                    namespace_id="company:default",
                    owner_id="chief-of-staff",
                    kind=MemoryKind.EPISODIC,
                    content=content,
                    tags=["escalation", "risk_summary"],
                    checkpoint_ref=checkpoint.checkpoint_id if checkpoint else None,
                    source_trace=run_trace.runtrace_id,
                    work_ticket_ref=work_ticket.ticket_id,
                    thread_ref=work_ticket.thread_ref,
                )
            )
        ]

    def create_launch_growth_memories(
        self,
        work_ticket: WorkTicket,
        run_trace: RunTrace,
        checkpoint: Checkpoint | None,
        task_graph: TaskGraph,
        node_outputs: dict[str, str],
    ) -> list[MemoryRecord]:
        if task_graph.workflow_recipe != "launch_growth":
            return []

        output_by_department = {
            node.owner_department: node_outputs.get(node.node_id, "")
            for node in task_graph.nodes
            if node.owner_department != "Executive Office" and node_outputs.get(node.node_id)
        }
        executive_summary = next(
            (
                node_outputs.get(node.node_id, "")
                for node in reversed(task_graph.nodes)
                if node.owner_department == "Executive Office" and node_outputs.get(node.node_id)
            ),
            "",
        )

        records: list[MemoryRecord] = []
        department_tags: dict[str, list[str]] = {
            "Growth & Marketing": ["launch_growth", "growth_plan", "channel_plan"],
            "Customer Success & Support": ["launch_growth", "support_readiness", "feedback_loop"],
            "Sales & Partnerships": ["launch_growth", "partner_motion", "distribution"],
            "Trust / Security / Legal": ["launch_growth", "risk_review", "compliance"],
        }
        department_kinds: dict[str, MemoryKind] = {
            "Growth & Marketing": MemoryKind.PROCEDURAL,
            "Customer Success & Support": MemoryKind.PROCEDURAL,
            "Sales & Partnerships": MemoryKind.EPISODIC,
            "Trust / Security / Legal": MemoryKind.EVIDENCE,
        }

        for department, content in output_by_department.items():
            namespace_id = self._department_namespace(department)
            owner_id = self._employee_for_department(department)
            records.append(
                self.write(
                    MemoryWriteRequest(
                        namespace_id=namespace_id,
                        owner_id=owner_id,
                        kind=department_kinds.get(department, MemoryKind.EPISODIC),
                        content=content,
                        tags=department_tags.get(department, ["launch_growth", "post_launch"]),
                        checkpoint_ref=checkpoint.checkpoint_id if checkpoint else None,
                        source_trace=run_trace.runtrace_id,
                        work_ticket_ref=work_ticket.ticket_id,
                        thread_ref=work_ticket.thread_ref,
                    )
                )
            )

        if executive_summary:
            records.append(
                self.write(
                    MemoryWriteRequest(
                        namespace_id="company:default",
                        owner_id="chief-of-staff",
                        kind=MemoryKind.SEMANTIC,
                        content=executive_summary,
                        tags=["launch_growth", "post_launch_feedback", "executive_synthesis"],
                        checkpoint_ref=checkpoint.checkpoint_id if checkpoint else None,
                        source_trace=run_trace.runtrace_id,
                        work_ticket_ref=work_ticket.ticket_id,
                        thread_ref=work_ticket.thread_ref,
                    )
                )
            )

        return records

    def get_namespace(self, namespace_id: str) -> MemoryNamespace:
        namespace = self._namespaces.get(namespace_id)
        if namespace is None:
            raise KeyError(namespace_id)
        return namespace

    def _bootstrap_namespaces(self) -> None:
        if self._namespaces.list():
            return

        company = get_company_profile()
        self._namespaces.save(
            MemoryNamespace(
                namespace_id=f"company:{company.company_id}",
                scope=MemoryScope.COMPANY_SHARED,
                owner=company.company_id,
                read_policy="authorized_company_shared",
                write_policy="chief_of_staff_managed",
                promotion_policy="company_approval_required",
            )
        )
        for department in get_departments():
            self._namespaces.save(
                MemoryNamespace(
                    namespace_id=self._department_namespace(department.department_name),
                    scope=MemoryScope.DEPARTMENT_SHARED,
                    owner=department.department_name,
                    read_policy="same_department_or_executive_office",
                    write_policy="department_or_executive_approval",
                    promotion_policy="department_promotion_required",
                )
            )
        for employee in get_employees():
            self._namespaces.save(
                MemoryNamespace(
                    namespace_id=f"employee:{employee.employee_id}",
                    scope=MemoryScope.AGENT_PRIVATE,
                    owner=employee.employee_id,
                    read_policy="owner_only",
                    write_policy="auto_private_write",
                    promotion_policy="private_auto_learning",
                )
            )

    def _default_visibility(self, scope: MemoryScope, scope_owner: str) -> str:
        if scope == MemoryScope.AGENT_PRIVATE:
            return f"private:{scope_owner}"
        if scope == MemoryScope.DEPARTMENT_SHARED:
            return f"department:{scope_owner}"
        return "company_authorized"

    def _department_namespace(self, department_name: str) -> str:
        normalized = department_name.lower().replace(" ", "-").replace("&", "and").replace("/", "-")
        return f"department:{normalized}"

    def _employee_for_department(self, department_name: str) -> str:
        for employee in get_employees():
            if employee.department == department_name:
                return employee.employee_id
        return "chief-of-staff"

    def _is_read_allowed(self, record: MemoryRecord, query: RecallQuery) -> bool:
        if record.scope == MemoryScope.AGENT_PRIVATE:
            return query.requester_id in {record.owner_id, "chief-of-staff", "ceo"}
        if record.scope == MemoryScope.DEPARTMENT_SHARED:
            return query.requester_department == record.scope_id or query.requester_id in {"chief-of-staff", "ceo"}
        if record.scope == MemoryScope.COMPANY_SHARED:
            if record.visibility == "restricted":
                return query.requester_id in {"chief-of-staff", "ceo"}
            return True
        return True


_memory_service = MemoryService(
    namespace_store=build_model_store(MemoryNamespace, "namespace_id", "memory_namespaces"),
    record_store=build_model_store(MemoryRecord, "memory_id", "memory_records"),
)


def get_memory_service() -> MemoryService:
    return _memory_service
