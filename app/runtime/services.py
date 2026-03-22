from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from operator import add
from typing import Annotated
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:  # pragma: no cover - compatibility fallback for older LangGraph builds.
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver

from app.company.bootstrap import get_departments
from app.control_plane.models import RunEvent, RunTraceStatus, TaskGraph, TaskGraphStatus
from app.control_plane.services import get_control_plane_service
from app.conversation.models import ConversationIntakeRequest, ConversationSurface
from app.conversation.services import get_conversation_service
from app.executive_office.models import CEOCommand
from app.executive_office.models import InteractionMode
from app.memory.services import get_memory_service
from app.company.models import TriggerType
from app.openclaw.services import get_openclaw_gateway_adapter
from app.runtime.models import PostLaunchFollowUpLink, PostLaunchRoutingResult, PostLaunchSummary, RuntimeExecutionResult, RuntimeState

POST_LAUNCH_MEMORY_TAGS = {
    "post_launch_feedback",
    "growth_plan",
    "support_readiness",
    "feedback_loop",
    "partner_motion",
    "risk_review",
}


def _merge_outputs(left: dict[str, str], right: dict[str, str]) -> dict[str, str]:
    return {**left, **right}


class LangGraphRuntimeService:
    def __init__(self) -> None:
        self._checkpointer = InMemorySaver()

    def execute_work_ticket(self, work_ticket_id: str) -> RuntimeExecutionResult:
        control_plane = get_control_plane_service()
        work_ticket = control_plane.get_required_work_ticket(work_ticket_id)
        if work_ticket.taskgraph_ref is None:
            raise ValueError("This work ticket does not have an executable TaskGraph")
        if work_ticket.runtrace_ref is None:
            raise ValueError("This work ticket does not have a linked RunTrace")

        task_graph = control_plane.get_required_task_graph(work_ticket.taskgraph_ref)
        if task_graph.status == TaskGraphStatus.ESCALATED:
            raise ValueError("Escalated TaskGraph cannot be executed until governance resolves it")

        runtime_thread_id = f"{work_ticket.thread_ref or work_ticket.ticket_id}:runtime:{uuid4().hex[:6]}"
        compiled_graph = self._compile(task_graph, work_ticket.runtrace_ref)

        control_plane.set_work_ticket_status(work_ticket_id, "executing")
        control_plane.append_run_trace_event(
            work_ticket.runtrace_ref,
            RunEvent(
                event_type="runtime_execution_started",
                message="LangGraph runtime execution started.",
                metadata={
                    "taskgraph_id": task_graph.taskgraph_id,
                    "runtime_thread_id": runtime_thread_id,
                },
            ),
            status=RunTraceStatus.ACTIVE,
        )
        conversation_service = get_conversation_service()
        existing_thread = (
            conversation_service.get_thread(work_ticket.thread_ref)
            if work_ticket.thread_ref
            else None
        )
        if existing_thread is not None:
            conversation_service.set_thread_status(work_ticket.thread_ref, "executing")

        final_state = compiled_graph.invoke(
            {
                "work_ticket_id": work_ticket.ticket_id,
                "work_ticket_title": work_ticket.title,
                "work_ticket_type": work_ticket.ticket_type,
                "taskgraph_id": task_graph.taskgraph_id,
                "runtrace_id": work_ticket.runtrace_ref,
                "surface": existing_thread.surface.value if existing_thread is not None else "runtime",
                "channel_ref": work_ticket.channel_ref or f"runtime:{work_ticket.ticket_id}",
                "executed_nodes": [],
                "node_outputs": {},
            },
            config={"configurable": {"thread_id": runtime_thread_id}},
        )

        task_graph = control_plane.reconcile_task_graph_execution(
            task_graph.taskgraph_id,
            final_state.get("executed_nodes", []),
        )
        final_ticket_status = self._completion_status_for(task_graph)
        work_ticket = control_plane.set_work_ticket_status(work_ticket_id, final_ticket_status)
        run_trace = control_plane.append_run_trace_event(
            work_ticket.runtrace_ref,
            RunEvent(
                event_type="runtime_execution_completed",
                message="LangGraph runtime execution completed.",
                metadata={
                    "taskgraph_id": task_graph.taskgraph_id,
                    "completed_nodes": str(len(final_state.get("executed_nodes", []))),
                    "runtime_thread_id": runtime_thread_id,
                },
            ),
            status=RunTraceStatus.COMPLETED,
        )
        checkpoint = control_plane.get_latest_checkpoint_for_ticket(work_ticket_id)
        memory_records = self._sync_runtime_memories(
            work_ticket=work_ticket,
            task_graph=task_graph,
            run_trace=run_trace,
            checkpoint=checkpoint,
            node_outputs=final_state.get("node_outputs", {}),
        )
        post_launch_follow_up = None
        if self._should_auto_route_post_launch(work_ticket, task_graph):
            post_launch_follow_up = self.route_post_launch_follow_up(work_ticket_id)
        run_trace = control_plane.get_required_run_trace(work_ticket.runtrace_ref)

        conversation_thread = None
        if work_ticket.thread_ref and conversation_service.get_thread(work_ticket.thread_ref) is not None:
            conversation_thread = conversation_service.set_thread_status(work_ticket.thread_ref, final_ticket_status)

        return RuntimeExecutionResult(
            runtime_thread_id=runtime_thread_id,
            work_ticket=work_ticket,
            task_graph=task_graph,
            run_trace=run_trace,
            conversation_thread=conversation_thread,
            executed_nodes=final_state.get("executed_nodes", []),
            node_outputs=final_state.get("node_outputs", {}),
            memory_records=memory_records,
            post_launch_follow_up=post_launch_follow_up,
        )

    def route_post_launch_follow_up(self, source_work_ticket_id: str) -> PostLaunchRoutingResult:
        control_plane = get_control_plane_service()
        conversation_service = get_conversation_service()
        source_work_ticket = control_plane.get_required_work_ticket(source_work_ticket_id)
        if source_work_ticket.runtrace_ref is None or source_work_ticket.taskgraph_ref is None:
            raise ValueError("This work ticket does not have a completed launch workflow")

        source_run_trace = control_plane.get_required_run_trace(source_work_ticket.runtrace_ref)
        source_task_graph = control_plane.get_required_task_graph(source_work_ticket.taskgraph_ref)
        if source_task_graph.workflow_recipe != "launch_growth":
            raise ValueError("Post-launch follow-up is only available for launch_growth workflows")

        existing_link = self._existing_post_launch_follow_up(source_work_ticket, source_run_trace)
        if existing_link is not None:
            return self._hydrate_post_launch_routing_result(existing_link, already_exists=True)

        intake_result = conversation_service.intake(
            ConversationIntakeRequest(
                surface=ConversationSurface.DASHBOARD,
                channel_id=f"dashboard:post-launch:{source_work_ticket.ticket_id}",
                initiator_id="chief-of-staff",
                participant_ids=["ceo", "chief-of-staff"],
                bound_agent_ids=["growth-lead", "customer-success-lead"],
                title=f"Post-launch cadence · {source_work_ticket.title}",
                command=CEOCommand(
                    intent=(
                        f"整理 {source_work_ticket.title} 上线后的用户反馈、支持问题、增长信号和下一步分发建议，"
                        "形成 post-launch cadence 摘要"
                    ),
                    trigger_type=TriggerType.SCHEDULED_HEARTBEAT,
                    activation_hint=["Growth & Marketing", "Customer Success & Support"],
                    surface="dashboard",
                ),
            )
        )

        follow_up_ticket = intake_result.command_result.work_ticket
        follow_up_run_trace = intake_result.command_result.run_trace
        follow_up_task_graph = intake_result.command_result.task_graph
        link = PostLaunchFollowUpLink(
            source_work_ticket_ref=source_work_ticket.ticket_id,
            source_title=source_work_ticket.title,
            source_runtrace_ref=source_run_trace.runtrace_id,
            follow_up_ticket_ref=follow_up_ticket.ticket_id,
            follow_up_title=follow_up_ticket.title,
            follow_up_runtrace_ref=follow_up_run_trace.runtrace_id,
            follow_up_thread_ref=intake_result.thread.thread_id,
            trigger_type=TriggerType.SCHEDULED_HEARTBEAT.value,
            created_at=datetime.now(UTC),
            status=follow_up_ticket.status,
            note="post_launch_cadence_auto_route",
        )
        control_plane.append_run_trace_event(
            source_run_trace.runtrace_id,
            RunEvent(
                event_type="post_launch_followup_created",
                message="Post-launch cadence work ticket created.",
                metadata={
                    "follow_up_ticket_ref": follow_up_ticket.ticket_id,
                    "follow_up_runtrace_ref": follow_up_run_trace.runtrace_id,
                    "follow_up_thread_ref": intake_result.thread.thread_id,
                    "trigger_type": TriggerType.SCHEDULED_HEARTBEAT.value,
                },
            ),
            status=source_run_trace.status,
        )
        return PostLaunchRoutingResult(
            already_exists=False,
            link=link,
            follow_up_work_ticket=follow_up_ticket,
            follow_up_run_trace=follow_up_run_trace,
            follow_up_task_graph=follow_up_task_graph,
            follow_up_thread=intake_result.thread,
        )

    def get_post_launch_summary(self) -> PostLaunchSummary:
        control_plane = get_control_plane_service()
        all_tickets = {ticket.ticket_id: ticket for ticket in control_plane.list_work_tickets()}
        launch_run_traces = [
            trace for trace in control_plane.list_run_traces() if trace.workflow_recipe == "launch_growth"
        ]
        launch_tickets = [
            all_tickets[trace.work_ticket_ref]
            for trace in launch_run_traces
            if trace.work_ticket_ref in all_tickets
        ]

        follow_ups: list[PostLaunchFollowUpLink] = []
        for trace in launch_run_traces:
            source_ticket = all_tickets.get(trace.work_ticket_ref)
            if source_ticket is None:
                continue
            existing_link = self._existing_post_launch_follow_up(source_ticket, trace)
            if existing_link is not None:
                follow_ups.append(existing_link)

        feedback_memories = [
            record
            for record in get_memory_service().list_records()
            if set(record.tags).intersection(POST_LAUNCH_MEMORY_TAGS)
        ]
        feedback_memories.sort(key=lambda record: record.created_at, reverse=True)
        follow_ups.sort(key=lambda link: link.created_at, reverse=True)
        launch_tickets.sort(key=lambda ticket: ticket.ticket_id, reverse=True)
        return PostLaunchSummary(
            launch_tickets=launch_tickets,
            follow_ups=follow_ups,
            feedback_memories=feedback_memories[:24],
        )

    def _compile(self, task_graph: TaskGraph, runtrace_id: str):
        class CompiledRuntimeState(RuntimeState):
            executed_nodes: Annotated[list[str], add]
            node_outputs: Annotated[dict[str, str], _merge_outputs]

        builder = StateGraph(CompiledRuntimeState)
        dependents: dict[str, list[str]] = defaultdict(list)
        root_nodes: list[str] = []

        for node in task_graph.nodes:
            builder.add_node(
                node.node_id,
                self._make_node_runner(
                    taskgraph_id=task_graph.taskgraph_id,
                    workflow_recipe=task_graph.workflow_recipe,
                    runtrace_id=runtrace_id,
                    node_id=node.node_id,
                    department=node.owner_department,
                    output_kind=node.output_kind or "Deliverable",
                    depends_on=node.depends_on,
                ),
            )
            if not node.depends_on:
                root_nodes.append(node.node_id)
            for dependency in node.depends_on:
                dependents[dependency].append(node.node_id)

        for node_id in root_nodes:
            builder.add_edge(START, node_id)

        for node in task_graph.nodes:
            next_nodes = dependents.get(node.node_id, [])
            if not next_nodes:
                builder.add_edge(node.node_id, END)
                continue
            for next_node_id in next_nodes:
                builder.add_edge(node.node_id, next_node_id)

        return builder.compile(checkpointer=self._checkpointer)

    def _make_node_runner(
        self,
        *,
        taskgraph_id: str,
        workflow_recipe: str,
        runtrace_id: str,
        node_id: str,
        department: str,
        output_kind: str,
        depends_on: list[str],
    ):
        employee_id = self._employee_for_department(department)

        def run_node(state: RuntimeState) -> RuntimeState:
            control_plane = get_control_plane_service()
            control_plane.mark_task_node_active(taskgraph_id, node_id)
            control_plane.append_run_trace_event(
                runtrace_id,
                RunEvent(
                    event_type="task_node_started",
                    message=f"{department} started node execution.",
                    metadata={
                        "node_id": node_id,
                        "department": department,
                        "taskgraph_id": taskgraph_id,
                    },
                ),
                status=RunTraceStatus.ACTIVE,
            )

            work_ticket = control_plane.get_required_work_ticket(state["work_ticket_id"])
            upstream_outputs = {
                dependency: state.get("node_outputs", {}).get(dependency, "")
                for dependency in depends_on
                if state.get("node_outputs", {}).get(dependency)
            }
            dialogue_result = get_openclaw_gateway_adapter().invoke_agent(
                employee_id=employee_id,
                user_message=self._build_node_prompt(
                    workflow_recipe=workflow_recipe,
                    node_id=node_id,
                    department=department,
                    output_kind=output_kind,
                    work_ticket_title=state["work_ticket_title"],
                    work_ticket_type=state["work_ticket_type"],
                    upstream_outputs=upstream_outputs,
                ),
                work_ticket=work_ticket,
                channel_id=state.get("channel_ref", f"runtime:{state['work_ticket_id']}"),
                surface=state.get("surface", "runtime"),
                visible_participants=["dashboard-mirror", "runtrace"],
            )
            output = dialogue_result.reply_text

            updated_graph = control_plane.complete_task_node(taskgraph_id, node_id)
            trace_status = (
                RunTraceStatus.COMPLETED if updated_graph.status == TaskGraphStatus.COMPLETED else RunTraceStatus.ACTIVE
            )
            control_plane.attach_run_trace_agent_turn(
                runtrace_id,
                f"{dialogue_result.openclaw_agent_id or employee_id}:{dialogue_result.session_key or node_id}",
            )
            control_plane.append_run_trace_event(
                runtrace_id,
                RunEvent(
                    event_type="task_node_completed",
                    message=f"{department} completed node execution.",
                    metadata={
                        "node_id": node_id,
                        "department": department,
                        "output_kind": output_kind,
                        "employee_id": employee_id,
                        "strategy": dialogue_result.strategy,
                        "model_ref": dialogue_result.model_ref,
                        "session_key": dialogue_result.session_key or "none",
                    },
                ),
                status=trace_status,
            )
            return {
                "executed_nodes": [node_id],
                "node_outputs": {node_id: output},
            }

        return run_node

    def _build_node_prompt(
        self,
        *,
        workflow_recipe: str,
        node_id: str,
        department: str,
        output_kind: str,
        work_ticket_title: str,
        work_ticket_type: str,
        upstream_outputs: dict[str, str],
    ) -> str:
        prompt = (
            f"你正在执行 TaskGraph 节点 `{node_id}`。\n"
            f"WorkTicket: {work_ticket_title}\n"
            f"TicketType: {work_ticket_type}\n"
            f"Department: {department}\n"
            f"Workflow recipe: {workflow_recipe}\n"
            f"Expected output: {output_kind}\n"
        )

        if upstream_outputs:
            joined_outputs = "\n\n".join(
                f"[{dependency}]\n{output}" for dependency, output in upstream_outputs.items()
            )
            prompt += f"\n上游节点输出：\n{joined_outputs}\n"

        if workflow_recipe == "discovery_synthesis" and output_kind == "CrossAgentSynthesis":
            prompt += (
                "\n请把 Research / Product / Design 的输入综合成一个统一结论，而不是简单拼接。\n"
                "输出必须分成四段：\n"
                "1. 事实\n"
                "2. 推断\n"
                "3. 建议\n"
                "4. 待确认项\n"
                "如果不同部门观点存在冲突，请明确写出冲突点与取舍建议。"
            )
        elif workflow_recipe == "discovery_synthesis":
            prompt += (
                "\n当前任务属于 Discovery / Synthesis Loop。\n"
                "请从本席位职责出发，输出一段可供后续综合的分析，不要越权替其他部门下结论。"
            )
        elif workflow_recipe == "launch_growth" and output_kind == "LaunchDecisionBrief":
            prompt += (
                "\n当前任务属于 Launch / Growth Loop 的综合阶段。\n"
                "请把增长、支持、合作和风险输入整合为一个上线决策摘要。\n"
                "输出必须分成六段：\n"
                "1. 发布目标\n"
                "2. 渠道与传播动作\n"
                "3. 支持与反馈闭环\n"
                "4. 风险与合规\n"
                "5. CEO 建议决策\n"
                "6. 待确认项\n"
                "如果某个可选部门未参与，也要在相关段落里说明依赖空缺。"
            )
        elif workflow_recipe == "launch_growth":
            prompt += (
                "\n当前任务属于 Launch / Growth Loop。\n"
                "请从本席位职责出发，给出上线前后可执行的动作、交付物和回传机制。\n"
                "输出要覆盖：目标受众、动作建议、成功信号、需要同步给 Executive Office 的风险或阻塞。"
            )
        else:
            prompt += "\n请基于本席位职责给出该节点的可执行产出摘要。"

        return prompt

    def _employee_for_department(self, department: str) -> str:
        for item in get_departments():
            if item.department_name == department:
                return item.default_employee
        return "chief-of-staff"

    def _completion_status_for(self, task_graph: TaskGraph) -> str:
        if task_graph.interaction_mode == InteractionMode.FORMAL_PROJECT:
            return "execution_completed"
        return "completed"

    def _should_auto_route_post_launch(self, work_ticket, task_graph: TaskGraph) -> bool:
        if task_graph.workflow_recipe != "launch_growth":
            return False
        if work_ticket.channel_ref and work_ticket.channel_ref.startswith("dashboard:post-launch:"):
            return False
        return True

    def _sync_runtime_memories(
        self,
        *,
        work_ticket,
        task_graph: TaskGraph,
        run_trace,
        checkpoint,
        node_outputs: dict[str, str],
    ):
        if task_graph.workflow_recipe != "launch_growth":
            return []

        memory_records = get_memory_service().create_launch_growth_memories(
            work_ticket=work_ticket,
            run_trace=run_trace,
            checkpoint=checkpoint,
            task_graph=task_graph,
            node_outputs=node_outputs,
        )
        if checkpoint is not None:
            control_plane = get_control_plane_service()
            for memory_record in memory_records:
                control_plane.attach_memory_to_checkpoint(checkpoint.checkpoint_id, memory_record.memory_id)
        if memory_records:
            get_control_plane_service().append_run_trace_event(
                run_trace.runtrace_id,
                RunEvent(
                    event_type="launch_feedback_synced",
                    message="Launch / Growth outputs synced into Memory Fabric.",
                    metadata={
                        "memory_records": str(len(memory_records)),
                        "workflow_recipe": task_graph.workflow_recipe,
                    },
                ),
                status=RunTraceStatus.COMPLETED,
            )
        return memory_records

    def _existing_post_launch_follow_up(
        self,
        source_work_ticket,
        source_run_trace,
    ) -> PostLaunchFollowUpLink | None:
        control_plane = get_control_plane_service()
        for event in source_run_trace.events:
            if event.event_type != "post_launch_followup_created":
                continue
            follow_up_ticket_ref = event.metadata.get("follow_up_ticket_ref")
            if not follow_up_ticket_ref:
                continue
            follow_up_ticket = control_plane.get_work_ticket(follow_up_ticket_ref)
            follow_up_title = follow_up_ticket.title if follow_up_ticket is not None else follow_up_ticket_ref
            return PostLaunchFollowUpLink(
                source_work_ticket_ref=source_work_ticket.ticket_id,
                source_title=source_work_ticket.title,
                source_runtrace_ref=source_run_trace.runtrace_id,
                follow_up_ticket_ref=follow_up_ticket_ref,
                follow_up_title=follow_up_title,
                follow_up_runtrace_ref=event.metadata.get("follow_up_runtrace_ref"),
                follow_up_thread_ref=event.metadata.get("follow_up_thread_ref"),
                trigger_type=event.metadata.get("trigger_type", TriggerType.SCHEDULED_HEARTBEAT.value),
                created_at=event.created_at,
                status=follow_up_ticket.status if follow_up_ticket is not None else "unknown",
                note="post_launch_cadence_auto_route",
            )
        return None

    def _hydrate_post_launch_routing_result(
        self,
        link: PostLaunchFollowUpLink,
        *,
        already_exists: bool,
    ) -> PostLaunchRoutingResult:
        control_plane = get_control_plane_service()
        conversation_service = get_conversation_service()
        follow_up_work_ticket = control_plane.get_required_work_ticket(link.follow_up_ticket_ref)
        follow_up_run_trace = control_plane.get_required_run_trace(link.follow_up_runtrace_ref or follow_up_work_ticket.runtrace_ref)
        follow_up_task_graph = (
            control_plane.get_task_graph(follow_up_work_ticket.taskgraph_ref)
            if follow_up_work_ticket.taskgraph_ref
            else None
        )
        follow_up_thread = (
            conversation_service.get_thread(link.follow_up_thread_ref)
            if link.follow_up_thread_ref
            else None
        )
        hydrated_link = link.model_copy(update={"status": follow_up_work_ticket.status, "follow_up_title": follow_up_work_ticket.title})
        return PostLaunchRoutingResult(
            already_exists=already_exists,
            link=hydrated_link,
            follow_up_work_ticket=follow_up_work_ticket,
            follow_up_run_trace=follow_up_run_trace,
            follow_up_task_graph=follow_up_task_graph,
            follow_up_thread=follow_up_thread,
        )


_runtime_service = LangGraphRuntimeService()


def get_runtime_service() -> LangGraphRuntimeService:
    return _runtime_service
