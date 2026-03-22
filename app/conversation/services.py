from __future__ import annotations

from uuid import uuid4

from app.company.bootstrap import get_departments, get_employees
from app.conversation.models import (
    BotSeatBinding,
    ChannelBinding,
    ChannelBindingUpdateRequest,
    ConversationIntakeRequest,
    ConversationIntakeResult,
    ConversationSurface,
    ConversationThread,
    PendingHandoffState,
    RoomPolicy,
    RoomPolicyUpdateRequest,
    SpeakerMode,
)
from app.control_plane.services import get_control_plane_service
from app.executive_office.models import CEOCommand
from app.feishu.config import get_feishu_bot_app_configs
from app.store import ModelStore, build_model_store

CORE_FEISHU_DEPARTMENTS = {
    "Executive Office",
    "Product",
    "Research & Intelligence",
    "Project Management",
    "Design & UX",
    "Engineering",
    "Quality",
}


class ConversationService:
    def __init__(
        self,
        thread_store: ModelStore[ConversationThread],
        channel_binding_store: ModelStore[ChannelBinding],
        bot_binding_store: ModelStore[BotSeatBinding],
        room_policy_store: ModelStore[RoomPolicy],
    ) -> None:
        self._threads = thread_store
        self._channel_bindings = channel_binding_store
        self._bot_bindings = bot_binding_store
        self._room_policies = room_policy_store
        self._bootstrap_defaults()

    def intake(self, request: ConversationIntakeRequest) -> ConversationIntakeResult:
        channel_binding = self._get_channel_binding_for(request.surface)
        thread = self._resolve_thread(request, channel_binding)
        command = self._command_for_thread(request.command, request.surface, thread.thread_id, request.channel_id)
        command_result = get_control_plane_service().intake_command(command)

        updated_thread = thread.model_copy(
            update={
                "interaction_mode": command_result.classification.interaction_mode,
                "work_ticket_ref": command_result.work_ticket.ticket_id,
                "taskgraph_ref": command_result.task_graph.taskgraph_id if command_result.task_graph else None,
                "runtrace_ref": command_result.run_trace.runtrace_id,
                "bound_agent_ids": request.bound_agent_ids
                or thread.bound_agent_ids
                or self._default_agents_for_surface(request.surface, command_result.classification.recommended_departments),
                "status": "linked",
            }
        )
        updated_thread = self._threads.save(updated_thread)
        return ConversationIntakeResult(thread=updated_thread, command_result=command_result)

    def get_thread(self, thread_id: str) -> ConversationThread | None:
        return self._threads.get(thread_id)

    def find_thread_by_surface_channel(
        self,
        surface: ConversationSurface,
        channel_id: str,
    ) -> ConversationThread | None:
        matches = [
            thread
            for thread in self._threads.list()
            if thread.surface == surface and thread.channel_id == channel_id
        ]
        if not matches:
            return None
        matches.sort(key=lambda thread: thread.created_at, reverse=True)
        return matches[0]

    def get_required_thread(self, thread_id: str) -> ConversationThread:
        thread = self.get_thread(thread_id)
        if thread is None:
            raise KeyError(thread_id)
        return thread

    def list_threads(self) -> list[ConversationThread]:
        return self._threads.list()

    def set_thread_status(self, thread_id: str, status: str) -> ConversationThread:
        thread = self.get_required_thread(thread_id)
        return self._threads.save(thread.model_copy(update={"status": status}))

    def set_active_runtrace(
        self,
        thread_id: str,
        *,
        runtrace_id: str,
        delivery_guard_epoch: int,
        superseded_runtrace_ref: str | None = None,
    ) -> ConversationThread:
        thread = self.get_required_thread(thread_id)
        superseded_refs = list(thread.superseded_runtrace_refs)
        if superseded_runtrace_ref and superseded_runtrace_ref not in superseded_refs:
            superseded_refs.append(superseded_runtrace_ref)
        return self._threads.save(
            thread.model_copy(
                update={
                    "runtrace_ref": runtrace_id,
                    "active_runtrace_ref": runtrace_id,
                    "delivery_guard_epoch": delivery_guard_epoch,
                    "superseded_runtrace_refs": superseded_refs,
                }
            )
        )

    def set_last_committed_state(self, thread_id: str, state: dict[str, object]) -> ConversationThread:
        thread = self.get_required_thread(thread_id)
        return self._threads.save(thread.model_copy(update={"last_committed_state": dict(state)}))

    def set_pending_handoff(
        self,
        thread_id: str,
        pending_handoff: PendingHandoffState | None,
    ) -> ConversationThread:
        thread = self.get_required_thread(thread_id)
        return self._threads.save(thread.model_copy(update={"pending_handoff": pending_handoff}))

    def attach_openclaw_session(self, thread_id: str, employee_id: str, session_key: str) -> ConversationThread:
        thread = self.get_required_thread(thread_id)
        session_refs = dict(thread.openclaw_session_refs)
        session_refs[employee_id] = session_key
        return self._threads.save(thread.model_copy(update={"openclaw_session_refs": session_refs}))

    def merge_thread_visibility(
        self,
        thread_id: str,
        *,
        participant_ids: list[str] | None = None,
        bound_agent_ids: list[str] | None = None,
    ) -> ConversationThread:
        thread = self.get_required_thread(thread_id)
        merged_participants = list(
            dict.fromkeys(
                [
                    *thread.participant_ids,
                    *(participant_ids or []),
                ]
            )
        )
        merged_agents = list(
            dict.fromkeys(
                [
                    *thread.bound_agent_ids,
                    *(bound_agent_ids or []),
                ]
            )
        )
        return self._threads.save(
            thread.model_copy(
                update={
                    "participant_ids": merged_participants,
                    "bound_agent_ids": merged_agents,
                }
            )
        )

    def start_new_thread(
        self,
        *,
        surface: ConversationSurface,
        channel_id: str,
        initiator_id: str,
        participant_ids: list[str],
        bound_agent_ids: list[str],
        title: str,
    ) -> ConversationThread:
        channel_binding = self._get_channel_binding_for(surface)
        room_policy_ref = channel_binding.room_policy_ref if surface == ConversationSurface.FEISHU_GROUP else None
        thread = ConversationThread(
            thread_id=f"ct-{uuid4().hex[:8]}",
            surface=surface,
            channel_id=channel_id,
            provider=channel_binding.provider,
            title=title,
            participant_ids=list(dict.fromkeys([initiator_id, *participant_ids])),
            bound_agent_ids=list(dict.fromkeys(bound_agent_ids)),
            channel_binding_ref=channel_binding.binding_id,
            room_policy_ref=room_policy_ref,
            visible_room_ref=channel_id if surface == ConversationSurface.FEISHU_GROUP else None,
            status="draft",
        )
        return self._threads.save(thread)

    def list_channel_bindings(self) -> list[ChannelBinding]:
        return self._channel_bindings.list()

    def list_bot_seat_bindings(self) -> list[BotSeatBinding]:
        return self._bot_bindings.list()

    def get_bot_binding_by_app_id(self, app_id: str) -> BotSeatBinding | None:
        for binding in self._bot_bindings.list():
            if binding.feishu_app_id == app_id:
                return binding
        return None

    def get_bot_binding_by_employee_id(self, employee_id: str) -> BotSeatBinding | None:
        for binding in self._bot_bindings.list():
            if binding.virtual_employee == employee_id:
                return binding
        return None

    def list_room_policies(self) -> list[RoomPolicy]:
        return self._room_policies.list()

    def update_channel_binding(self, binding_id: str, request: ChannelBindingUpdateRequest) -> ChannelBinding:
        binding = self._get_required_channel_binding(binding_id)
        return self._channel_bindings.save(
            binding.model_copy(
                update={
                    "default_route": request.default_route,
                    "mention_policy": request.mention_policy,
                    "sync_back_policy": request.sync_back_policy,
                    "room_policy_ref": request.room_policy_ref,
                }
            )
        )

    def update_room_policy(self, room_policy_id: str, request: RoomPolicyUpdateRequest) -> RoomPolicy:
        policy = self._get_required_room_policy(room_policy_id)
        return self._room_policies.save(
            policy.model_copy(
                update={
                    "speaker_mode": request.speaker_mode,
                    "visible_participants": request.visible_participants,
                    "turn_taking_rule": request.turn_taking_rule,
                    "escalation_rule": request.escalation_rule,
                }
            )
        )

    def _resolve_thread(self, request: ConversationIntakeRequest, channel_binding: ChannelBinding) -> ConversationThread:
        if request.thread_id:
            existing = self._threads.get(request.thread_id)
            if existing is None:
                raise KeyError(request.thread_id)
            participant_ids = list(dict.fromkeys([*existing.participant_ids, *request.participant_ids]))
            bound_agent_ids = list(dict.fromkeys([*existing.bound_agent_ids, *request.bound_agent_ids]))
            return self._threads.save(
                existing.model_copy(
                    update={
                        "participant_ids": participant_ids,
                        "bound_agent_ids": bound_agent_ids,
                    }
                )
            )

        room_policy_ref = channel_binding.room_policy_ref if request.surface == ConversationSurface.FEISHU_GROUP else None
        thread = ConversationThread(
            thread_id=f"ct-{uuid4().hex[:8]}",
            surface=request.surface,
            channel_id=request.channel_id,
            provider=channel_binding.provider,
            title=request.title or request.command.intent[:80],
            participant_ids=list(dict.fromkeys([request.initiator_id, *request.participant_ids])),
            bound_agent_ids=request.bound_agent_ids,
            channel_binding_ref=channel_binding.binding_id,
            room_policy_ref=room_policy_ref,
            visible_room_ref=request.channel_id if request.surface == ConversationSurface.FEISHU_GROUP else None,
            status="draft",
        )
        return self._threads.save(thread)

    def _command_for_thread(
        self,
        command: CEOCommand,
        surface: ConversationSurface,
        thread_id: str,
        channel_id: str,
    ) -> CEOCommand:
        return command.model_copy(
            update={
                "surface": surface.value,
                "thread_ref": thread_id,
                "entry_channel": channel_id,
            }
        )

    def _get_channel_binding_for(self, surface: ConversationSurface) -> ChannelBinding:
        for binding in self._channel_bindings.list():
            if binding.surface == surface:
                return binding
        raise KeyError(surface.value)

    def _get_required_channel_binding(self, binding_id: str) -> ChannelBinding:
        for binding in self._channel_bindings.list():
            if binding.binding_id == binding_id:
                return binding
        raise KeyError(binding_id)

    def _get_required_room_policy(self, room_policy_id: str) -> RoomPolicy:
        for policy in self._room_policies.list():
            if policy.room_policy_id == room_policy_id:
                return policy
        raise KeyError(room_policy_id)

    def _default_agents_for_surface(self, surface: ConversationSurface, departments: list[str]) -> list[str]:
        if surface == ConversationSurface.DASHBOARD:
            return ["chief-of-staff"]

        agents: list[str] = []
        employees_by_department = {employee.department: employee.employee_id for employee in get_employees()}
        for department in departments:
            employee_id = employees_by_department.get(department)
            if employee_id is not None:
                agents.append(employee_id)
        return list(dict.fromkeys(agents or ([] if surface == ConversationSurface.FEISHU_GROUP else ["chief-of-staff"])))

    def _bootstrap_defaults(self) -> None:
        self._bootstrap_room_and_channel_defaults()
        self._sync_bot_bindings()

    def _bootstrap_room_and_channel_defaults(self) -> None:
        executive_room = self._ensure_room_policy(
            RoomPolicy(
                room_policy_id="room-executive",
                room_type="Executive Room",
                speaker_mode=SpeakerMode.MENTION_FAN_OUT_VISIBLE,
                visible_participants=["ceo-visible-room", "dashboard-mirror", "chief-of-staff"],
                turn_taking_rule="mentioned_agents_reply_and_transcript_mirrors_to_visible_room",
                escalation_rule="ceo_decision_required_for_high_risk",
            )
        )
        project_room = self._ensure_room_policy(
            RoomPolicy(
                room_policy_id="room-project",
                room_type="Project Room",
                speaker_mode=SpeakerMode.MENTION_FAN_OUT_VISIBLE,
                visible_participants=["ceo-visible-room", "dashboard-mirror", "project-participants"],
                turn_taking_rule="mentioned_agents_speak_directly_or_in_visible_turns",
                escalation_rule="quality_or_conflict_routes_back_to_executive_office",
            )
        )
        self._ensure_room_policy(
            RoomPolicy(
                room_policy_id="room-launch",
                room_type="Launch Room",
                speaker_mode=SpeakerMode.MENTION_FAN_OUT_VISIBLE,
                visible_participants=[
                    "dashboard-mirror",
                    "ceo-visible-room",
                    "chief-of-staff",
                    "product-lead",
                    "delivery-lead",
                    "design-lead",
                    "research-lead",
                ],
                turn_taking_rule="launch_core_bots_reply_in_visible_room_turns",
                escalation_rule="launch_scope_or_market_risk_routes_back_to_executive_office",
            )
        )
        self._ensure_room_policy(
            RoomPolicy(
                room_policy_id="room-ops",
                room_type="Ops Room",
                speaker_mode=SpeakerMode.MENTION_FAN_OUT_VISIBLE,
                visible_participants=[
                    "dashboard-mirror",
                    "ceo-visible-room",
                    "chief-of-staff",
                    "delivery-lead",
                    "engineering-lead",
                    "quality-lead",
                ],
                turn_taking_rule="ops_triage_and_delivery_risk_replies_stay_visible",
                escalation_rule="production_or_quality_risks_route_to_executive_office",
            )
        )
        self._ensure_room_policy(
            RoomPolicy(
                room_policy_id="room-support",
                room_type="Support Room",
                speaker_mode=SpeakerMode.MENTION_FAN_OUT_VISIBLE,
                visible_participants=[
                    "dashboard-mirror",
                    "ceo-visible-room",
                    "chief-of-staff",
                    "product-lead",
                    "quality-lead",
                ],
                turn_taking_rule="support_triage_and_quality_feedback_transcript_stays_visible",
                escalation_rule="repeated_customer_issues_route_to_quality_and_executive_office",
            )
        )
        self._ensure_room_policy(
            RoomPolicy(
                room_policy_id="room-review",
                room_type="Review Room",
                speaker_mode=SpeakerMode.MENTION_FAN_OUT_VISIBLE,
                visible_participants=["ceo-visible-room", "dashboard-mirror", "quality-lead"],
                turn_taking_rule="mentioned_review_agents_reply_and_keep_transcript_visible",
                escalation_rule="override_and_rollback_return_to_dashboard",
            )
        )

        self._channel_bindings.save(
            ChannelBinding(
                binding_id="channel-dashboard",
                surface=ConversationSurface.DASHBOARD,
                provider="internal",
                default_route="chief_of_staff_intake",
                mention_policy="n/a",
                sync_back_policy="memory_and_taskgraph",
            )
        )
        self._channel_bindings.save(
            ChannelBinding(
                binding_id="channel-feishu-dm",
                surface=ConversationSurface.FEISHU_DM,
                provider="feishu",
                default_route="direct_department_with_chief_of_staff_sync_back",
                mention_policy="direct_message_single_bot",
                sync_back_policy="executive_summary_only",
            )
        )
        self._channel_bindings.save(
            ChannelBinding(
                binding_id="channel-feishu-group",
                surface=ConversationSurface.FEISHU_GROUP,
                provider="feishu",
                default_route="mention_based_visible_room_fan_out",
                mention_policy="mentioned_departments_only",
                sync_back_policy="memory_and_taskgraph_with_visible_transcript",
                room_policy_ref=project_room.room_policy_id,
            )
        )

    def _ensure_room_policy(self, default_policy: RoomPolicy) -> RoomPolicy:
        existing = next(
            (policy for policy in self._room_policies.list() if policy.room_policy_id == default_policy.room_policy_id),
            None,
        )
        if existing is not None:
            return existing
        return self._room_policies.save(default_policy)

    def _sync_bot_bindings(self) -> None:
        department_to_employee = {department.default_employee: department.department_name for department in get_departments()}
        configured_apps = {config.employee_id: config for config in get_feishu_bot_app_configs()}
        for employee in get_employees():
            if employee.department not in CORE_FEISHU_DEPARTMENTS:
                continue
            configured = configured_apps.get(employee.employee_id)
            self._bot_bindings.save(
                BotSeatBinding(
                    binding_id=f"bot-{employee.employee_id}",
                    department=department_to_employee.get(employee.employee_id, employee.department),
                    virtual_employee=employee.employee_id,
                    feishu_app_id=(configured.app_id if configured else f"app-{employee.employee_id}"),
                    feishu_bot_identity=(
                        configured.bot_identity if configured and configured.bot_identity else f"feishu-{employee.employee_id}"
                    ),
                )
            )


_conversation_service = ConversationService(
    thread_store=build_model_store(ConversationThread, "thread_id", "conversation_threads"),
    channel_binding_store=build_model_store(ChannelBinding, "binding_id", "channel_bindings"),
    bot_binding_store=build_model_store(BotSeatBinding, "binding_id", "bot_seat_bindings"),
    room_policy_store=build_model_store(RoomPolicy, "room_policy_id", "room_policies"),
)


def get_conversation_service() -> ConversationService:
    return _conversation_service
