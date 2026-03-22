from __future__ import annotations

from uuid import uuid4

from app.company.models import WorkTicket
from app.control_plane.governance import BudgetPolicyService, TriggerScheduler
from app.control_plane.models import (
    BudgetCheck,
    Checkpoint,
    CheckpointKind,
    CommandIntakeResult,
    RunEvent,
    RunTrace,
    RunTraceStatus,
    TaskGraph,
    TaskGraphStatus,
    TaskNode,
    TaskNodeStatus,
    TriggerContext,
    TriggerValidationStatus,
)
from app.executive_office.models import CEOCommand, CommandClassificationResult, InteractionMode
from app.executive_office.services import ExecutiveOfficeService
from app.store import ModelStore, build_model_store

FORMAL_PROJECT_CHAIN: tuple[str, ...] = (
    "Executive Office",
    "Product",
    "Project Management",
    "Design & UX",
    "Engineering",
    "Quality",
)

DISCOVERY_SYNTHESIS_PARALLEL: tuple[str, ...] = (
    "Research & Intelligence",
    "Product",
    "Design & UX",
)

LAUNCH_GROWTH_CORE: tuple[str, ...] = (
    "Growth & Marketing",
    "Customer Success & Support",
)

LAUNCH_GROWTH_OPTIONAL: tuple[str, ...] = (
    "Sales & Partnerships",
    "Trust / Security / Legal",
)


class WorkTicketService:
    def __init__(self, store: ModelStore[WorkTicket]) -> None:
        self._store = store

    def upsert_from_classification(
        self,
        classification: CommandClassificationResult,
        task_graph: TaskGraph | None,
        status_override: str | None = None,
    ) -> WorkTicket:
        ticket = classification.work_ticket.model_copy(
            update={
                "taskgraph_ref": task_graph.taskgraph_id if task_graph else None,
                "status": status_override or self._ticket_status_for(classification.interaction_mode),
            }
        )
        return self._store.save(ticket)

    def attach_run_trace(self, ticket_id: str, runtrace_id: str) -> WorkTicket:
        ticket = self.get_required(ticket_id)
        return self._store.save(ticket.model_copy(update={"runtrace_ref": runtrace_id}))

    def get(self, ticket_id: str) -> WorkTicket | None:
        return self._store.get(ticket_id)

    def get_required(self, ticket_id: str) -> WorkTicket:
        ticket = self.get(ticket_id)
        if ticket is None:
            raise KeyError(ticket_id)
        return ticket

    def list(self) -> list[WorkTicket]:
        return self._store.list()

    def set_status(self, ticket_id: str, status: str) -> WorkTicket:
        ticket = self.get_required(ticket_id)
        return self._store.save(ticket.model_copy(update={"status": status}))

    def attach_artifact(self, ticket_id: str, artifact_id: str) -> WorkTicket:
        ticket = self.get_required(ticket_id)
        artifacts = list(ticket.artifacts)
        if artifact_id not in artifacts:
            artifacts.append(artifact_id)
        return self._store.save(ticket.model_copy(update={"artifacts": artifacts}))

    def set_supersede_refs(self, ticket_id: str, supersede_refs: list[str]) -> WorkTicket:
        ticket = self.get_required(ticket_id)
        deduped = list(dict.fromkeys([*ticket.supersede_refs, *supersede_refs]))
        return self._store.save(ticket.model_copy(update={"supersede_refs": deduped}))

    def _ticket_status_for(self, mode: InteractionMode) -> str:
        if mode == InteractionMode.IDEA_CAPTURE:
            return "captured"
        if mode == InteractionMode.QUICK_CONSULT:
            return "consulting"
        if mode == InteractionMode.DEPARTMENT_TASK:
            return "queued"
        if mode == InteractionMode.FORMAL_PROJECT:
            return "active"
        if mode == InteractionMode.REVIEW_DECISION:
            return "under_review"
        if mode == InteractionMode.OVERRIDE_RECOVERY:
            return "override_pending"
        return "escalated"


class TaskGraphService:
    def __init__(self, store: ModelStore[TaskGraph]) -> None:
        self._store = store

    def create_for(self, classification: CommandClassificationResult) -> TaskGraph | None:
        if classification.workflow_recipe == "discovery_synthesis":
            return self._create_discovery_synthesis_graph(classification)
        if classification.workflow_recipe == "launch_growth":
            return self._create_launch_growth_graph(classification)

        departments = self._departments_for(classification)
        if not departments:
            return None

        ticket_id = classification.work_ticket.ticket_id
        taskgraph_id = f"tg-{uuid4().hex[:8]}"
        nodes: list[TaskNode] = []
        previous_node_id: str | None = None

        for index, department in enumerate(departments):
            node_id = f"task-{index + 1}-{uuid4().hex[:6]}"
            nodes.append(
                TaskNode(
                    node_id=node_id,
                    title=f"{department} handling {classification.interaction_mode.value}",
                    owner_department=department,
                    status=TaskNodeStatus.READY if previous_node_id is None else TaskNodeStatus.BLOCKED,
                    depends_on=[] if previous_node_id is None else [previous_node_id],
                    output_kind=self._output_kind_for(classification.interaction_mode, department),
                )
            )
            previous_node_id = node_id

        graph = TaskGraph(
            taskgraph_id=taskgraph_id,
            interaction_mode=classification.interaction_mode,
            workflow_recipe=classification.workflow_recipe,
            status=TaskGraphStatus.READY,
            goal_lineage_ref=classification.goal_request.goal_lineage_ref,
            work_ticket_ref=ticket_id,
            nodes=nodes,
        )
        return self._store.save(graph)

    def get(self, taskgraph_id: str) -> TaskGraph | None:
        return self._store.get(taskgraph_id)

    def get_required(self, taskgraph_id: str) -> TaskGraph:
        graph = self.get(taskgraph_id)
        if graph is None:
            raise KeyError(taskgraph_id)
        return graph

    def list(self) -> list[TaskGraph]:
        return self._store.list()

    def restore_from_snapshot(self, snapshot: TaskGraph) -> TaskGraph:
        restored_nodes: list[TaskNode] = []
        for index, node in enumerate(snapshot.nodes):
            restored_nodes.append(
                node.model_copy(update={"status": TaskNodeStatus.READY if index == 0 else TaskNodeStatus.BLOCKED})
            )

        restored_graph = snapshot.model_copy(update={"status": TaskGraphStatus.READY, "nodes": restored_nodes})
        return self._store.save(restored_graph)

    def set_status(self, taskgraph_id: str, status: TaskGraphStatus) -> TaskGraph:
        graph = self.get_required(taskgraph_id)
        return self._store.save(graph.model_copy(update={"status": status}))

    def mark_node_active(self, taskgraph_id: str, node_id: str) -> TaskGraph:
        graph = self.get_required(taskgraph_id)
        updated_nodes = [
            node.model_copy(update={"status": TaskNodeStatus.ACTIVE}) if node.node_id == node_id else node for node in graph.nodes
        ]
        return self._store.save(graph.model_copy(update={"status": TaskGraphStatus.ACTIVE, "nodes": updated_nodes}))

    def complete_node(self, taskgraph_id: str, node_id: str) -> TaskGraph:
        graph = self.get_required(taskgraph_id)
        completed_node_ids = {
            node.node_id
            for node in graph.nodes
            if node.node_id == node_id or node.status == TaskNodeStatus.COMPLETED
        }

        updated_nodes: list[TaskNode] = []
        for node in graph.nodes:
            if node.node_id == node_id:
                updated_nodes.append(node.model_copy(update={"status": TaskNodeStatus.COMPLETED}))
                continue

            if node.status == TaskNodeStatus.BLOCKED and all(dep in completed_node_ids for dep in node.depends_on):
                updated_nodes.append(node.model_copy(update={"status": TaskNodeStatus.READY}))
                continue

            updated_nodes.append(node)

        all_completed = all(node.status == TaskNodeStatus.COMPLETED for node in updated_nodes)
        return self._store.save(
            graph.model_copy(
                update={
                    "status": TaskGraphStatus.COMPLETED if all_completed else TaskGraphStatus.ACTIVE,
                    "nodes": updated_nodes,
                }
            )
        )

    def reconcile_completed_nodes(self, taskgraph_id: str, completed_node_ids: list[str]) -> TaskGraph:
        graph = self.get_required(taskgraph_id)
        completed_set = {
            node.node_id for node in graph.nodes if node.status == TaskNodeStatus.COMPLETED
        }
        completed_set.update(completed_node_ids)

        updated_nodes: list[TaskNode] = []
        for node in graph.nodes:
            if node.node_id in completed_set:
                updated_nodes.append(node.model_copy(update={"status": TaskNodeStatus.COMPLETED}))
            elif all(dep in completed_set for dep in node.depends_on):
                updated_nodes.append(node.model_copy(update={"status": TaskNodeStatus.READY}))
            else:
                updated_nodes.append(node)

        all_completed = all(node.status == TaskNodeStatus.COMPLETED for node in updated_nodes)
        next_status = TaskGraphStatus.COMPLETED if all_completed else TaskGraphStatus.ACTIVE
        return self._store.save(graph.model_copy(update={"status": next_status, "nodes": updated_nodes}))

    def _departments_for(self, classification: CommandClassificationResult) -> list[str]:
        mode = classification.interaction_mode
        recommended = classification.recommended_departments

        if mode in {InteractionMode.IDEA_CAPTURE, InteractionMode.QUICK_CONSULT}:
            return []
        if mode == InteractionMode.DEPARTMENT_TASK:
            return recommended[:1]
        if mode == InteractionMode.FORMAL_PROJECT:
            return list(FORMAL_PROJECT_CHAIN)
        if mode == InteractionMode.REVIEW_DECISION:
            return ["Executive Office", "Quality"]
        unique_departments = ["Executive Office", *recommended]
        return list(dict.fromkeys(unique_departments))

    def _output_kind_for(self, mode: InteractionMode, department: str) -> str:
        if mode == InteractionMode.DEPARTMENT_TASK:
            return "TaskResult"
        if mode == InteractionMode.FORMAL_PROJECT and department == "Quality":
            return "Checkpoint"
        if mode == InteractionMode.REVIEW_DECISION:
            return "DecisionRecord"
        if mode == InteractionMode.OVERRIDE_RECOVERY:
            return "OverrideDecision"
        if mode == InteractionMode.ESCALATION:
            return "EscalationSummary"
        return "Deliverable"

    def _create_discovery_synthesis_graph(self, classification: CommandClassificationResult) -> TaskGraph:
        ticket_id = classification.work_ticket.ticket_id
        taskgraph_id = f"tg-{uuid4().hex[:8]}"
        framing_node_id = f"task-1-{uuid4().hex[:6]}"
        parallel_node_ids = {
            department: f"task-{index + 2}-{uuid4().hex[:6]}"
            for index, department in enumerate(DISCOVERY_SYNTHESIS_PARALLEL)
        }
        synthesis_node_id = f"task-5-{uuid4().hex[:6]}"

        nodes = [
            TaskNode(
                node_id=framing_node_id,
                title="Executive Office frames the discovery question",
                owner_department="Executive Office",
                status=TaskNodeStatus.READY,
                output_kind="DiscoveryBrief",
            ),
            *[
                TaskNode(
                    node_id=node_id,
                    title=f"{department} produces discovery analysis",
                    owner_department=department,
                    status=TaskNodeStatus.BLOCKED,
                    depends_on=[framing_node_id],
                    output_kind=self._discovery_output_kind_for(department),
                )
                for department, node_id in parallel_node_ids.items()
            ],
            TaskNode(
                node_id=synthesis_node_id,
                title="Executive Office synthesizes cross-agent findings",
                owner_department="Executive Office",
                status=TaskNodeStatus.BLOCKED,
                depends_on=list(parallel_node_ids.values()),
                output_kind="CrossAgentSynthesis",
            ),
        ]

        graph = TaskGraph(
            taskgraph_id=taskgraph_id,
            interaction_mode=classification.interaction_mode,
            workflow_recipe="discovery_synthesis",
            status=TaskGraphStatus.READY,
            goal_lineage_ref=classification.goal_request.goal_lineage_ref,
            work_ticket_ref=ticket_id,
            nodes=nodes,
        )
        return self._store.save(graph)

    def _create_launch_growth_graph(self, classification: CommandClassificationResult) -> TaskGraph:
        ticket_id = classification.work_ticket.ticket_id
        taskgraph_id = f"tg-{uuid4().hex[:8]}"
        framing_node_id = f"task-1-{uuid4().hex[:6]}"

        active_optional_departments = [
            department
            for department in LAUNCH_GROWTH_OPTIONAL
            if department in classification.recommended_departments
        ]
        launch_departments = [*LAUNCH_GROWTH_CORE, *active_optional_departments]
        launch_node_ids = {
            department: f"task-{index + 2}-{uuid4().hex[:6]}"
            for index, department in enumerate(launch_departments)
        }
        synthesis_node_id = f"task-{len(launch_departments) + 2}-{uuid4().hex[:6]}"

        nodes = [
            TaskNode(
                node_id=framing_node_id,
                title="Executive Office frames the launch milestone",
                owner_department="Executive Office",
                status=TaskNodeStatus.READY,
                output_kind="LaunchBrief",
            ),
            *[
                TaskNode(
                    node_id=node_id,
                    title=f"{department} produces launch-readiness output",
                    owner_department=department,
                    status=TaskNodeStatus.BLOCKED,
                    depends_on=[framing_node_id],
                    output_kind=self._launch_output_kind_for(department),
                )
                for department, node_id in launch_node_ids.items()
            ],
            TaskNode(
                node_id=synthesis_node_id,
                title="Executive Office synthesizes launch and feedback plan",
                owner_department="Executive Office",
                status=TaskNodeStatus.BLOCKED,
                depends_on=list(launch_node_ids.values()),
                output_kind="LaunchDecisionBrief",
            ),
        ]

        graph = TaskGraph(
            taskgraph_id=taskgraph_id,
            interaction_mode=classification.interaction_mode,
            workflow_recipe="launch_growth",
            status=TaskGraphStatus.READY,
            goal_lineage_ref=classification.goal_request.goal_lineage_ref,
            work_ticket_ref=ticket_id,
            nodes=nodes,
        )
        return self._store.save(graph)

    def _discovery_output_kind_for(self, department: str) -> str:
        if department == "Research & Intelligence":
            return "SignalSummary"
        if department == "Product":
            return "ProductHypothesis"
        if department == "Design & UX":
            return "ExperienceDirection"
        return "DiscoveryContribution"

    def _launch_output_kind_for(self, department: str) -> str:
        if department == "Growth & Marketing":
            return "LaunchChannelPlan"
        if department == "Customer Success & Support":
            return "SupportReadiness"
        if department == "Sales & Partnerships":
            return "PartnerMotion"
        if department == "Trust / Security / Legal":
            return "RiskReview"
        return "LaunchContribution"


class RunTraceService:
    def __init__(self, store: ModelStore[RunTrace]) -> None:
        self._store = store

    def create_for(
        self,
        command: CEOCommand,
        classification: CommandClassificationResult,
        work_ticket: WorkTicket,
        task_graph: TaskGraph | None,
        budget_checks: list[BudgetCheck],
        trigger_context: TriggerContext,
    ) -> RunTrace:
        runtrace_id = f"rt-{uuid4().hex[:8]}"
        events = [
            RunEvent(
                event_type="command_received",
                message="CEOCommand entered Executive Office intake.",
                metadata={
                    "priority": command.priority,
                    "trigger_type": classification.trigger_type.value,
                    "surface": command.surface,
                },
            ),
            RunEvent(
                event_type="trigger_validated",
                message=trigger_context.message,
                metadata={
                    "trigger_type": trigger_context.trigger_type.value,
                    "trigger_status": trigger_context.status.value,
                    "routing_rule": trigger_context.routing_rule,
                },
            ),
            RunEvent(
                event_type="classification_completed",
                message="Interaction mode and participation scope resolved.",
                metadata={
                    "interaction_mode": classification.interaction_mode.value,
                    "participation_scope": classification.participation_scope.value,
                },
            ),
            RunEvent(
                event_type="work_ticket_created",
                message="Control-plane work ticket created and linked.",
                metadata={"ticket_id": work_ticket.ticket_id, "ticket_status": work_ticket.status},
            ),
        ]
        for check in budget_checks:
            events.append(
                RunEvent(
                    event_type="budget_checked",
                    message=check.message,
                    metadata={
                        "scope": check.scope.value,
                        "status": check.status.value,
                        "estimated_cost": str(check.estimated_cost),
                        "limit": "none" if check.limit is None else str(check.limit),
                    },
                )
            )
        if task_graph:
            events.append(
                RunEvent(
                    event_type="task_graph_created",
                    message="TaskGraph created for routed execution.",
                    metadata={"taskgraph_id": task_graph.taskgraph_id, "node_count": str(len(task_graph.nodes))},
                )
            )
        else:
            events.append(
                RunEvent(
                    event_type="task_graph_skipped",
                    message="Interaction mode does not require a full TaskGraph in V1.",
                    metadata={"interaction_mode": classification.interaction_mode.value},
                )
            )

        trace = RunTrace(
            runtrace_id=runtrace_id,
            interaction_mode=classification.interaction_mode,
            workflow_recipe=classification.workflow_recipe,
            trigger_type=classification.trigger_type,
            status=self._trace_status_for(classification.interaction_mode, budget_checks, trigger_context),
            surface=command.surface,
            thread_ref=work_ticket.thread_ref,
            channel_ref=work_ticket.channel_ref,
            goal_lineage_ref=classification.goal_request.goal_lineage_ref,
            work_ticket_ref=work_ticket.ticket_id,
            taskgraph_ref=task_graph.taskgraph_id if task_graph else None,
            activated_departments=classification.recommended_departments,
            visible_speakers=self._visible_speakers_for(command.surface, classification),
            dispatch_targets=[],
            agent_turn_refs=[],
            events=events,
        )
        return self._store.save(trace)

    def get(self, runtrace_id: str) -> RunTrace | None:
        return self._store.get(runtrace_id)

    def list(self) -> list[RunTrace]:
        return self._store.list()

    def mark_restored(self, runtrace_id: str, checkpoint_id: str, taskgraph_id: str | None) -> RunTrace:
        trace = self.get_required(runtrace_id)
        updated = trace.model_copy(
            update={
                "status": RunTraceStatus.ROUTED,
                "taskgraph_ref": taskgraph_id,
                "events": [
                    *trace.events,
                    RunEvent(
                        event_type="checkpoint_restored",
                        message="Checkpoint restored into active control-plane state.",
                        metadata={
                            "checkpoint_id": checkpoint_id,
                            "taskgraph_id": taskgraph_id or "none",
                        },
                    ),
                ],
            }
        )
        return self._store.save(updated)

    def append_event(
        self,
        runtrace_id: str,
        event: RunEvent,
        status: RunTraceStatus | None = None,
    ) -> RunTrace:
        trace = self.get_required(runtrace_id)
        updated = trace.model_copy(update={"status": status or trace.status, "events": [*trace.events, event]})
        return self._store.save(updated)

    def set_dispatch_targets(self, runtrace_id: str, targets: list[str]) -> RunTrace:
        trace = self.get_required(runtrace_id)
        merged_targets = list(dict.fromkeys([*trace.dispatch_targets, *targets]))
        return self._store.save(trace.model_copy(update={"dispatch_targets": merged_targets}))

    def mark_superseded(
        self,
        runtrace_id: str,
        *,
        successor_runtrace_id: str,
        reason: str,
    ) -> RunTrace:
        trace = self.get_required(runtrace_id)
        return self._store.save(
            trace.model_copy(
                update={
                    "status": RunTraceStatus.SUPERSEDED,
                    "superseded_by_runtrace_ref": successor_runtrace_id,
                    "interruption_reason": reason,
                    "events": [
                        *trace.events,
                        RunEvent(
                            event_type="run_superseded",
                            message="RunTrace was superseded by a newer run on the same thread.",
                            metadata={
                                "runtrace_id": runtrace_id,
                                "superseded_by_runtrace_id": successor_runtrace_id,
                                "reason": reason,
                            },
                        ),
                    ],
                }
            )
        )

    def set_supersedes_runtrace_ref(self, runtrace_id: str, supersedes_runtrace_ref: str | None) -> RunTrace:
        trace = self.get_required(runtrace_id)
        return self._store.save(trace.model_copy(update={"supersedes_runtrace_ref": supersedes_runtrace_ref}))

    def set_visible_turn_count(self, runtrace_id: str, visible_turn_count: int) -> RunTrace:
        trace = self.get_required(runtrace_id)
        return self._store.save(trace.model_copy(update={"visible_turn_count": visible_turn_count}))

    def set_delivery_guard_epoch(self, runtrace_id: str, epoch: int) -> RunTrace:
        trace = self.get_required(runtrace_id)
        return self._store.save(trace.model_copy(update={"delivery_guard_epoch": epoch}))

    def set_interruption_reason(self, runtrace_id: str, reason: str | None) -> RunTrace:
        trace = self.get_required(runtrace_id)
        return self._store.save(trace.model_copy(update={"interruption_reason": reason}))

    def set_interruption_dispatch_targets(self, runtrace_id: str, targets: list[str]) -> RunTrace:
        trace = self.get_required(runtrace_id)
        return self._store.save(
            trace.model_copy(update={"interruption_dispatch_targets": list(dict.fromkeys(targets))})
        )

    def attach_agent_turn_ref(self, runtrace_id: str, turn_ref: str) -> RunTrace:
        trace = self.get_required(runtrace_id)
        refs = list(dict.fromkeys([*trace.agent_turn_refs, turn_ref]))
        return self._store.save(trace.model_copy(update={"agent_turn_refs": refs}))

    def set_handoff_origin(self, runtrace_id: str, handoff_origin: str | None) -> RunTrace:
        trace = self.get_required(runtrace_id)
        return self._store.save(trace.model_copy(update={"handoff_origin": handoff_origin}))

    def set_handoff_resolution_basis(self, runtrace_id: str, handoff_resolution_basis: str | None) -> RunTrace:
        trace = self.get_required(runtrace_id)
        return self._store.save(trace.model_copy(update={"handoff_resolution_basis": handoff_resolution_basis}))

    def set_collaboration_intent(self, runtrace_id: str, collaboration_intent: str | None) -> RunTrace:
        trace = self.get_required(runtrace_id)
        return self._store.save(trace.model_copy(update={"collaboration_intent": collaboration_intent}))

    def set_reply_visible_named_targets(self, runtrace_id: str, targets: list[str]) -> RunTrace:
        trace = self.get_required(runtrace_id)
        return self._store.save(
            trace.model_copy(update={"reply_visible_named_targets": list(dict.fromkeys(targets))})
        )

    def set_handoff_chain_state(
        self,
        runtrace_id: str,
        *,
        spoken_bot_ids: list[str],
        remaining_bot_ids: list[str],
        remaining_turn_budget: int,
        stop_reason: str | None = None,
    ) -> RunTrace:
        trace = self.get_required(runtrace_id)
        return self._store.save(
            trace.model_copy(
                update={
                    "spoken_bot_ids": spoken_bot_ids,
                    "remaining_bot_ids": remaining_bot_ids,
                    "remaining_turn_budget": remaining_turn_budget,
                    "stop_reason": stop_reason,
                }
            )
        )

    def flag_handoff_contract_violation(self, runtrace_id: str) -> RunTrace:
        trace = self.get_required(runtrace_id)
        return self._store.save(trace.model_copy(update={"handoff_contract_violation": True}))

    def flag_handoff_repetition_violation(self, runtrace_id: str) -> RunTrace:
        trace = self.get_required(runtrace_id)
        return self._store.save(trace.model_copy(update={"handoff_repetition_violation": True}))

    def flag_stopped_by_turn_limit(self, runtrace_id: str) -> RunTrace:
        trace = self.get_required(runtrace_id)
        return self._store.save(trace.model_copy(update={"stopped_by_turn_limit": True}))

    def get_required(self, runtrace_id: str) -> RunTrace:
        trace = self.get(runtrace_id)
        if trace is None:
            raise KeyError(runtrace_id)
        return trace

    def _trace_status_for(
        self,
        mode: InteractionMode,
        budget_checks: list[BudgetCheck],
        trigger_context: TriggerContext,
    ) -> RunTraceStatus:
        if trigger_context.status == TriggerValidationStatus.REJECTED:
            return RunTraceStatus.BLOCKED
        if any(check.status.value == "blocked" for check in budget_checks):
            return RunTraceStatus.BLOCKED
        if mode in {InteractionMode.OVERRIDE_RECOVERY, InteractionMode.ESCALATION}:
            return RunTraceStatus.ESCALATED
        return RunTraceStatus.ROUTED

    def _visible_speakers_for(
        self,
        surface: str,
        classification: CommandClassificationResult,
    ) -> list[str]:
        if surface == "feishu_dm" and classification.recommended_departments:
            return ["Chief of Staff", classification.recommended_departments[0]]
        if surface == "feishu_group":
            return ["Chief of Staff", *classification.recommended_departments]
        return ["Chief of Staff"]


class CheckpointStore:
    def __init__(self, store: ModelStore[Checkpoint]) -> None:
        self._store = store

    def create_for_intake(
        self,
        command: CEOCommand,
        classification: CommandClassificationResult,
        work_ticket: WorkTicket,
        task_graph: TaskGraph | None,
        run_trace: RunTrace,
    ) -> Checkpoint | None:
        kind = self._kind_for(command, classification.interaction_mode)
        if kind is None:
            return None

        checkpoint = Checkpoint(
            checkpoint_id=f"cp-{uuid4().hex[:8]}",
            work_ticket_ref=work_ticket.ticket_id,
            taskgraph_ref=task_graph.taskgraph_id if task_graph else None,
            runtrace_ref=run_trace.runtrace_id,
            goal_lineage_ref=classification.goal_request.goal_lineage_ref,
            kind=kind,
            stage=self._stage_for(kind),
            task_graph_snapshot=task_graph.model_copy(deep=True) if task_graph else None,
            memory_refs=[],
            artifact_refs=[],
            approval_state="pending",
            verdict_state="pending",
            rollback_scope="task_graph",
        )
        return self._store.save(checkpoint)

    def get(self, checkpoint_id: str) -> Checkpoint | None:
        return self._store.get(checkpoint_id)

    def get_required(self, checkpoint_id: str) -> Checkpoint:
        checkpoint = self.get(checkpoint_id)
        if checkpoint is None:
            raise KeyError(checkpoint_id)
        return checkpoint

    def list_for_ticket(self, ticket_id: str) -> list[Checkpoint]:
        return [checkpoint for checkpoint in self._store.list() if checkpoint.work_ticket_ref == ticket_id]

    def latest_for_ticket(self, ticket_id: str) -> Checkpoint | None:
        checkpoints = self.list_for_ticket(ticket_id)
        if not checkpoints:
            return None
        return checkpoints[-1]

    def update_verdict(self, checkpoint_id: str, verdict_state: str) -> Checkpoint:
        checkpoint = self.get_required(checkpoint_id)
        return self._store.save(checkpoint.model_copy(update={"verdict_state": verdict_state}))

    def update_approval(self, checkpoint_id: str, approval_state: str) -> Checkpoint:
        checkpoint = self.get_required(checkpoint_id)
        return self._store.save(checkpoint.model_copy(update={"approval_state": approval_state}))

    def attach_artifact(self, checkpoint_id: str, artifact_id: str) -> Checkpoint:
        checkpoint = self.get_required(checkpoint_id)
        artifact_refs = list(checkpoint.artifact_refs)
        if artifact_id not in artifact_refs:
            artifact_refs.append(artifact_id)
        return self._store.save(checkpoint.model_copy(update={"artifact_refs": artifact_refs}))

    def attach_memory_ref(self, checkpoint_id: str, memory_id: str) -> Checkpoint:
        checkpoint = self.get_required(checkpoint_id)
        memory_refs = list(checkpoint.memory_refs)
        if memory_id not in memory_refs:
            memory_refs.append(memory_id)
        return self._store.save(checkpoint.model_copy(update={"memory_refs": memory_refs}))

    def mark_superseded(self, checkpoint_id: str, decision_id: str) -> Checkpoint:
        checkpoint = self.get_required(checkpoint_id)
        return self._store.save(checkpoint.model_copy(update={"superseded_by": decision_id}))

    def _kind_for(self, command: CEOCommand, mode: InteractionMode) -> CheckpointKind | None:
        if mode == InteractionMode.FORMAL_PROJECT:
            return CheckpointKind.FORMAL
        if mode == InteractionMode.DEPARTMENT_TASK and command.checkpoint_requested:
            return CheckpointKind.LIGHTWEIGHT
        return None

    def _stage_for(self, kind: CheckpointKind) -> str:
        if kind == CheckpointKind.FORMAL:
            return "formal_project_intake"
        return "department_task_lightweight"


class ControlPlaneService:
    def __init__(
        self,
        executive_office: ExecutiveOfficeService,
        work_tickets: WorkTicketService,
        task_graphs: TaskGraphService,
        run_traces: RunTraceService,
        budget_policy: BudgetPolicyService,
        trigger_scheduler: TriggerScheduler,
        checkpoints: CheckpointStore,
    ) -> None:
        self._executive_office = executive_office
        self._work_tickets = work_tickets
        self._task_graphs = task_graphs
        self._run_traces = run_traces
        self._budget_policy = budget_policy
        self._trigger_scheduler = trigger_scheduler
        self._checkpoints = checkpoints

    def intake_command(self, command: CEOCommand) -> CommandIntakeResult:
        classification = self._executive_office.classify_command(command)
        budget_checks = self._budget_policy.evaluate(command, classification)
        trigger_context = self._trigger_scheduler.validate(command, classification)
        blocked = self._budget_policy.has_blocking_issue(budget_checks) or (
            trigger_context.status == TriggerValidationStatus.REJECTED
        )

        task_graph = None if blocked else self._task_graphs.create_for(classification)
        work_ticket = self._work_tickets.upsert_from_classification(
            classification,
            task_graph,
            status_override=self._ticket_status_override(blocked, trigger_context),
        )
        run_trace = self._run_traces.create_for(
            command,
            classification,
            work_ticket,
            task_graph,
            budget_checks,
            trigger_context,
        )
        work_ticket = self._work_tickets.attach_run_trace(work_ticket.ticket_id, run_trace.runtrace_id)
        checkpoint = self._checkpoints.create_for_intake(
            command=command,
            classification=classification,
            work_ticket=work_ticket,
            task_graph=task_graph,
            run_trace=run_trace,
        )
        from app.memory.services import get_memory_service

        memory_records = get_memory_service().create_intake_memories(
            command=command,
            classification=classification,
            work_ticket=work_ticket,
            run_trace=run_trace,
            checkpoint=checkpoint,
            task_graph=task_graph,
        )
        if checkpoint is not None:
            for memory_record in memory_records:
                checkpoint = self._checkpoints.attach_memory_ref(checkpoint.checkpoint_id, memory_record.memory_id)
        classification = classification.model_copy(update={"work_ticket": work_ticket})
        return CommandIntakeResult(
            classification=classification,
            work_ticket=work_ticket,
            task_graph=task_graph,
            run_trace=run_trace,
            budget_checks=budget_checks,
            trigger_context=trigger_context,
            checkpoint=checkpoint,
        )

    def get_work_ticket(self, ticket_id: str) -> WorkTicket | None:
        return self._work_tickets.get(ticket_id)

    def list_work_tickets(self) -> list[WorkTicket]:
        return self._work_tickets.list()

    def get_required_work_ticket(self, ticket_id: str) -> WorkTicket:
        return self._work_tickets.get_required(ticket_id)

    def set_work_ticket_status(self, ticket_id: str, status: str) -> WorkTicket:
        return self._work_tickets.set_status(ticket_id, status)

    def attach_artifact_to_ticket(self, ticket_id: str, artifact_id: str) -> WorkTicket:
        return self._work_tickets.attach_artifact(ticket_id, artifact_id)

    def set_work_ticket_supersede_refs(self, ticket_id: str, supersede_refs: list[str]) -> WorkTicket:
        return self._work_tickets.set_supersede_refs(ticket_id, supersede_refs)

    def get_task_graph(self, taskgraph_id: str | None) -> TaskGraph | None:
        if taskgraph_id is None:
            return None
        return self._task_graphs.get(taskgraph_id)

    def get_required_task_graph(self, taskgraph_id: str) -> TaskGraph:
        return self._task_graphs.get_required(taskgraph_id)

    def set_task_graph_status(self, taskgraph_id: str, status: TaskGraphStatus) -> TaskGraph:
        return self._task_graphs.set_status(taskgraph_id, status)

    def mark_task_node_active(self, taskgraph_id: str, node_id: str) -> TaskGraph:
        return self._task_graphs.mark_node_active(taskgraph_id, node_id)

    def complete_task_node(self, taskgraph_id: str, node_id: str) -> TaskGraph:
        return self._task_graphs.complete_node(taskgraph_id, node_id)

    def reconcile_task_graph_execution(self, taskgraph_id: str, completed_node_ids: list[str]) -> TaskGraph:
        return self._task_graphs.reconcile_completed_nodes(taskgraph_id, completed_node_ids)

    def get_run_trace(self, runtrace_id: str) -> RunTrace | None:
        return self._run_traces.get(runtrace_id)

    def list_run_traces(self) -> list[RunTrace]:
        return self._run_traces.list()

    def get_required_run_trace(self, runtrace_id: str) -> RunTrace:
        return self._run_traces.get_required(runtrace_id)

    def append_run_trace_event(
        self,
        runtrace_id: str,
        event: RunEvent,
        status: RunTraceStatus | None = None,
    ) -> RunTrace:
        return self._run_traces.append_event(runtrace_id, event, status)

    def get_checkpoint(self, checkpoint_id: str) -> Checkpoint | None:
        return self._checkpoints.get(checkpoint_id)

    def set_run_trace_dispatch_targets(self, runtrace_id: str, targets: list[str]) -> RunTrace:
        return self._run_traces.set_dispatch_targets(runtrace_id, targets)

    def mark_run_trace_superseded(
        self,
        runtrace_id: str,
        *,
        successor_runtrace_id: str,
        reason: str,
    ) -> RunTrace:
        return self._run_traces.mark_superseded(
            runtrace_id,
            successor_runtrace_id=successor_runtrace_id,
            reason=reason,
        )

    def set_run_trace_supersedes_runtrace_ref(
        self,
        runtrace_id: str,
        supersedes_runtrace_ref: str | None,
    ) -> RunTrace:
        return self._run_traces.set_supersedes_runtrace_ref(runtrace_id, supersedes_runtrace_ref)

    def set_run_trace_visible_turn_count(self, runtrace_id: str, visible_turn_count: int) -> RunTrace:
        return self._run_traces.set_visible_turn_count(runtrace_id, visible_turn_count)

    def set_run_trace_delivery_guard_epoch(self, runtrace_id: str, epoch: int) -> RunTrace:
        return self._run_traces.set_delivery_guard_epoch(runtrace_id, epoch)

    def set_run_trace_interruption_reason(self, runtrace_id: str, reason: str | None) -> RunTrace:
        return self._run_traces.set_interruption_reason(runtrace_id, reason)

    def set_run_trace_interruption_dispatch_targets(self, runtrace_id: str, targets: list[str]) -> RunTrace:
        return self._run_traces.set_interruption_dispatch_targets(runtrace_id, targets)

    def attach_run_trace_agent_turn(self, runtrace_id: str, turn_ref: str) -> RunTrace:
        return self._run_traces.attach_agent_turn_ref(runtrace_id, turn_ref)

    def set_run_trace_handoff_origin(self, runtrace_id: str, handoff_origin: str | None) -> RunTrace:
        return self._run_traces.set_handoff_origin(runtrace_id, handoff_origin)

    def set_run_trace_handoff_resolution_basis(self, runtrace_id: str, handoff_resolution_basis: str | None) -> RunTrace:
        return self._run_traces.set_handoff_resolution_basis(runtrace_id, handoff_resolution_basis)

    def set_run_trace_collaboration_intent(self, runtrace_id: str, collaboration_intent: str | None) -> RunTrace:
        return self._run_traces.set_collaboration_intent(runtrace_id, collaboration_intent)

    def set_run_trace_reply_visible_named_targets(self, runtrace_id: str, targets: list[str]) -> RunTrace:
        return self._run_traces.set_reply_visible_named_targets(runtrace_id, targets)

    def set_run_trace_handoff_chain_state(
        self,
        runtrace_id: str,
        *,
        spoken_bot_ids: list[str],
        remaining_bot_ids: list[str],
        remaining_turn_budget: int,
        stop_reason: str | None = None,
    ) -> RunTrace:
        return self._run_traces.set_handoff_chain_state(
            runtrace_id,
            spoken_bot_ids=spoken_bot_ids,
            remaining_bot_ids=remaining_bot_ids,
            remaining_turn_budget=remaining_turn_budget,
            stop_reason=stop_reason,
        )

    def flag_run_trace_handoff_contract_violation(self, runtrace_id: str) -> RunTrace:
        return self._run_traces.flag_handoff_contract_violation(runtrace_id)

    def flag_run_trace_handoff_repetition_violation(self, runtrace_id: str) -> RunTrace:
        return self._run_traces.flag_handoff_repetition_violation(runtrace_id)

    def flag_run_trace_stopped_by_turn_limit(self, runtrace_id: str) -> RunTrace:
        return self._run_traces.flag_stopped_by_turn_limit(runtrace_id)

    def list_checkpoints_for_ticket(self, ticket_id: str) -> list[Checkpoint]:
        return self._checkpoints.list_for_ticket(ticket_id)

    def get_latest_checkpoint_for_ticket(self, ticket_id: str) -> Checkpoint | None:
        return self._checkpoints.latest_for_ticket(ticket_id)

    def update_checkpoint_verdict(self, checkpoint_id: str, verdict_state: str) -> Checkpoint:
        return self._checkpoints.update_verdict(checkpoint_id, verdict_state)

    def update_checkpoint_approval(self, checkpoint_id: str, approval_state: str) -> Checkpoint:
        return self._checkpoints.update_approval(checkpoint_id, approval_state)

    def attach_artifact_to_checkpoint(self, checkpoint_id: str, artifact_id: str) -> Checkpoint:
        return self._checkpoints.attach_artifact(checkpoint_id, artifact_id)

    def attach_memory_to_checkpoint(self, checkpoint_id: str, memory_id: str) -> Checkpoint:
        return self._checkpoints.attach_memory_ref(checkpoint_id, memory_id)

    def mark_checkpoint_superseded(self, checkpoint_id: str, decision_id: str) -> Checkpoint:
        return self._checkpoints.mark_superseded(checkpoint_id, decision_id)

    def collect_supersede_refs(self, work_ticket_id: str, checkpoint_id: str | None = None) -> list[str]:
        work_ticket = self.get_required_work_ticket(work_ticket_id)
        checkpoint = self.get_checkpoint(checkpoint_id) if checkpoint_id else self.get_latest_checkpoint_for_ticket(work_ticket_id)
        refs: list[str] = []
        if work_ticket.thread_ref:
            refs.append(f"thread:{work_ticket.thread_ref}")
        if work_ticket.channel_ref:
            refs.append(f"channel:{work_ticket.channel_ref}")
        if work_ticket.taskgraph_ref:
            refs.append(f"taskgraph:{work_ticket.taskgraph_ref}")
        if work_ticket.runtrace_ref:
            refs.append(f"runtrace:{work_ticket.runtrace_ref}")
        refs.extend(f"artifact:{artifact_id}" for artifact_id in work_ticket.artifacts)

        if checkpoint is not None:
            refs.append(f"checkpoint:{checkpoint.checkpoint_id}")
            if checkpoint.taskgraph_ref:
                refs.append(f"checkpoint_taskgraph:{checkpoint.taskgraph_ref}")
            refs.extend(f"checkpoint_artifact:{artifact_id}" for artifact_id in checkpoint.artifact_refs)
            refs.extend(f"memory:{memory_id}" for memory_id in checkpoint.memory_refs)

        return list(dict.fromkeys(refs))

    def restore_checkpoint(self, checkpoint_id: str) -> tuple[Checkpoint, WorkTicket, TaskGraph | None, RunTrace]:
        checkpoint = self._checkpoints.get_required(checkpoint_id)
        restored_graph = None
        if checkpoint.task_graph_snapshot is not None:
            restored_graph = self._task_graphs.restore_from_snapshot(checkpoint.task_graph_snapshot)
        work_ticket = self._work_tickets.set_status(checkpoint.work_ticket_ref, "restored")
        run_trace = self._run_traces.mark_restored(
            checkpoint.runtrace_ref,
            checkpoint.checkpoint_id,
            restored_graph.taskgraph_id if restored_graph else None,
        )
        work_ticket = self._work_tickets.attach_run_trace(work_ticket.ticket_id, run_trace.runtrace_id)
        return checkpoint, work_ticket, restored_graph, run_trace

    def _ticket_status_override(self, blocked: bool, trigger_context: TriggerContext) -> str | None:
        if trigger_context.status == TriggerValidationStatus.REJECTED:
            return "trigger_rejected"
        if blocked:
            return "budget_blocked"
        return None


_control_plane_service = ControlPlaneService(
    executive_office=ExecutiveOfficeService(),
    work_tickets=WorkTicketService(build_model_store(WorkTicket, "ticket_id", "work_tickets")),
    task_graphs=TaskGraphService(build_model_store(TaskGraph, "taskgraph_id", "task_graphs")),
    run_traces=RunTraceService(build_model_store(RunTrace, "runtrace_id", "run_traces")),
    budget_policy=BudgetPolicyService(),
    trigger_scheduler=TriggerScheduler(),
    checkpoints=CheckpointStore(build_model_store(Checkpoint, "checkpoint_id", "checkpoints")),
)


def get_control_plane_service() -> ControlPlaneService:
    return _control_plane_service
