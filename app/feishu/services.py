from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from app.artifacts.services import get_artifact_store_service
from app.company.bootstrap import get_employees
from app.company.models import TriggerType
from app.control_plane.models import RunEvent
from app.control_plane.services import get_control_plane_service
from app.conversation.models import ConversationIntakeRequest, ConversationSurface, PendingHandoffState
from app.conversation.services import ConversationService, get_conversation_service
from app.core.config import get_settings
from app.executive_office.models import CEOCommand
from app.feishu.config import (
    get_feishu_bot_app_config_by_app_id,
    get_feishu_bot_app_config_by_employee_id,
    get_feishu_bot_app_configs,
)
from app.feishu.models import (
    FeishuBotAppConfig,
    FeishuInboundEventRecord,
    FeishuGroupDebugEventRecord,
    FeishuBotAppView,
    FeishuDeadLetterDetailView,
    FeishuMentionDispatchResult,
    FeishuOutboundMessageRecord,
    FeishuReplayAuditEntryView,
    FeishuReplayMessageResult,
    FeishuSendMessageRequest,
    FeishuSendMessageResult,
    FeishuWebhookResult,
)
from app.openclaw.models import OpenClawChatResult, OpenClawCollaborationContext, OpenClawHandoffContext
from app.openclaw.services import get_openclaw_dialogue_service
from app.persona.services import get_employee_pack_compiler
from app.store import ModelStore, build_model_store


@dataclass
class CachedToken:
    value: str
    expires_at: float


@dataclass(frozen=True)
class MentionMatchResult:
    matched: bool
    basis: str | None = None


ROLE_ALIAS_OVERRIDES: dict[str, tuple[str, ...]] = {
    "chief-of-staff": ("chief of staff",),
    "product-lead": ("product lead",),
    "research-lead": ("research lead",),
    "delivery-lead": ("project lead", "delivery lead"),
    "design-lead": ("design lead",),
    "engineering-lead": ("engineering lead",),
    "quality-lead": ("quality lead",),
}

HANDOFF_CONTRACT_VIOLATION_MARKERS: tuple[str, ...] = (
    "手动 @",
    "手动@",
    "当前系统配置限制",
    "无法直接通过工具向",
    "不能跨 agent",
    "需要通过 feishu 群聊来 @",
)

GENERIC_HANDOFF_REPLY_MARKERS: tuple[str, ...] = (
    "通知下一个bot",
    "通知下一个 bot",
    "下一个bot",
    "下一个 bot",
    "下一个接棒",
    "下一位接棒",
    "下一位回复",
    "继续接棒",
    "继续回复",
    "接力",
)

MULTI_TURN_COLLABORATION_HINTS: tuple[str, ...] = (
    "接棒",
    "继续",
    "继续回复",
    "继续补充",
    "然后请",
    "再请",
    "让",
    "并请",
    "通知",
    "轮流",
    "依次",
    "协作",
    "一起",
    "报数",
)

USER_REPEAT_CURRENT_BOT_MARKERS: tuple[str, ...] = (
    "最后请你",
    "最后由你",
    "最后你来",
    "请你再",
    "你再",
    "再次回复",
    "再回复",
    "再总结",
    "再次总结",
    "最后总结",
    "最后再总结",
)


class FeishuSurfaceAdapterService:
    def __init__(
        self,
        inbound_store: ModelStore[FeishuInboundEventRecord],
        group_debug_store: ModelStore[FeishuGroupDebugEventRecord],
        outbound_store: ModelStore[FeishuOutboundMessageRecord],
        conversation_service: ConversationService,
    ) -> None:
        self._inbound = inbound_store
        self._group_debug = group_debug_store
        self._outbound = outbound_store
        self._conversation = conversation_service
        self._token_cache: dict[str, CachedToken] = {}

    def handle_callback(self, raw_body: bytes, headers: dict[str, str]) -> FeishuWebhookResult:
        payload = json.loads(raw_body.decode("utf-8"))
        self._verify_plain_callback_token(payload)
        return self.handle_payload(payload)

    def handle_payload(self, payload: dict[str, Any]) -> FeishuWebhookResult:
        if payload.get("encrypt"):
            raise ValueError("Encrypted Feishu callbacks are not supported in V1 yet. Leave Encrypt Key empty.")

        if payload.get("type") == "url_verification":
            return FeishuWebhookResult(status="challenge", challenge=payload.get("challenge"))

        header = payload.get("header", {})
        event_type = header.get("event_type")
        if event_type != "im.message.receive_v1":
            return FeishuWebhookResult(status="ignored", detail=f"Unsupported event type: {event_type or 'unknown'}")

        app_id = header.get("app_id")
        if not app_id:
            raise ValueError("Missing Feishu app_id in callback header.")

        binding = self._conversation.get_bot_binding_by_app_id(app_id)
        if binding is None:
            app_config = get_feishu_bot_app_config_by_app_id(app_id)
            if app_config is not None:
                binding = self._conversation.get_bot_binding_by_employee_id(app_config.employee_id)
        if binding is None:
            raise ValueError(f"No BotSeatBinding configured for Feishu app_id: {app_id}")

        event = payload.get("event", {})
        message = event.get("message", {})
        message_id = message.get("message_id")
        if not message_id:
            raise ValueError("Missing Feishu message_id in callback payload.")
        record_id = self._record_id(app_id, message_id)

        existing = self._inbound.get(record_id)
        if existing is not None:
            if self._surface_for_chat_type(message.get("chat_type")) == ConversationSurface.FEISHU_GROUP:
                self._record_group_debug_event(
                    app_id=app_id,
                    header=header,
                    event=event,
                    message_id=message_id,
                    surface=ConversationSurface.FEISHU_GROUP,
                    dispatch_mode=existing.dispatch_mode,
                    processed_status="duplicate",
                    target_agent_ids=existing.target_agent_ids,
                    raw_mentions_summary=existing.raw_mentions_summary,
                    detail="Duplicate message_id ignored.",
                )
            return FeishuWebhookResult(
                status="duplicate",
                app_id=existing.app_id,
                surface=existing.surface,
                message_id=existing.message_id,
                thread_id=existing.thread_ref,
                work_ticket_id=existing.work_ticket_ref,
                runtrace_id=existing.runtrace_ref,
                detail="Duplicate message_id ignored.",
            )

        if message.get("message_type") != "text":
            if self._surface_for_chat_type(message.get("chat_type")) == ConversationSurface.FEISHU_GROUP:
                self._record_group_debug_event(
                    app_id=app_id,
                    header=header,
                    event=event,
                    message_id=message_id,
                    surface=ConversationSurface.FEISHU_GROUP,
                    dispatch_mode="unsupported_message_type",
                    processed_status="ignored_unsupported",
                    detail=f"Unsupported message_type: {message.get('message_type') or 'unknown'}",
                )
            return FeishuWebhookResult(
                status="ignored",
                app_id=app_id,
                detail=f"Unsupported message_type: {message.get('message_type') or 'unknown'}",
            )

        intent = self._extract_text_intent(message.get("content", ""))
        if not intent:
            if self._surface_for_chat_type(message.get("chat_type")) == ConversationSurface.FEISHU_GROUP:
                self._record_group_debug_event(
                    app_id=app_id,
                    header=header,
                    event=event,
                    message_id=message_id,
                    surface=ConversationSurface.FEISHU_GROUP,
                    dispatch_mode="empty_group_text",
                    processed_status="ignored_empty",
                    detail="Text message content was empty.",
                )
            return FeishuWebhookResult(status="ignored", app_id=app_id, detail="Text message content was empty.")

        surface = self._surface_for_chat_type(message.get("chat_type"))
        chat_id = message.get("chat_id")
        if not chat_id:
            raise ValueError("Missing Feishu chat_id in callback payload.")
        raw_mentions_summary = self._summarize_mentions(self._message_mentions(event))

        command_mode = self._parse_control_command(intent)
        if command_mode == "new_only":
            return self._handle_new_conversation_marker(
                app_id=app_id,
                event=event,
                surface=surface,
                chat_id=chat_id,
                binding=binding,
            )
        force_new_conversation = command_mode == "new_with_message"
        normalized_intent = self._strip_new_command_prefix(intent) if force_new_conversation else intent

        channel_id = self._channel_id_for(surface, chat_id)
        existing_thread = None
        if not force_new_conversation:
            existing_thread = self._conversation.find_thread_by_surface_channel(surface, channel_id)
        prior_active_runtrace_ref = (
            (existing_thread.active_runtrace_ref or existing_thread.runtrace_ref) if existing_thread else None
        )
        prior_work_ticket_ref = existing_thread.work_ticket_ref if existing_thread else None
        prior_delivery_guard_epoch = existing_thread.delivery_guard_epoch if existing_thread else 0
        pending_handoff_dispatch_targets = self._pending_handoff_dispatch_targets(existing_thread)

        mentioned_agent_ids = [binding.virtual_employee] if surface != ConversationSurface.FEISHU_GROUP else []
        dispatch_target_ids = list(mentioned_agent_ids)
        dispatch_resolution_basis = "direct_bot_app" if surface != ConversationSurface.FEISHU_GROUP else "explicit_mentions_only"
        match_basis: str | None = "direct_bot_app" if surface != ConversationSurface.FEISHU_GROUP else None
        deterministic_text_target_ids: list[str] = []
        deterministic_name_target_ids: list[str] = []
        semantic_handoff_target_ids: list[str] = []
        semantic_dispatch_target_ids: list[str] = []
        semantic_handoff_candidates: list[dict[str, Any]] = []
        collaboration_intent: str | None = None
        user_repeat_allowed_ids: list[str] = []
        target_resolution_basis = "explicit_mentions_only"
        if surface == ConversationSurface.FEISHU_GROUP:
            group_match = self._group_match_result(event, binding.virtual_employee)
            mentioned_agent_ids = self._resolve_target_agents(event)
            deterministic_name_target_ids = self._resolve_deterministic_name_targets(normalized_intent)
            if self._should_infer_semantic_dispatch(
                normalized_intent,
                deterministic_name_target_ids,
                mentioned_agent_ids,
            ):
                semantic_dispatch_target_ids, semantic_handoff_candidates = self._infer_semantic_target_ids(
                    receiving_employee_id=binding.virtual_employee,
                    user_message=normalized_intent,
                    channel_id=channel_id,
                    surface=surface,
                    chat_id=chat_id,
                    current_app_id=app_id,
                    candidate_employee_ids=[
                        seat_binding.virtual_employee
                        for seat_binding in self._conversation.list_bot_seat_bindings()
                    ],
                    allow_current_employee=True,
                )
            dispatch_target_ids = list(
                dict.fromkeys(
                    [
                        *mentioned_agent_ids,
                        *deterministic_name_target_ids,
                        *pending_handoff_dispatch_targets,
                        *semantic_dispatch_target_ids,
                    ]
                )
            )
            dispatch_target_ids = self._ordered_group_dispatch_targets(
                current_employee_id=binding.virtual_employee,
                dispatch_target_ids=dispatch_target_ids,
                pending_handoff=existing_thread.pending_handoff if existing_thread else None,
                interruption_mode=bool(prior_active_runtrace_ref),
            )
            deterministic_text_target_ids = [
                target_employee_id
                for target_employee_id in deterministic_name_target_ids
                if target_employee_id != binding.virtual_employee
            ]
            semantic_handoff_target_ids = [
                target_employee_id
                for target_employee_id in semantic_dispatch_target_ids
                if target_employee_id != binding.virtual_employee
            ]
            target_resolution_basis = self._target_resolution_basis(
                deterministic_text_target_ids,
                semantic_handoff_target_ids,
            )
            dispatch_resolution_basis = self._dispatch_resolution_basis(
                mentioned_agent_ids,
                deterministic_name_target_ids,
                semantic_dispatch_target_ids,
            )
            collaboration_intent = self._collaboration_intent(
                user_message=normalized_intent,
                dispatch_target_ids=dispatch_target_ids,
                candidate_handoff_target_ids=[
                    *deterministic_text_target_ids,
                    *semantic_handoff_target_ids,
                ],
            )
            user_repeat_allowed_ids = self._user_repeat_allowed_targets(
                user_message=normalized_intent,
                current_employee_id=binding.virtual_employee,
                dispatch_target_ids=dispatch_target_ids,
                channel_id=channel_id,
                surface=surface,
                chat_id=chat_id,
                current_app_id=app_id,
            )
            match_basis = self._group_dispatch_match_basis(
                employee_id=binding.virtual_employee,
                explicit_target_ids=mentioned_agent_ids,
                explicit_match_basis=group_match.basis,
                deterministic_name_target_ids=deterministic_name_target_ids,
                semantic_dispatch_target_ids=semantic_dispatch_target_ids,
            )
            if binding.virtual_employee not in dispatch_target_ids:
                self._record_group_debug_event(
                    app_id=app_id,
                    header=header,
                    event=event,
                    message_id=message_id,
                    surface=surface,
                    dispatch_mode="non_targeted_group_message",
                    processed_status="ignored_non_targeted",
                    dispatch_targets=dispatch_target_ids,
                    dispatch_resolution_basis=dispatch_resolution_basis,
                    collaboration_intent=collaboration_intent,
                    matched_employee_id=binding.virtual_employee,
                    match_basis=match_basis,
                    raw_mentions_summary=raw_mentions_summary,
                    deterministic_name_target_ids=deterministic_name_target_ids,
                    semantic_dispatch_target_ids=semantic_dispatch_target_ids,
                    deterministic_text_target_ids=deterministic_text_target_ids,
                    semantic_handoff_target_ids=semantic_handoff_target_ids,
                    semantic_handoff_candidates=semantic_handoff_candidates,
                    target_resolution_basis=target_resolution_basis,
                    detail=f"Group message did not target {binding.virtual_employee}.",
                )
                return FeishuWebhookResult(
                    status="ignored",
                    app_id=app_id,
                    surface=surface,
                    message_id=message_id,
                    target_agent_ids=[],
                    dispatch_mode="non_targeted_group_message",
                    detail=f"Group message did not target {binding.virtual_employee}.",
                )
        dispatch_result = FeishuMentionDispatchResult(
            app_id=app_id,
            chat_id=chat_id,
            message_id=message_id,
            target_agent_ids=dispatch_target_ids,
            dispatch_mode="multi_agent_fan_out" if len(dispatch_target_ids) > 1 else "single_agent",
        )
        forced_handoff_targets = list(
            dict.fromkeys(
                [
                    *deterministic_text_target_ids,
                    *semantic_handoff_target_ids,
                    *(
                        [
                            employee_id
                            for employee_id in pending_handoff_dispatch_targets
                            if employee_id != binding.virtual_employee
                        ]
                        if surface == ConversationSurface.FEISHU_GROUP
                        else []
                    ),
                ]
            )
        )
        participant_ids = self._build_participants(event, binding.virtual_employee, dispatch_target_ids)
        activation_hint_targets = list(
            dict.fromkeys(
                [
                    *dispatch_target_ids,
                    *deterministic_text_target_ids,
                    *semantic_handoff_target_ids,
                ]
            )
        )
        intake_request = ConversationIntakeRequest(
            command=CEOCommand(
                intent=normalized_intent,
                trigger_type=TriggerType.EVENT_BASED,
                entry_channel=channel_id,
                surface=surface.value,
                activation_hint=self._department_hints_for_employee_ids(activation_hint_targets),
            ),
            surface=surface,
            channel_id=channel_id,
            initiator_id=self._resolve_initiator(event),
            participant_ids=participant_ids,
            bound_agent_ids=dispatch_target_ids,
            title=normalized_intent[:80],
            thread_id=existing_thread.thread_id if existing_thread else None,
        )
        intake_result = self._conversation.intake(intake_request)

        run_trace = get_control_plane_service().append_run_trace_event(
            intake_result.command_result.run_trace.runtrace_id,
            RunEvent(
                event_type="feishu_event_received",
                message="Feishu callback routed into conversation intake.",
                metadata={
                    "app_id": app_id,
                    "message_id": message_id,
                    "surface": surface.value,
                    "channel_id": channel_id,
                    "dispatch_mode": dispatch_result.dispatch_mode,
                    "dispatch_targets": ",".join(dispatch_result.target_agent_ids),
                },
            ),
        )
        run_trace = get_control_plane_service().set_run_trace_dispatch_targets(
            run_trace.runtrace_id,
            dispatch_result.target_agent_ids,
        )
        run_trace = get_control_plane_service().set_run_trace_collaboration_intent(
            run_trace.runtrace_id,
            collaboration_intent,
        )
        delivery_guard_epoch = prior_delivery_guard_epoch + 1 if surface == ConversationSurface.FEISHU_GROUP else 0
        if surface == ConversationSurface.FEISHU_GROUP:
            run_trace = get_control_plane_service().set_run_trace_delivery_guard_epoch(
                run_trace.runtrace_id,
                delivery_guard_epoch,
            )
            run_trace = get_control_plane_service().set_run_trace_interruption_dispatch_targets(
                run_trace.runtrace_id,
                dispatch_result.target_agent_ids,
            )
            if prior_active_runtrace_ref and prior_active_runtrace_ref != run_trace.runtrace_id:
                get_control_plane_service().append_run_trace_event(
                    run_trace.runtrace_id,
                    RunEvent(
                        event_type="run_supersede_requested",
                        message="A newer group message is taking over the active visible run on this thread.",
                        metadata={
                            "thread_id": intake_result.thread.thread_id,
                            "prior_runtrace_id": prior_active_runtrace_ref,
                            "new_runtrace_id": run_trace.runtrace_id,
                            "message_id": message_id,
                        },
                    ),
                )
                get_control_plane_service().mark_run_trace_superseded(
                    prior_active_runtrace_ref,
                    successor_runtrace_id=run_trace.runtrace_id,
                    reason="user_interruption",
                )
                run_trace = get_control_plane_service().set_run_trace_supersedes_runtrace_ref(
                    run_trace.runtrace_id,
                    prior_active_runtrace_ref,
                )
                run_trace = get_control_plane_service().set_run_trace_interruption_reason(
                    run_trace.runtrace_id,
                    "user_interruption",
                )
                get_control_plane_service().set_work_ticket_supersede_refs(
                    intake_result.command_result.work_ticket.ticket_id,
                    [
                        f"runtrace:{prior_active_runtrace_ref}",
                        *([f"ticket:{prior_work_ticket_ref}"] if prior_work_ticket_ref else []),
                    ],
                )
            self._conversation.set_active_runtrace(
                intake_result.thread.thread_id,
                runtrace_id=run_trace.runtrace_id,
                delivery_guard_epoch=delivery_guard_epoch,
                superseded_runtrace_ref=(
                    prior_active_runtrace_ref
                    if prior_active_runtrace_ref and prior_active_runtrace_ref != run_trace.runtrace_id
                    else None
                ),
            )
            get_control_plane_service().append_run_trace_event(
                run_trace.runtrace_id,
                RunEvent(
                    event_type="thread_active_run_switched",
                    message="Thread active visible run switched to the latest group run.",
                    metadata={
                        "thread_id": intake_result.thread.thread_id,
                        "prior_runtrace_id": prior_active_runtrace_ref or "",
                        "new_runtrace_id": run_trace.runtrace_id,
                        "delivery_guard_epoch": str(delivery_guard_epoch),
                    },
                ),
            )
            get_control_plane_service().append_run_trace_event(
                run_trace.runtrace_id,
                RunEvent(
                    event_type="interruption_dispatch_resolved",
                    message="Dispatch targets resolved for the latest user interruption on this group thread.",
                    metadata={
                        "thread_id": intake_result.thread.thread_id,
                        "runtrace_id": run_trace.runtrace_id,
                        "targets": ",".join(dispatch_result.target_agent_ids),
                        "resolution_basis": dispatch_resolution_basis or "",
                    },
                ),
            )

        inbound_record = self._inbound.save(
            FeishuInboundEventRecord(
                record_id=record_id,
                message_id=message_id,
                event_id=header.get("event_id"),
                app_id=app_id,
                surface=surface,
                chat_id=chat_id,
                thread_ref=intake_result.thread.thread_id,
                work_ticket_ref=intake_result.command_result.work_ticket.ticket_id,
                runtrace_ref=run_trace.runtrace_id,
                sender_id=self._sender_raw_id(event),
                text=normalized_intent,
                dispatch_mode=dispatch_result.dispatch_mode,
                dispatch_targets=dispatch_target_ids,
                dispatch_resolution_basis=dispatch_resolution_basis,
                collaboration_intent=collaboration_intent,
                target_agent_ids=dispatch_result.target_agent_ids,
                deterministic_name_target_ids=deterministic_name_target_ids,
                semantic_dispatch_target_ids=semantic_dispatch_target_ids,
                deterministic_text_target_ids=deterministic_text_target_ids,
                semantic_handoff_target_ids=semantic_handoff_target_ids,
                forced_handoff_targets=forced_handoff_targets,
                supersedes_runtrace_ref=(
                    prior_active_runtrace_ref
                    if surface == ConversationSurface.FEISHU_GROUP and prior_active_runtrace_ref != run_trace.runtrace_id
                    else None
                ),
                active_thread_runtrace_ref=run_trace.runtrace_id if surface == ConversationSurface.FEISHU_GROUP else None,
                interruption_dispatch_targets=dispatch_result.target_agent_ids if surface == ConversationSurface.FEISHU_GROUP else [],
                delivery_guard_epoch=delivery_guard_epoch if surface == ConversationSurface.FEISHU_GROUP else None,
                raw_mentions_summary=raw_mentions_summary,
            )
        )
        if surface == ConversationSurface.FEISHU_GROUP:
            self._record_group_debug_event(
                app_id=app_id,
                header=header,
                event=event,
                message_id=message_id,
                surface=surface,
                dispatch_mode=dispatch_result.dispatch_mode,
                processed_status="processed",
                dispatch_targets=dispatch_target_ids,
                dispatch_resolution_basis=dispatch_resolution_basis,
                collaboration_intent=collaboration_intent,
                target_agent_ids=dispatch_result.target_agent_ids,
                matched_employee_id=binding.virtual_employee,
                match_basis=match_basis,
                raw_mentions_summary=raw_mentions_summary,
                deterministic_name_target_ids=deterministic_name_target_ids,
                semantic_dispatch_target_ids=semantic_dispatch_target_ids,
                deterministic_text_target_ids=deterministic_text_target_ids,
                semantic_handoff_target_ids=semantic_handoff_target_ids,
                semantic_handoff_candidates=semantic_handoff_candidates,
                target_resolution_basis=target_resolution_basis,
                detail=f"thread={inbound_record.thread_ref}",
            )

        reply_count = 0
        reply_errors: list[str] = []
        if get_feishu_bot_app_config_by_app_id(app_id) is not None:
            dialogue_service = get_openclaw_dialogue_service()
            available_bot_ids = self._group_available_bot_ids() if surface == ConversationSurface.FEISHU_GROUP else [binding.virtual_employee]
            thread_state = self._conversation.get_required_thread(intake_result.thread.thread_id)
            interruption_reason = (
                "user_interruption"
                if surface == ConversationSurface.FEISHU_GROUP
                and prior_active_runtrace_ref
                and prior_active_runtrace_ref != run_trace.runtrace_id
                else None
            )
            dispatch_reason = self._dispatch_reason(
                dispatch_resolution_basis=dispatch_resolution_basis,
                used_pending_handoff=bool(pending_handoff_dispatch_targets),
                interruption_reason=interruption_reason,
            )
            defer_source_turn = (
                surface == ConversationSurface.FEISHU_GROUP
                and interruption_reason == "user_interruption"
                and bool(dispatch_target_ids)
                and dispatch_target_ids[0] != binding.virtual_employee
            )
            source_visible_turn_count = (
                0 if defer_source_turn else 1 if surface == ConversationSurface.FEISHU_GROUP else 0
            )
            initial_spoken_bot_ids = [] if defer_source_turn else [binding.virtual_employee]
            scheduled_turn_targets = dispatch_target_ids[1:] if defer_source_turn else []
            collaboration_context = self._build_collaboration_context(
                collaboration_intent=collaboration_intent,
                dispatch_targets=dispatch_target_ids,
                candidate_handoff_targets=forced_handoff_targets,
                spoken_bot_ids=initial_spoken_bot_ids,
                available_bot_ids=available_bot_ids,
                visible_turn_count=source_visible_turn_count,
                dispatch_reason=dispatch_reason,
                last_committed_state=thread_state.last_committed_state,
                pending_handoff=thread_state.pending_handoff,
                interruption_mode=interruption_reason,
            )
            final_handoff_targets: list[str] = []
            reply_visible_named_targets: list[str] = []
            reply_semantic_handoff_targets: list[str] = []
            handoff_resolution_basis: str | None = None
            handoff_name_contract_violation = False
            handoff_origin: str | None = None
            source_reply_text_for_handoff = ""
            source_handoff_reason: str | None = None
            source_structured_handoff_targets: list[str] = []
            if defer_source_turn:
                source_handoff_reason = (
                    (
                        thread_state.pending_handoff.reason
                        or thread_state.pending_handoff.instruction
                    )
                    if thread_state.pending_handoff is not None
                    else "回应用户插话并继续当前接棒"
                )
                final_handoff_targets = dispatch_target_ids[:1]
                handoff_resolution_basis = dispatch_resolution_basis or "interruption_schedule"
                handoff_origin = "interruption_schedule"
                get_control_plane_service().append_run_trace_event(
                    run_trace.runtrace_id,
                    RunEvent(
                        event_type="source_turn_deferred",
                        message=f"{binding.virtual_employee} deferred the source turn to the interruption correction target.",
                        metadata={
                            "employee_id": binding.virtual_employee,
                            "deferred_target": final_handoff_targets[0] if final_handoff_targets else "",
                            "dispatch_targets": ",".join(dispatch_target_ids),
                        },
                    ),
                )
                get_control_plane_service().set_run_trace_handoff_chain_state(
                    run_trace.runtrace_id,
                    spoken_bot_ids=[],
                    remaining_bot_ids=collaboration_context.remaining_bot_ids,
                    remaining_turn_budget=collaboration_context.remaining_turn_budget,
                    stop_reason=None,
                )
                get_control_plane_service().set_run_trace_visible_turn_count(
                    run_trace.runtrace_id,
                    source_visible_turn_count,
                )
            else:
                dialogue_result = dialogue_service.generate_reply(
                    employee_id=binding.virtual_employee,
                    user_message=normalized_intent,
                    work_ticket=intake_result.command_result.work_ticket,
                    channel_id=channel_id,
                    surface=surface.value,
                    app_id=app_id,
                    visible_participants=intake_result.thread.participant_ids,
                    conversation_history=self._build_thread_history(
                        thread_ref=intake_result.thread.thread_id,
                        current_app_id=app_id,
                    ),
                    forced_handoff_targets=forced_handoff_targets,
                    collaboration_context=collaboration_context,
                )
                run_trace = get_control_plane_service().append_run_trace_event(
                    run_trace.runtrace_id,
                    RunEvent(
                        event_type="agent_dialogue_generated",
                        message=f"{binding.virtual_employee} generated a Feishu reply.",
                        metadata={
                            "strategy": dialogue_result.strategy,
                            "model_ref": dialogue_result.model_ref,
                            "turn_mode": "source",
                            "employee_id": binding.virtual_employee,
                            "error_detail": dialogue_result.error_detail or "",
                        },
                    ),
                )
                reply_text = dialogue_result.reply_text
                follow_up_texts = list(dialogue_result.follow_up_texts)
                handoff_contract_violation = self._is_handoff_contract_violation(
                    reply_text,
                    forced_handoff_targets,
                )
                if handoff_contract_violation:
                    get_control_plane_service().flag_run_trace_handoff_contract_violation(run_trace.runtrace_id)
                    run_trace = get_control_plane_service().append_run_trace_event(
                        run_trace.runtrace_id,
                        RunEvent(
                            event_type="handoff_contract_violation",
                            message="Agent reply requested collaboration with a prohibited fallback phrase.",
                            metadata={
                                "employee_id": binding.virtual_employee,
                                "forced_handoff_targets": ",".join(forced_handoff_targets),
                            },
                        ),
                    )
                if intake_result.thread.thread_id:
                    self._conversation.attach_openclaw_session(
                        intake_result.thread.thread_id,
                        binding.virtual_employee,
                        dialogue_result.session_key or f"agent:{binding.virtual_employee}:{surface.value}:{chat_id}",
                    )

                (
                    dialogue_result,
                    final_handoff_targets,
                    reply_visible_named_targets,
                    reply_semantic_handoff_targets,
                    handoff_resolution_basis,
                    handoff_name_contract_violation,
                ) = self._resolve_dialogue_handoff_targets(
                    dialogue_service=dialogue_service,
                    current_employee_id=binding.virtual_employee,
                    dialogue_result=dialogue_result,
                    work_ticket_ref=intake_result.command_result.work_ticket.ticket_id,
                    user_message=normalized_intent,
                    forced_handoff_targets=forced_handoff_targets,
                    channel_id=channel_id,
                    surface=surface,
                    chat_id=chat_id,
                    current_app_id=app_id,
                    visible_participants=intake_result.thread.participant_ids,
                    conversation_history=self._build_thread_history(
                        thread_ref=intake_result.thread.thread_id,
                        current_app_id=app_id,
                    ),
                    collaboration_context=collaboration_context,
                    turn_mode="source",
                )
                if handoff_name_contract_violation:
                    get_control_plane_service().flag_run_trace_handoff_contract_violation(run_trace.runtrace_id)
                    run_trace = get_control_plane_service().append_run_trace_event(
                        run_trace.runtrace_id,
                        RunEvent(
                            event_type="handoff_contract_violation",
                            message="Agent reply requested another bot but did not name it in visible text.",
                            metadata={
                                "employee_id": binding.virtual_employee,
                                "resolved_handoff_targets": ",".join(final_handoff_targets),
                            },
                        ),
                    )
                follow_up_texts = list(dialogue_result.follow_up_texts)
                handoff_origin = self._handoff_origin(
                    deterministic_text_target_ids=deterministic_text_target_ids,
                    semantic_handoff_target_ids=semantic_handoff_target_ids,
                    model_handoff_targets=dialogue_result.handoff_targets,
                )
                if handoff_origin:
                    get_control_plane_service().set_run_trace_handoff_origin(run_trace.runtrace_id, handoff_origin)
                if handoff_resolution_basis:
                    get_control_plane_service().set_run_trace_handoff_resolution_basis(
                        run_trace.runtrace_id,
                        handoff_resolution_basis,
                    )
                get_control_plane_service().set_run_trace_reply_visible_named_targets(
                    run_trace.runtrace_id,
                    reply_visible_named_targets,
                )
                get_control_plane_service().set_run_trace_handoff_chain_state(
                    run_trace.runtrace_id,
                    spoken_bot_ids=[binding.virtual_employee],
                    remaining_bot_ids=collaboration_context.remaining_bot_ids,
                    remaining_turn_budget=collaboration_context.remaining_turn_budget,
                    stop_reason=(
                        "handoff_contract_violation"
                        if handoff_name_contract_violation
                        else None
                    ),
                )
                get_control_plane_service().set_run_trace_visible_turn_count(
                    run_trace.runtrace_id,
                    source_visible_turn_count,
                )
                self._update_thread_turn_state(
                    thread_id=intake_result.thread.thread_id,
                    speaker_id=binding.virtual_employee,
                    reply_text=dialogue_result.reply_text,
                    handoff_targets=final_handoff_targets,
                    handoff_reason=dialogue_result.handoff_reason,
                    runtrace_ref=run_trace.runtrace_id,
                )
                reply_specs = [("auto_reply", dialogue_result.reply_text), *[("auto_follow_up", text) for text in follow_up_texts]]
                streamed_specs = self._expand_visible_reply_specs(reply_specs)
                for index, (source_kind, reply_text) in enumerate(streamed_specs, start=1):
                    try:
                        send_result = self.send_text_message(
                            FeishuSendMessageRequest(
                                app_id=app_id,
                                chat_id=chat_id,
                                text=reply_text,
                                work_ticket_ref=intake_result.command_result.work_ticket.ticket_id,
                                thread_ref=intake_result.thread.thread_id,
                                runtrace_ref=run_trace.runtrace_id,
                                delivery_guard_epoch=delivery_guard_epoch if surface == ConversationSurface.FEISHU_GROUP else None,
                                source_kind=source_kind,
                                idempotency_key=self._auto_reply_idempotency_key(
                                    app_id=app_id,
                                    message_id=message_id,
                                    source_kind=source_kind,
                                    ordinal=index,
                                    text=reply_text,
                                ),
                            )
                        )
                        self._sleep_between_stream_chunks(index, len(streamed_specs))
                        if send_result.status in {"sent", "deduplicated"}:
                            reply_count += 1
                        else:
                            reply_errors.append(send_result.error_detail or f"{source_kind} failed")
                            break
                    except ValueError as exc:
                        reply_errors.append(str(exc))
                        break

                source_reply_text_for_handoff = dialogue_result.reply_text
                source_handoff_reason = dialogue_result.handoff_reason
                source_structured_handoff_targets = list(dialogue_result.handoff_targets)

            if surface == ConversationSurface.FEISHU_GROUP and final_handoff_targets:
                handoff_result = self._orchestrate_visible_handoffs(
                    source_employee_id=binding.virtual_employee,
                    handoff_targets=final_handoff_targets,
                    handoff_reason=source_handoff_reason,
                    handoff_origin=handoff_origin,
                    handoff_resolution_basis=handoff_resolution_basis,
                    structured_handoff_targets=source_structured_handoff_targets,
                    reply_visible_named_targets=reply_visible_named_targets,
                    reply_semantic_handoff_targets=reply_semantic_handoff_targets,
                    scheduled_turn_targets=scheduled_turn_targets,
                    app_id=app_id,
                    chat_id=chat_id,
                    surface=surface,
                    channel_id=channel_id,
                    user_message=normalized_intent,
                    source_reply_text=source_reply_text_for_handoff,
                    event=event,
                    intake_result_thread_id=intake_result.thread.thread_id,
                    work_ticket_ref=intake_result.command_result.work_ticket.ticket_id,
                    runtrace_ref=run_trace.runtrace_id,
                    already_targeted_agent_ids=mentioned_agent_ids,
                    visible_participants=intake_result.thread.participant_ids,
                    collaboration_intent=collaboration_intent,
                    initial_spoken_bot_ids=initial_spoken_bot_ids,
                    available_bot_ids=available_bot_ids,
                    user_repeat_allowed_ids=user_repeat_allowed_ids,
                    initial_visible_turn_count=source_visible_turn_count,
                    delivery_guard_epoch=delivery_guard_epoch if surface == ConversationSurface.FEISHU_GROUP else None,
                    interruption_reason=interruption_reason,
                    dispatch_reason=dispatch_reason,
                )
                reply_count += handoff_result["reply_count"]
                reply_errors.extend(handoff_result["reply_errors"])
            elif surface == ConversationSurface.FEISHU_GROUP and not final_handoff_targets:
                get_control_plane_service().set_run_trace_handoff_chain_state(
                    run_trace.runtrace_id,
                    spoken_bot_ids=initial_spoken_bot_ids,
                    remaining_bot_ids=collaboration_context.remaining_bot_ids,
                    remaining_turn_budget=collaboration_context.remaining_turn_budget,
                    stop_reason=(
                        "handoff_contract_violation"
                        if handoff_name_contract_violation
                        else "no_resolved_next_hop"
                        if collaboration_intent == "multi_turn_collaboration"
                        else None
                    ),
                )

        return FeishuWebhookResult(
            status="processed",
            app_id=app_id,
            surface=surface,
            message_id=message_id,
            thread_id=intake_result.thread.thread_id,
            work_ticket_id=intake_result.command_result.work_ticket.ticket_id,
            runtrace_id=run_trace.runtrace_id,
            reply_sent=reply_count > 0,
            reply_count=reply_count,
            target_agent_ids=dispatch_result.target_agent_ids,
            dispatch_mode=dispatch_result.dispatch_mode,
            detail=" | ".join(reply_errors) if reply_errors else None,
        )

    def send_text_message(self, request: FeishuSendMessageRequest) -> FeishuSendMessageResult:
        app_config = get_feishu_bot_app_config_by_app_id(request.app_id)
        if app_config is None:
            raise ValueError(f"Unknown Feishu app_id: {request.app_id}")
        if not app_config.app_secret:
            raise ValueError(f"Missing Feishu app_secret for app_id: {request.app_id}")

        stale_drop_reason = self._delivery_guard_drop_reason(request)
        if stale_drop_reason is not None:
            dropped_record = self._outbound.save(
                FeishuOutboundMessageRecord(
                    outbound_id=f"fo-{uuid4().hex[:8]}",
                    app_id=request.app_id,
                    receive_id_type=request.receive_id_type,
                    receive_id=request.chat_id,
                    message_id=None,
                    text=request.text,
                    mention_employee_ids=request.mention_employee_ids,
                    work_ticket_ref=request.work_ticket_ref,
                    thread_ref=request.thread_ref,
                    runtrace_ref=request.runtrace_ref,
                    source_kind=request.source_kind,
                    idempotency_key=request.idempotency_key or self._build_idempotency_key(request),
                    status="dropped_stale",
                    attempt_count=0,
                    delivery_guard_epoch=request.delivery_guard_epoch,
                    delivery_guard_checked_at=datetime.now(UTC),
                    stale_drop_reason=stale_drop_reason,
                    dropped_as_stale=True,
                    error_detail=None,
                )
            )
            if request.runtrace_ref:
                get_control_plane_service().append_run_trace_event(
                    request.runtrace_ref,
                    RunEvent(
                        event_type="stale_reply_dropped",
                        message="Feishu outbound reply was dropped because the run is no longer active on the thread.",
                        metadata={
                            "thread_id": request.thread_ref or "",
                            "runtrace_id": request.runtrace_ref,
                            "active_runtrace_id": (
                                (
                                    self._conversation.get_required_thread(request.thread_ref).active_runtrace_ref
                                    if request.thread_ref and self._conversation.get_thread(request.thread_ref)
                                    else ""
                                )
                                or ""
                            ),
                            "outbound_source_kind": request.source_kind,
                            "reason": stale_drop_reason,
                            "outbound_ref": dropped_record.outbound_id,
                        },
                    ),
                )
            return FeishuSendMessageResult(
                app_id=request.app_id,
                receive_id_type=request.receive_id_type,
                receive_id=request.chat_id,
                message_id=None,
                status="dropped_stale",
                attempt_count=0,
                mention_employee_ids=request.mention_employee_ids,
                outbound_ref=dropped_record.outbound_id,
                attachment_object_ref=None,
                error_detail=stale_drop_reason,
            )

        idempotency_key = request.idempotency_key or self._build_idempotency_key(request)
        existing = self._find_successful_outbound(idempotency_key)
        if existing is not None:
            return FeishuSendMessageResult(
                app_id=existing.app_id,
                receive_id_type=existing.receive_id_type,
                receive_id=existing.receive_id,
                message_id=existing.message_id,
                status="deduplicated",
                attempt_count=existing.attempt_count,
                mention_employee_ids=existing.mention_employee_ids,
                outbound_ref=existing.outbound_id,
                attachment_object_ref=existing.attachment_object_ref,
                error_detail=existing.error_detail,
            )

        payload = {
            "receive_id": request.chat_id,
            "msg_type": "text",
            "content": json.dumps(
                {"text": self._compose_text_with_mentions(request.text, request.mention_employee_ids)},
                ensure_ascii=False,
            ),
        }
        settings = get_settings()
        attempt_count = 0
        last_error: str | None = None
        max_attempts = max(1, settings.feishu_send_max_attempts)

        for attempt in range(1, max_attempts + 1):
            attempt_count = attempt
            try:
                access_token = self._get_tenant_access_token(app_config.app_id, app_config.app_secret)
                response_body = self._post_json(
                    f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={request.receive_id_type}",
                    payload,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                data = response_body.get("data", {})
                attachment_blob = get_artifact_store_service().store_text(
                    source_type="feishu_reply_attachment",
                    source_ref=data.get("message_id") or f"pending-{uuid4().hex[:8]}",
                    text=request.text,
                    filename="reply.txt",
                    summary=f"Feishu {request.source_kind} reply for {request.chat_id}",
                    work_ticket_ref=request.work_ticket_ref,
                    thread_ref=request.thread_ref,
                    runtrace_ref=request.runtrace_ref,
                )
                outbound_record = self._outbound.save(
                    FeishuOutboundMessageRecord(
                        outbound_id=f"fo-{uuid4().hex[:8]}",
                        app_id=request.app_id,
                        receive_id_type=request.receive_id_type,
                        receive_id=request.chat_id,
                        message_id=data.get("message_id"),
                        text=request.text,
                        mention_employee_ids=request.mention_employee_ids,
                        work_ticket_ref=request.work_ticket_ref,
                        thread_ref=request.thread_ref,
                        runtrace_ref=request.runtrace_ref,
                        source_kind=request.source_kind,
                        idempotency_key=idempotency_key,
                        status="sent",
                        attempt_count=attempt_count,
                        delivery_guard_epoch=request.delivery_guard_epoch,
                        delivery_guard_checked_at=datetime.now(UTC),
                        error_detail=None,
                        attachment_object_ref=attachment_blob.object_id,
                        attachment_bucket=attachment_blob.bucket,
                        attachment_object_key=attachment_blob.object_key,
                    )
                )
                if request.runtrace_ref:
                    get_control_plane_service().append_run_trace_event(
                        request.runtrace_ref,
                        RunEvent(
                            event_type="feishu_reply_sent",
                            message="Feishu outbound reply sent and mirrored to artifacts.",
                            metadata={
                                "app_id": request.app_id,
                                "receive_id": request.chat_id,
                                "source_kind": request.source_kind,
                                "outbound_ref": outbound_record.outbound_id,
                                "attempt_count": str(attempt_count),
                            },
                        ),
                    )
                return FeishuSendMessageResult(
                    app_id=request.app_id,
                    receive_id_type=request.receive_id_type,
                    receive_id=request.chat_id,
                    message_id=data.get("message_id"),
                    status="sent",
                    attempt_count=attempt_count,
                    mention_employee_ids=request.mention_employee_ids,
                    outbound_ref=outbound_record.outbound_id,
                    attachment_object_ref=attachment_blob.object_id,
                )
            except ValueError as exc:
                last_error = str(exc)
                if attempt < max_attempts:
                    time.sleep(settings.feishu_send_retry_backoff_seconds * attempt)

        failed_record = self._outbound.save(
            FeishuOutboundMessageRecord(
                outbound_id=f"fo-{uuid4().hex[:8]}",
                app_id=request.app_id,
                receive_id_type=request.receive_id_type,
                receive_id=request.chat_id,
                message_id=None,
                text=request.text,
                mention_employee_ids=request.mention_employee_ids,
                work_ticket_ref=request.work_ticket_ref,
                thread_ref=request.thread_ref,
                runtrace_ref=request.runtrace_ref,
                source_kind=request.source_kind,
                idempotency_key=idempotency_key,
                status="failed",
                attempt_count=attempt_count,
                delivery_guard_epoch=request.delivery_guard_epoch,
                delivery_guard_checked_at=datetime.now(UTC),
                error_detail=last_error,
            )
        )
        if request.runtrace_ref:
            get_control_plane_service().append_run_trace_event(
                request.runtrace_ref,
                RunEvent(
                    event_type="feishu_reply_failed",
                    message="Feishu outbound reply failed after retries.",
                    metadata={
                        "app_id": request.app_id,
                        "receive_id": request.chat_id,
                        "source_kind": request.source_kind,
                        "outbound_ref": failed_record.outbound_id,
                        "attempt_count": str(attempt_count),
                        "error_detail": last_error or "",
                    },
                ),
            )
        return FeishuSendMessageResult(
            app_id=request.app_id,
            receive_id_type=request.receive_id_type,
            receive_id=request.chat_id,
            message_id=None,
            status="failed",
            attempt_count=attempt_count,
            mention_employee_ids=request.mention_employee_ids,
            outbound_ref=failed_record.outbound_id,
            attachment_object_ref=None,
            error_detail=last_error,
        )

    def list_inbound_events(self) -> list[FeishuInboundEventRecord]:
        return self._inbound.list()

    def list_group_debug_events(self) -> list[FeishuGroupDebugEventRecord]:
        events = self._group_debug.list()
        events.sort(key=lambda item: item.captured_at, reverse=True)
        return events

    def get_group_debug_event(self, debug_event_id: str) -> FeishuGroupDebugEventRecord:
        event = self._group_debug.get(debug_event_id)
        if event is None:
            raise KeyError(debug_event_id)
        return event

    def list_outbound_messages(self) -> list[FeishuOutboundMessageRecord]:
        return self._outbound.list()

    def list_dead_letters(self, include_resolved: bool = False) -> list[FeishuOutboundMessageRecord]:
        dead_letters = [
            record
            for record in self._outbound.list()
            if record.status == "failed" and (include_resolved or record.replayed_by_outbound_ref is None)
        ]
        dead_letters.sort(key=lambda item: item.last_attempt_at, reverse=True)
        return dead_letters

    def list_replay_audit(
        self,
        *,
        source_outbound_ref: str | None = None,
        chat_id: str | None = None,
    ) -> list[FeishuReplayAuditEntryView]:
        records = self._outbound.list()
        audit_entries = [
            FeishuReplayAuditEntryView(
                outbound_id=record.outbound_id,
                app_id=record.app_id,
                receive_id=record.receive_id,
                source_kind=record.source_kind,
                status=record.status,
                attempt_count=record.attempt_count,
                created_at=record.created_at,
                error_detail=record.error_detail,
                replay_source_outbound_ref=record.replay_source_outbound_ref,
                replay_root_outbound_ref=record.replay_root_outbound_ref,
                work_ticket_ref=record.work_ticket_ref,
                thread_ref=record.thread_ref,
                runtrace_ref=record.runtrace_ref,
            )
            for record in records
            if record.replay_source_outbound_ref is not None
        ]

        if source_outbound_ref:
            audit_entries = [
                entry
                for entry in audit_entries
                if entry.replay_source_outbound_ref == source_outbound_ref or entry.replay_root_outbound_ref == source_outbound_ref
            ]
        if chat_id:
            audit_entries = [entry for entry in audit_entries if entry.receive_id == chat_id]

        audit_entries.sort(key=lambda item: item.created_at, reverse=True)
        return audit_entries

    def get_dead_letter_detail(self, outbound_id: str) -> FeishuDeadLetterDetailView:
        original = self._get_required_outbound(outbound_id)
        return FeishuDeadLetterDetailView(
            dead_letter=original,
            replay_history=self.list_replay_audit(source_outbound_ref=outbound_id),
        )

    def replay_outbound_message(self, outbound_id: str) -> FeishuReplayMessageResult:
        original = self._get_required_outbound(outbound_id)
        if original.status != "failed":
            raise ValueError(f"Outbound message is not a dead letter: {outbound_id}")
        replay_result = self.send_text_message(
            FeishuSendMessageRequest(
                app_id=original.app_id,
                chat_id=original.receive_id,
                text=original.text,
                mention_employee_ids=original.mention_employee_ids,
                receive_id_type=original.receive_id_type,
                work_ticket_ref=original.work_ticket_ref,
                thread_ref=original.thread_ref,
                runtrace_ref=original.runtrace_ref,
                source_kind=f"{original.source_kind}:replay",
                idempotency_key=original.idempotency_key or original.outbound_id,
            )
        )

        updated_original = self._outbound.save(
            original.model_copy(
                update={
                    "replay_attempt_count": original.replay_attempt_count + 1,
                    "replayed_by_outbound_ref": replay_result.outbound_ref or original.replayed_by_outbound_ref,
                    "last_replay_at": datetime.now(UTC),
                }
            )
        )
        if replay_result.outbound_ref:
            replayed_record = self._get_required_outbound(replay_result.outbound_ref)
            self._outbound.save(
                replayed_record.model_copy(
                    update={
                        "replay_source_outbound_ref": updated_original.outbound_id,
                        "replay_root_outbound_ref": updated_original.replay_root_outbound_ref or updated_original.outbound_id,
                    }
                )
            )
        if replay_result.outbound_ref and updated_original.runtrace_ref:
            get_control_plane_service().append_run_trace_event(
                updated_original.runtrace_ref,
                RunEvent(
                    event_type="feishu_dead_letter_replayed",
                    message="Feishu failed outbound replayed from dead-letter queue.",
                    metadata={
                        "source_outbound_ref": updated_original.outbound_id,
                        "replay_outbound_ref": replay_result.outbound_ref,
                        "status": replay_result.status,
                    },
                ),
            )

        return FeishuReplayMessageResult(
            source_outbound_ref=updated_original.outbound_id,
            replay_attempt_count=updated_original.replay_attempt_count,
            replay_result=replay_result,
        )

    def list_bot_apps(self) -> list[FeishuBotAppView]:
        return [
            FeishuBotAppView(
                employee_id=config.employee_id,
                app_id=config.app_id,
                bot_identity=config.bot_identity,
                bot_open_id=config.bot_open_id,
                display_name=config.display_name,
            )
            for config in get_feishu_bot_app_configs()
        ]

    def _parse_control_command(self, intent: str) -> str:
        stripped = intent.strip()
        lowered = stripped.lower()
        if lowered == "/new":
            return "new_only"
        if lowered.startswith("/new "):
            return "new_with_message"
        return "default"

    def _strip_new_command_prefix(self, intent: str) -> str:
        stripped = intent.strip()
        if stripped.lower() == "/new":
            return ""
        if stripped.lower().startswith("/new "):
            return stripped[5:].strip()
        return stripped

    def _handle_new_conversation_marker(
        self,
        *,
        app_id: str,
        event: dict[str, Any],
        surface: ConversationSurface,
        chat_id: str,
        binding: Any,
    ) -> FeishuWebhookResult:
        if surface == ConversationSurface.FEISHU_GROUP:
            prompt = "群聊默认不支持自由 `/new`。如果需要新起一条可见协作，请使用 `/new @bot 你的问题`，或在 Dashboard 中显式发起新线程。"
            send_result = self.send_text_message(
                FeishuSendMessageRequest(
                    app_id=app_id,
                    chat_id=chat_id,
                    text=prompt,
                    source_kind="control_reply",
                    idempotency_key=self._auto_reply_idempotency_key(
                        app_id=app_id,
                        message_id=f"group-new-block-{chat_id}",
                        source_kind="control_reply",
                        ordinal=1,
                        text=prompt,
                    ),
                )
            )
            return FeishuWebhookResult(
                status="ignored",
                app_id=app_id,
                surface=surface,
                reply_sent=send_result.status in {"sent", "deduplicated"},
                reply_count=1 if send_result.status in {"sent", "deduplicated"} else 0,
                dispatch_mode="group_new_blocked",
                detail="Group /new requires explicit targeted syntax.",
            )

        channel_id = self._channel_id_for(surface, chat_id)
        dispatch_target_ids = [binding.virtual_employee]
        participant_ids = self._build_participants(event, binding.virtual_employee, dispatch_target_ids)
        thread = self._conversation.start_new_thread(
            surface=surface,
            channel_id=channel_id,
            initiator_id=self._resolve_initiator(event),
            participant_ids=participant_ids,
            bound_agent_ids=dispatch_target_ids,
            title="新会话",
        )
        prompt = "已开启一个新对话。下一条消息会作为全新会话继续；也可以直接发送 `/new 你的问题` 一步开始。"
        send_result = self.send_text_message(
            FeishuSendMessageRequest(
                app_id=app_id,
                chat_id=chat_id,
                text=prompt,
                thread_ref=thread.thread_id,
                source_kind="control_reply",
                idempotency_key=self._auto_reply_idempotency_key(
                    app_id=app_id,
                    message_id=f"new-{thread.thread_id}",
                    source_kind="control_reply",
                    ordinal=1,
                    text=prompt,
                ),
            )
        )
        return FeishuWebhookResult(
            status="processed",
            app_id=app_id,
            surface=surface,
            message_id=None,
            thread_id=thread.thread_id,
            reply_sent=send_result.status in {"sent", "deduplicated"},
            reply_count=1 if send_result.status in {"sent", "deduplicated"} else 0,
            target_agent_ids=dispatch_target_ids,
            dispatch_mode="new_conversation_marker",
            detail="Started a fresh conversation thread.",
        )

    def _orchestrate_visible_handoffs(
        self,
        *,
        source_employee_id: str,
        handoff_targets: list[str],
        handoff_reason: str | None,
        handoff_origin: str | None,
        handoff_resolution_basis: str | None,
        structured_handoff_targets: list[str],
        reply_visible_named_targets: list[str],
        reply_semantic_handoff_targets: list[str],
        scheduled_turn_targets: list[str],
        app_id: str,
        chat_id: str,
        surface: ConversationSurface,
        channel_id: str,
        user_message: str,
        source_reply_text: str,
        event: dict[str, Any],
        intake_result_thread_id: str,
        work_ticket_ref: str,
        runtrace_ref: str,
        already_targeted_agent_ids: list[str],
        visible_participants: list[str],
        collaboration_intent: str | None,
        initial_spoken_bot_ids: list[str],
        available_bot_ids: list[str],
        user_repeat_allowed_ids: list[str],
        initial_visible_turn_count: int,
        delivery_guard_epoch: int | None,
        interruption_reason: str | None,
        dispatch_reason: str | None,
    ) -> dict[str, Any]:
        limit = max(0, get_settings().feishu_visible_handoff_turn_limit)
        if limit == 0:
            return {"reply_count": 0, "reply_errors": []}

        reply_count = 0
        reply_errors: list[str] = []
        thread = self._conversation.get_required_thread(intake_result_thread_id)
        dialogue_service = get_openclaw_dialogue_service()
        spoken_bot_ids = list(dict.fromkeys(initial_spoken_bot_ids))
        spoken_counts: dict[str, int] = {employee_id: 1 for employee_id in spoken_bot_ids}
        pending_handoffs: list[tuple[str, str, str | None, str, str | None, list[str], list[str], list[str], bool]] = [
            (
                source_employee_id,
                target_employee_id,
                handoff_reason,
                source_reply_text,
                handoff_resolution_basis,
                list(structured_handoff_targets),
                list(reply_visible_named_targets),
                list(reply_semantic_handoff_targets),
                False,
            )
            for target_employee_id in handoff_targets
        ]
        scheduled_queue = [
            employee_id
            for employee_id in dict.fromkeys(scheduled_turn_targets)
            if employee_id and employee_id not in handoff_targets
        ]
        visible_turn_count = initial_visible_turn_count
        handoff_turn_index = 0
        stop_reason: str | None = None
        stopped_by_turn_limit = False

        while pending_handoffs:
            if visible_turn_count >= limit:
                stopped_by_turn_limit = True
                stop_reason = "limit_reached"
                break
            (
                source_agent_for_turn,
                target_employee_id,
                reason_for_turn,
                source_reply_for_turn,
                resolution_basis_for_turn,
                structured_targets_for_turn,
                reply_visible_named_targets_for_turn,
                reply_semantic_targets_for_turn,
                scheduled_turn_for_turn,
            ) = pending_handoffs.pop(0)
            if target_employee_id == source_agent_for_turn:
                continue
            if (
                not scheduled_turn_for_turn
                and target_employee_id in already_targeted_agent_ids
                and spoken_counts.get(target_employee_id, 0) == 0
            ):
                continue
            if not self._can_repeat_visible_turn(
                employee_id=target_employee_id,
                spoken_counts=spoken_counts,
                reply_visible_named_targets=reply_visible_named_targets_for_turn,
                user_repeat_allowed_ids=user_repeat_allowed_ids,
            ):
                continue

            target_binding = self._conversation.get_bot_binding_by_employee_id(target_employee_id)
            target_config = get_feishu_bot_app_config_by_employee_id(target_employee_id)
            if target_binding is None or target_config is None:
                continue

            handoff_turn_index += 1
            visible_turn_count += 1
            spoken_counts[target_employee_id] = spoken_counts.get(target_employee_id, 0) + 1
            if target_employee_id not in spoken_bot_ids:
                spoken_bot_ids.append(target_employee_id)
            thread_state = self._conversation.get_required_thread(intake_result_thread_id)
            collaboration_context = self._build_collaboration_context(
                collaboration_intent=collaboration_intent,
                dispatch_targets=[*initial_spoken_bot_ids, *already_targeted_agent_ids],
                candidate_handoff_targets=[],
                spoken_bot_ids=spoken_bot_ids,
                available_bot_ids=available_bot_ids,
                visible_turn_count=visible_turn_count,
                dispatch_reason=dispatch_reason,
                last_committed_state=thread_state.last_committed_state,
                pending_handoff=thread_state.pending_handoff,
                interruption_mode=interruption_reason,
            )
            thread = self._conversation.merge_thread_visibility(
                intake_result_thread_id,
                participant_ids=[f"feishu-{target_employee_id}", self._resolve_initiator(event)],
                bound_agent_ids=[target_employee_id],
            )
            handoff_context = OpenClawHandoffContext(
                handoff_source_agent=source_agent_for_turn,
                handoff_target_agent=target_employee_id,
                handoff_reason=reason_for_turn,
                handoff_origin=handoff_origin,
                source_agent_visible_reply=source_reply_for_turn,
                original_user_message=user_message,
                thread_summary=self._build_thread_history(
                    thread_ref=intake_result_thread_id,
                    current_app_id=target_config.app_id,
                ),
                visible_turn_index=visible_turn_count,
                collaboration_intent=collaboration_intent,
                last_committed_state_summary=self._summarize_last_committed_state(thread_state.last_committed_state),
                pending_handoff_summary=self._summarize_pending_handoff(thread_state.pending_handoff),
                dispatch_reason=dispatch_reason,
                interruption_reason=interruption_reason,
                spoken_bot_ids=spoken_bot_ids,
                remaining_bot_ids=collaboration_context.remaining_bot_ids,
                remaining_turn_budget=collaboration_context.remaining_turn_budget,
            )
            dialogue_result = dialogue_service.generate_reply(
                employee_id=target_employee_id,
                user_message=user_message,
                work_ticket=get_control_plane_service().get_required_work_ticket(work_ticket_ref),
                channel_id=channel_id,
                surface=surface.value,
                app_id=target_config.app_id,
                visible_participants=thread.participant_ids,
                conversation_history=handoff_context.thread_summary,
                turn_mode="handoff_target",
                handoff_context=handoff_context,
                collaboration_context=collaboration_context,
            )
            repetition_violation = self._is_handoff_repetition_violation(
                source_reply=source_reply_for_turn,
                target_reply=dialogue_result.reply_text,
            )
            if repetition_violation:
                get_control_plane_service().flag_run_trace_handoff_repetition_violation(runtrace_ref)
                get_control_plane_service().append_run_trace_event(
                    runtrace_ref,
                    RunEvent(
                        event_type="handoff_repetition_violation",
                        message=f"{target_employee_id} repeated the source framing and was retried.",
                        metadata={
                            "handoff_source_agent": source_agent_for_turn,
                            "handoff_target_agent": target_employee_id,
                            "visible_turn_index": str(visible_turn_count),
                        },
                    ),
                )
                retry_context = handoff_context.model_copy(
                    update={
                        "retry_reason": "avoid_repeating_source_framing",
                        "prior_target_reply": dialogue_result.reply_text,
                    }
                )
                retry_result = dialogue_service.generate_reply(
                    employee_id=target_employee_id,
                    user_message=user_message,
                    work_ticket=get_control_plane_service().get_required_work_ticket(work_ticket_ref),
                    channel_id=channel_id,
                    surface=surface.value,
                    app_id=target_config.app_id,
                    visible_participants=thread.participant_ids,
                    conversation_history=retry_context.thread_summary,
                    turn_mode="handoff_target",
                    handoff_context=retry_context,
                    collaboration_context=collaboration_context.model_copy(
                        update={
                            "retry_reason": "avoid_repeating_source_framing",
                            "prior_reply_text": dialogue_result.reply_text,
                        }
                    ),
                )
                if self._is_handoff_repetition_violation(
                    source_reply=source_reply_for_turn,
                    target_reply=retry_result.reply_text,
                ):
                    dialogue_result = retry_result.model_copy(
                        update={
                            "reply_text": self._rewrite_handoff_target_reply(
                                target_employee_id=target_employee_id,
                                source_employee_id=source_agent_for_turn,
                            ),
                            "follow_up_texts": [],
                            "handoff_targets": [],
                            "turn_complete": True,
                        }
                    )
                else:
                    dialogue_result = retry_result
            self._conversation.attach_openclaw_session(
                intake_result_thread_id,
                target_employee_id,
                dialogue_result.session_key or f"agent:{target_employee_id}:{surface.value}:{chat_id}",
            )
            get_control_plane_service().append_run_trace_event(
                runtrace_ref,
                RunEvent(
                    event_type="visible_agent_handoff",
                    message=f"{source_agent_for_turn} handed off to {target_employee_id} in visible room.",
                    metadata={
                        "handoff_source_agent": source_agent_for_turn,
                        "handoff_targets": target_employee_id,
                        "handoff_reason": reason_for_turn or "",
                        "handoff_origin": handoff_origin or "",
                        "handoff_resolution_basis": resolution_basis_for_turn or "",
                        "structured_handoff_targets": ",".join(structured_targets_for_turn),
                        "reply_visible_named_targets": ",".join(reply_visible_named_targets_for_turn),
                        "reply_name_targets": ",".join(reply_visible_named_targets_for_turn),
                        "reply_semantic_handoff_targets": ",".join(reply_semantic_targets_for_turn),
                        "final_handoff_targets": target_employee_id,
                        "visible_turn_index": str(visible_turn_count),
                        "remaining_turn_budget": str(max(limit - visible_turn_count, 0)),
                        "app_id": app_id,
                        "chat_id": chat_id,
                    },
                ),
            )

            (
                dialogue_result,
                nested_targets,
                nested_reply_visible_named_targets,
                nested_reply_semantic_targets,
                nested_resolution_basis,
                nested_contract_violation,
            ) = self._resolve_dialogue_handoff_targets(
                dialogue_service=dialogue_service,
                current_employee_id=target_employee_id,
                dialogue_result=dialogue_result,
                work_ticket_ref=work_ticket_ref,
                user_message=user_message,
                forced_handoff_targets=[],
                channel_id=channel_id,
                surface=surface,
                chat_id=chat_id,
                current_app_id=target_config.app_id,
                visible_participants=thread.participant_ids,
                conversation_history=handoff_context.thread_summary,
                collaboration_context=collaboration_context,
                turn_mode="handoff_target",
                handoff_context=handoff_context,
            )
            if nested_contract_violation:
                get_control_plane_service().flag_run_trace_handoff_contract_violation(runtrace_ref)
                get_control_plane_service().append_run_trace_event(
                    runtrace_ref,
                    RunEvent(
                        event_type="handoff_contract_violation",
                        message=f"{target_employee_id} requested another bot without naming it in visible text.",
                        metadata={
                            "employee_id": target_employee_id,
                            "resolved_handoff_targets": ",".join(nested_targets),
                            "visible_turn_index": str(visible_turn_count),
                        },
                    ),
                )
                stop_reason = "handoff_contract_violation"

            get_control_plane_service().append_run_trace_event(
                runtrace_ref,
                RunEvent(
                    event_type="handoff_target_dialogue_generated",
                    message=f"{target_employee_id} generated a visible handoff reply.",
                    metadata={
                        "strategy": dialogue_result.strategy,
                        "model_ref": dialogue_result.model_ref,
                        "turn_mode": "handoff_target",
                        "handoff_source_agent": source_agent_for_turn,
                        "handoff_target_agent": target_employee_id,
                        "visible_turn_index": str(visible_turn_count),
                        "handoff_source_reply": source_reply_for_turn,
                        "handoff_target_reply": dialogue_result.reply_text,
                        "handoff_resolution_basis": nested_resolution_basis or "",
                        "structured_handoff_targets": ",".join(dialogue_result.handoff_targets),
                        "reply_visible_named_targets": ",".join(nested_reply_visible_named_targets),
                        "reply_name_targets": ",".join(nested_reply_visible_named_targets),
                        "reply_semantic_handoff_targets": ",".join(nested_reply_semantic_targets),
                        "final_handoff_targets": ",".join(nested_targets),
                        "remaining_turn_budget": str(max(limit - visible_turn_count, 0)),
                        "error_detail": dialogue_result.error_detail or "",
                    },
                ),
            )

            source_config_for_turn = get_feishu_bot_app_config_by_employee_id(source_agent_for_turn)
            source_display_name_for_turn = (
                (source_config_for_turn.display_name if source_config_for_turn else source_agent_for_turn) or source_agent_for_turn
            )
            handoff_intro = (
                f"{source_display_name_for_turn} 请求 {target_config.display_name or target_employee_id} 接棒。"
                if handoff_turn_index == 1 and reason_for_turn
                else ""
            )
            reply_specs = []
            if handoff_intro:
                reply_specs.append(("visible_handoff_notice", f"{handoff_intro} 原因：{reason_for_turn}"))
            reply_specs.extend(
                [
                    ("visible_handoff_reply", dialogue_result.reply_text),
                    *[("visible_handoff_follow_up", text) for text in dialogue_result.follow_up_texts],
                ]
            )
            streamed_specs = self._expand_visible_reply_specs(reply_specs)
            for ordinal, (source_kind, reply_text) in enumerate(streamed_specs, start=1):
                try:
                    send_result = self.send_text_message(
                        FeishuSendMessageRequest(
                            app_id=target_config.app_id,
                            chat_id=chat_id,
                            text=reply_text,
                            work_ticket_ref=work_ticket_ref,
                            thread_ref=intake_result_thread_id,
                            runtrace_ref=runtrace_ref,
                            delivery_guard_epoch=delivery_guard_epoch,
                            source_kind=source_kind,
                            idempotency_key=self._auto_reply_idempotency_key(
                                app_id=target_config.app_id,
                                message_id=f"{app_id}:{thread.thread_id}:{target_employee_id}:{visible_turn_count}",
                                source_kind=source_kind,
                                ordinal=ordinal,
                                text=reply_text,
                            ),
                        )
                    )
                    if send_result.status in {"sent", "deduplicated"}:
                        reply_count += 1
                    else:
                        reply_errors.append(send_result.error_detail or f"{source_kind} failed")
                        break
                except ValueError as exc:
                    reply_errors.append(str(exc))
                    break

            get_control_plane_service().set_run_trace_reply_visible_named_targets(
                runtrace_ref,
                nested_reply_visible_named_targets,
            )
            get_control_plane_service().set_run_trace_visible_turn_count(
                runtrace_ref,
                visible_turn_count,
            )
            self._update_thread_turn_state(
                thread_id=intake_result_thread_id,
                speaker_id=target_employee_id,
                reply_text=dialogue_result.reply_text,
                handoff_targets=nested_targets,
                handoff_reason=dialogue_result.handoff_reason,
                runtrace_ref=runtrace_ref,
            )
            get_control_plane_service().set_run_trace_handoff_chain_state(
                runtrace_ref,
                spoken_bot_ids=spoken_bot_ids,
                remaining_bot_ids=collaboration_context.remaining_bot_ids,
                remaining_turn_budget=collaboration_context.remaining_turn_budget,
                stop_reason=stop_reason,
            )

            queued_targets = 0
            if scheduled_queue and visible_turn_count < limit:
                next_scheduled_target = scheduled_queue.pop(0)
                if (
                    next_scheduled_target != target_employee_id
                    and self._conversation.get_bot_binding_by_employee_id(next_scheduled_target) is not None
                    and self._can_repeat_visible_turn(
                        employee_id=next_scheduled_target,
                        spoken_counts=spoken_counts,
                        reply_visible_named_targets=nested_reply_visible_named_targets,
                        user_repeat_allowed_ids=user_repeat_allowed_ids,
                    )
                ):
                    queued_targets += 1
                    pending_handoffs.append(
                        (
                            target_employee_id,
                            next_scheduled_target,
                            dialogue_result.handoff_reason or reason_for_turn,
                            dialogue_result.reply_text,
                            nested_resolution_basis or "interruption_schedule",
                            list(dialogue_result.handoff_targets),
                            list(nested_reply_visible_named_targets),
                            list(nested_reply_semantic_targets),
                            True,
                        )
                    )
            if nested_targets and visible_turn_count < limit:
                for nested_target in nested_targets:
                    if nested_target == target_employee_id:
                        continue
                    if nested_target in already_targeted_agent_ids and spoken_counts.get(nested_target, 0) == 0:
                        continue
                    if not self._can_repeat_visible_turn(
                        employee_id=nested_target,
                        spoken_counts=spoken_counts,
                        reply_visible_named_targets=nested_reply_visible_named_targets,
                        user_repeat_allowed_ids=user_repeat_allowed_ids,
                    ):
                        continue
                    queued_targets += 1
                    pending_handoffs.append(
                        (
                            target_employee_id,
                            nested_target,
                            dialogue_result.handoff_reason,
                            dialogue_result.reply_text,
                            nested_resolution_basis,
                            list(dialogue_result.handoff_targets),
                            list(nested_reply_visible_named_targets),
                            list(nested_reply_semantic_targets),
                            False,
                        )
                    )
            if (
                queued_targets == 0
                and not nested_contract_violation
                and visible_turn_count < limit
            ):
                fallback_repeat_targets = [
                    employee_id
                    for employee_id in user_repeat_allowed_ids
                    if employee_id != target_employee_id
                    and spoken_counts.get(employee_id, 0) == 1
                ]
                for repeat_target in fallback_repeat_targets:
                    if repeat_target in already_targeted_agent_ids and spoken_counts.get(repeat_target, 0) == 0:
                        continue
                    if not self._can_repeat_visible_turn(
                        employee_id=repeat_target,
                        spoken_counts=spoken_counts,
                        reply_visible_named_targets=[],
                        user_repeat_allowed_ids=user_repeat_allowed_ids,
                    ):
                        continue
                    queued_targets += 1
                    pending_handoffs.append(
                        (
                            target_employee_id,
                            repeat_target,
                            dialogue_result.handoff_reason,
                            dialogue_result.reply_text,
                            nested_resolution_basis or "user_explicit_repeat",
                            list(dialogue_result.handoff_targets),
                            [],
                            list(nested_reply_semantic_targets),
                            False,
                        )
                    )
            if not nested_targets and collaboration_intent == "multi_turn_collaboration" and stop_reason is None:
                stop_reason = (
                    "no_remaining_bots"
                    if not collaboration_context.remaining_bot_ids
                    else "no_resolved_next_hop"
                )
            elif nested_contract_violation:
                stop_reason = "handoff_contract_violation"
            elif queued_targets > 0:
                stop_reason = None
            elif nested_targets:
                stopped_by_turn_limit = True
                stop_reason = "limit_reached"

        if pending_handoffs and visible_turn_count >= limit:
            stopped_by_turn_limit = True
            stop_reason = "limit_reached"

        get_control_plane_service().set_run_trace_visible_turn_count(
            runtrace_ref,
            visible_turn_count,
        )
        get_control_plane_service().set_run_trace_handoff_chain_state(
            runtrace_ref,
            spoken_bot_ids=spoken_bot_ids,
            remaining_bot_ids=[
                employee_id
                for employee_id in available_bot_ids
                if employee_id not in spoken_bot_ids
            ],
            remaining_turn_budget=max(limit - visible_turn_count, 0),
            stop_reason=stop_reason,
        )

        if pending_handoffs or stopped_by_turn_limit:
            get_control_plane_service().flag_run_trace_stopped_by_turn_limit(runtrace_ref)
            get_control_plane_service().append_run_trace_event(
                runtrace_ref,
                RunEvent(
                    event_type="visible_handoff_limit_reached",
                    message="Visible handoff chain stopped because the turn limit was reached.",
                    metadata={
                        "stopped_by_turn_limit": "true",
                        "remaining_pending_handoffs": str(len(pending_handoffs) or int(stopped_by_turn_limit)),
                        "limit": str(limit),
                    },
                ),
            )

        return {"reply_count": reply_count, "reply_errors": reply_errors}

    def _can_repeat_visible_turn(
        self,
        *,
        employee_id: str,
        spoken_counts: dict[str, int],
        reply_visible_named_targets: list[str],
        user_repeat_allowed_ids: list[str],
    ) -> bool:
        current_count = spoken_counts.get(employee_id, 0)
        if current_count == 0:
            return True
        if employee_id in reply_visible_named_targets:
            return True
        return employee_id in user_repeat_allowed_ids and current_count == 1

    def _build_thread_history(self, *, thread_ref: str, current_app_id: str) -> str:
        entries: list[tuple[float, str]] = []
        for inbound in self._inbound.list():
            if inbound.thread_ref != thread_ref or not inbound.text:
                continue
            sender = inbound.sender_id or "unknown-user"
            entries.append((inbound.processed_at.timestamp(), f"[user:{sender}] {inbound.text}"))

        for outbound in self._outbound.list():
            if outbound.thread_ref != thread_ref:
                continue
            role = "assistant"
            if outbound.app_id != current_app_id:
                role = f"visible-peer:{outbound.app_id}"
            entries.append((outbound.created_at.timestamp(), f"[{role}] {outbound.text}"))

        if not entries:
            return ""
        entries.sort(key=lambda item: item[0])
        return "\n".join(text for _, text in entries[-10:])

    def _expand_visible_reply_specs(self, reply_specs: list[tuple[str, str]]) -> list[tuple[str, str]]:
        settings = get_settings()
        if not settings.feishu_stream_enabled:
            return [(source_kind, text.strip()) for source_kind, text in reply_specs if text.strip()]

        expanded: list[tuple[str, str]] = []
        for source_kind, reply_text in reply_specs:
            for chunk in self._chunk_visible_reply(reply_text):
                expanded.append((source_kind, chunk))
        return expanded

    def _chunk_visible_reply(self, reply_text: str) -> list[str]:
        text = reply_text.strip()
        if not text:
            return []
        settings = get_settings()
        limit = max(80, settings.feishu_stream_chunk_chars)
        if len(text) <= limit:
            return [text]

        paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
        if not paragraphs:
            return [text]

        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            candidate = paragraph if not current else f"{current}\n\n{paragraph}"
            if len(candidate) <= limit:
                current = candidate
                continue
            if current:
                chunks.append(current)
                current = ""
            if len(paragraph) <= limit:
                current = paragraph
                continue
            sentence_chunks = self._split_long_paragraph(paragraph, limit)
            chunks.extend(sentence_chunks[:-1])
            current = sentence_chunks[-1]
        if current:
            chunks.append(current)
        return chunks or [text]

    def _split_long_paragraph(self, paragraph: str, limit: int) -> list[str]:
        pieces: list[str] = []
        remaining = paragraph.strip()
        while len(remaining) > limit:
            boundary = max(
                remaining.rfind(marker, 0, limit)
                for marker in ("。", "！", "？", "\n", "；", "，", " ")
            )
            if boundary <= 0:
                boundary = limit
            chunk = remaining[:boundary].strip()
            if chunk:
                pieces.append(chunk)
            remaining = remaining[boundary:].strip()
        if remaining:
            pieces.append(remaining)
        return pieces

    def _sleep_between_stream_chunks(self, index: int, total: int) -> None:
        if index >= total:
            return
        delay = get_settings().feishu_stream_chunk_delay_seconds
        if delay > 0:
            time.sleep(delay)

    def _get_tenant_access_token(self, app_id: str, app_secret: str) -> str:
        cached = self._token_cache.get(app_id)
        if cached and cached.expires_at > time.time() + 30:
            return cached.value

        payload = {"app_id": app_id, "app_secret": app_secret}
        response_body = self._post_json(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            payload,
        )
        token = response_body.get("tenant_access_token")
        expire = int(response_body.get("expire", 0))
        if not token:
            raise ValueError(f"Failed to get tenant access token for app_id: {app_id}")
        self._token_cache[app_id] = CachedToken(value=token, expires_at=time.time() + expire)
        return token

    def _post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                **(headers or {}),
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=8) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")
            raise ValueError(f"Feishu API request failed: {exc.code} {detail}") from exc

    def _verify_plain_callback_token(self, payload: dict[str, Any]) -> None:
        settings = get_settings()
        verification_token = payload.get("token")
        if settings.feishu_verification_token and verification_token != settings.feishu_verification_token:
            raise ValueError("Feishu callback verification token mismatch.")

    def _extract_text_intent(self, content: str) -> str:
        if not content:
            return ""
        payload = json.loads(content)
        return (payload.get("text") or "").strip()

    def _surface_for_chat_type(self, chat_type: str | None) -> ConversationSurface:
        if chat_type == "p2p":
            return ConversationSurface.FEISHU_DM
        return ConversationSurface.FEISHU_GROUP

    def _channel_id_for(self, surface: ConversationSurface, chat_id: str) -> str:
        if surface == ConversationSurface.FEISHU_DM:
            return f"feishu:dm:{chat_id}"
        return f"feishu:group:{chat_id}"

    def _resolve_target_agents(self, event: dict[str, Any]) -> list[str]:
        agent_ids: list[str] = []
        for mention in self._message_mentions(event):
            for binding in self._conversation.list_bot_seat_bindings():
                config = get_feishu_bot_app_config_by_employee_id(binding.virtual_employee)
                if config and self._mention_targets_bot(mention, binding.virtual_employee, config):
                    agent_ids.append(binding.virtual_employee)
        return list(dict.fromkeys(agent_ids))

    def _resolve_deterministic_name_targets(self, user_message: str) -> list[str]:
        normalized_message = self._normalize_human_label(user_message)
        if not normalized_message:
            return []

        target_ids: list[str] = []
        for binding in self._conversation.list_bot_seat_bindings():
            config = get_feishu_bot_app_config_by_employee_id(binding.virtual_employee)
            if config is None:
                continue
            aliases = self._bot_name_aliases(binding.virtual_employee, config)
            if any(alias and alias in normalized_message for alias in aliases):
                target_ids.append(binding.virtual_employee)
        return list(dict.fromkeys(target_ids))

    def _resolve_deterministic_text_targets(self, user_message: str) -> list[str]:
        return self._resolve_deterministic_name_targets(user_message)

    def _should_infer_semantic_dispatch(
        self,
        user_message: str,
        deterministic_name_target_ids: list[str],
        explicit_target_ids: list[str],
    ) -> bool:
        normalized_message = self._normalize_human_label(user_message)
        if not normalized_message:
            return False
        semantic_role_hints = (
            "需要产品",
            "需要设计",
            "需要研究",
            "需要工程",
            "需要质量",
            "需要项目",
            "让产品",
            "让设计",
            "让研究",
            "让工程",
            "让质量",
            "让项目",
            "请产品",
            "请设计",
            "请研究",
            "请工程",
            "请质量",
            "请项目",
            "产品判断",
            "设计补充",
            "研究补充",
            "工程判断",
            "质量判断",
        )
        if not deterministic_name_target_ids and not explicit_target_ids:
            return True
        return any(hint in normalized_message for hint in (*MULTI_TURN_COLLABORATION_HINTS, *semantic_role_hints))

    def _collaboration_intent(
        self,
        *,
        user_message: str,
        dispatch_target_ids: list[str],
        candidate_handoff_target_ids: list[str],
    ) -> str:
        normalized_message = self._normalize_human_label(user_message)
        if (
            any(hint in normalized_message for hint in MULTI_TURN_COLLABORATION_HINTS)
            or candidate_handoff_target_ids
            or len(dispatch_target_ids) > 1
        ):
            return "multi_turn_collaboration"
        return "single_turn_targeted"

    def _user_repeat_allowed_targets(
        self,
        *,
        user_message: str,
        current_employee_id: str,
        dispatch_target_ids: list[str],
        channel_id: str,
        surface: ConversationSurface,
        chat_id: str,
        current_app_id: str,
    ) -> list[str]:
        normalized_message = self._normalize_human_label(user_message)
        if not normalized_message:
            return []
        explicit_targets: list[str] = []
        if any(marker in normalized_message for marker in USER_REPEAT_CURRENT_BOT_MARKERS):
            explicit_targets.append(current_employee_id)
        config = get_feishu_bot_app_config_by_employee_id(current_employee_id)
        aliases = self._bot_name_aliases(current_employee_id, config) if config is not None else []
        named_repeat_markers = (
            "最后请",
            "最后由",
            "最后再",
            "再次",
            "再回复",
            "再总结",
            "来收口",
            "来拍板",
            "收口一下",
            "最后还是",
        )
        if any(alias and alias in normalized_message for alias in aliases) and any(
            marker in normalized_message for marker in named_repeat_markers
        ):
            explicit_targets.append(current_employee_id)

        explicit_targets.extend(
            self._resolve_explicit_repeat_named_targets(
                user_message=user_message,
                candidate_employee_ids=list(dict.fromkeys([current_employee_id, *dispatch_target_ids])),
            )
        )
        explicit_targets = list(dict.fromkeys(explicit_targets))
        if explicit_targets:
            return explicit_targets

        if not self._should_infer_semantic_repeat_recall(normalized_message):
            return []

        inferred_target_ids = self._infer_repeat_recall_target_ids(
            receiving_employee_id=current_employee_id,
            user_message=user_message,
            channel_id=channel_id,
            surface=surface,
            chat_id=chat_id,
            current_app_id=current_app_id,
            candidate_employee_ids=list(dict.fromkeys([current_employee_id, *dispatch_target_ids])),
        )
        return inferred_target_ids

    def _resolve_explicit_repeat_named_targets(
        self,
        *,
        user_message: str,
        candidate_employee_ids: list[str],
    ) -> list[str]:
        normalized_message = self._normalize_human_label(user_message)
        if not normalized_message:
            return []
        repeat_markers = (
            "最后请",
            "最后由",
            "最后还是",
            "最后再",
            "再回复",
            "再总结",
            "再次",
            "再回一次",
            "来收口",
            "收口一下",
            "来拍板",
            "再拍板",
        )
        if not any(marker in normalized_message for marker in repeat_markers):
            return []
        targets: list[str] = []
        for employee_id in candidate_employee_ids:
            config = get_feishu_bot_app_config_by_employee_id(employee_id)
            aliases = self._bot_name_aliases(employee_id, config) if config is not None else self._employee_aliases(employee_id)
            for alias in aliases:
                if not alias:
                    continue
                explicit_repeat_patterns = (
                    f"最后请{alias}",
                    f"最后由{alias}",
                    f"最后还是{alias}",
                    f"最后再由{alias}",
                    f"最后让{alias}",
                    f"请{alias}再",
                    f"让{alias}再",
                    f"{alias}再回复",
                    f"{alias}再次回复",
                    f"{alias}再总结",
                    f"{alias}来收口",
                    f"{alias}收口一下",
                    f"{alias}来拍板",
                    f"{alias}最后总结",
                )
                if any(pattern in normalized_message for pattern in explicit_repeat_patterns):
                    targets.append(employee_id)
                    break
        return list(dict.fromkeys(targets))

    def _should_infer_semantic_repeat_recall(self, normalized_message: str) -> bool:
        repeat_semantic_markers = (
            "最后",
            "收口",
            "总结",
            "拍板",
            "再回",
            "再回复",
            "再次回复",
            "再总结",
            "最后你来",
            "最后还是",
        )
        return any(marker in normalized_message for marker in repeat_semantic_markers)

    def _infer_repeat_recall_target_ids(
        self,
        *,
        receiving_employee_id: str,
        user_message: str,
        channel_id: str,
        surface: ConversationSurface,
        chat_id: str,
        current_app_id: str,
        candidate_employee_ids: list[str],
    ) -> list[str]:
        dialogue_service = get_openclaw_dialogue_service()
        infer_method = getattr(dialogue_service, "infer_repeat_recall_targets", None)
        if not callable(infer_method):
            return []
        result = infer_method(
            employee_id=receiving_employee_id,
            user_message=user_message,
            channel_id=channel_id,
            surface=surface.value,
            conversation_history=self._build_channel_visible_history(
                surface=surface,
                chat_id=chat_id,
                current_app_id=current_app_id,
            ),
            candidate_employee_ids=candidate_employee_ids,
        )
        return [candidate.employee_id for candidate in result.targets]

    def _group_available_bot_ids(self) -> list[str]:
        return [binding.virtual_employee for binding in self._conversation.list_bot_seat_bindings()]

    def _build_collaboration_context(
        self,
        *,
        collaboration_intent: str | None,
        dispatch_targets: list[str],
        candidate_handoff_targets: list[str],
        spoken_bot_ids: list[str],
        available_bot_ids: list[str],
        visible_turn_count: int,
        dispatch_reason: str | None = None,
        last_committed_state: dict[str, Any] | None = None,
        pending_handoff: PendingHandoffState | None = None,
        interruption_mode: str | None = None,
        retry_reason: str | None = None,
        prior_reply_text: str | None = None,
    ) -> OpenClawCollaborationContext:
        unique_spoken = list(dict.fromkeys(spoken_bot_ids))
        remaining_bot_ids = [
            employee_id
            for employee_id in available_bot_ids
            if employee_id not in unique_spoken
        ]
        turn_limit = max(0, get_settings().feishu_visible_handoff_turn_limit)
        return OpenClawCollaborationContext(
            collaboration_intent=collaboration_intent,
            dispatch_targets=list(dict.fromkeys(dispatch_targets)),
            candidate_handoff_targets=list(dict.fromkeys(candidate_handoff_targets)),
            spoken_bot_ids=unique_spoken,
            remaining_bot_ids=remaining_bot_ids,
            visible_turn_count=visible_turn_count,
            remaining_turn_budget=max(turn_limit - visible_turn_count, 0),
            dispatch_reason=dispatch_reason,
            last_committed_state_summary=self._summarize_last_committed_state(last_committed_state or {}),
            pending_handoff_summary=self._summarize_pending_handoff(pending_handoff),
            interruption_mode=interruption_mode,
            retry_reason=retry_reason,
            prior_reply_text=prior_reply_text,
        )

    def _pending_handoff_dispatch_targets(self, thread: Any | None) -> list[str]:
        pending_handoff = getattr(thread, "pending_handoff", None)
        if pending_handoff is None or pending_handoff.status != "active":
            return []
        candidate_targets = [pending_handoff.source_agent_id, pending_handoff.target_agent_id]
        return [
            employee_id
            for employee_id in dict.fromkeys(candidate_targets)
            if employee_id and self._conversation.get_bot_binding_by_employee_id(employee_id) is not None
        ]

    def _ordered_group_dispatch_targets(
        self,
        *,
        current_employee_id: str,
        dispatch_target_ids: list[str],
        pending_handoff: PendingHandoffState | None,
        interruption_mode: bool,
    ) -> list[str]:
        ordered_targets = [employee_id for employee_id in dict.fromkeys(dispatch_target_ids) if employee_id]
        if not ordered_targets:
            return []

        if not interruption_mode:
            if current_employee_id in ordered_targets:
                return [
                    current_employee_id,
                    *[employee_id for employee_id in ordered_targets if employee_id != current_employee_id],
                ]
            return ordered_targets

        priority_targets: list[str] = []
        if pending_handoff is not None and pending_handoff.status == "active":
            priority_targets.extend([pending_handoff.source_agent_id, pending_handoff.target_agent_id])
        priority_targets.append(current_employee_id)
        return [
            employee_id
            for employee_id in dict.fromkeys([*priority_targets, *ordered_targets])
            if employee_id in ordered_targets
        ]

    def _dispatch_reason(
        self,
        *,
        dispatch_resolution_basis: str | None,
        used_pending_handoff: bool,
        interruption_reason: str | None,
    ) -> str | None:
        parts: list[str] = []
        if interruption_reason:
            parts.append(interruption_reason)
        if used_pending_handoff:
            parts.append("pending_handoff_thread_state")
        if dispatch_resolution_basis:
            parts.append(dispatch_resolution_basis)
        return "+".join(parts) or None

    def _update_thread_turn_state(
        self,
        *,
        thread_id: str,
        speaker_id: str,
        reply_text: str,
        handoff_targets: list[str],
        handoff_reason: str | None,
        runtrace_ref: str,
    ) -> None:
        thread = self._conversation.get_required_thread(thread_id)
        prior_pending_handoff = thread.pending_handoff
        next_state = self._derive_last_committed_state(
            prior_state=thread.last_committed_state,
            speaker_id=speaker_id,
            reply_text=reply_text,
            handoff_targets=handoff_targets,
            handoff_reason=handoff_reason,
            runtrace_ref=runtrace_ref,
        )
        next_pending_handoff = self._build_pending_handoff_state(
            source_agent_id=speaker_id,
            handoff_targets=handoff_targets,
            reply_text=reply_text,
            handoff_reason=handoff_reason,
            runtrace_ref=runtrace_ref,
        )
        self._conversation.set_last_committed_state(thread_id, next_state)
        self._conversation.set_pending_handoff(thread_id, next_pending_handoff)
        self._append_thread_state_events(
            thread_id=thread_id,
            runtrace_ref=runtrace_ref,
            prior_state=thread.last_committed_state,
            next_state=next_state,
            prior_pending_handoff=prior_pending_handoff,
            next_pending_handoff=next_pending_handoff,
        )

    def _build_pending_handoff_state(
        self,
        *,
        source_agent_id: str,
        handoff_targets: list[str],
        reply_text: str,
        handoff_reason: str | None,
        runtrace_ref: str,
    ) -> PendingHandoffState | None:
        if not handoff_targets:
            return None
        return PendingHandoffState(
            source_agent_id=source_agent_id,
            target_agent_id=handoff_targets[0],
            instruction=self._extract_state_instruction(reply_text=reply_text, handoff_reason=handoff_reason),
            reason=handoff_reason,
            source_runtrace_ref=runtrace_ref,
        )

    def _derive_last_committed_state(
        self,
        *,
        prior_state: dict[str, Any],
        speaker_id: str,
        reply_text: str,
        handoff_targets: list[str],
        handoff_reason: str | None,
        runtrace_ref: str,
    ) -> dict[str, Any]:
        next_state = dict(prior_state)
        instruction = self._extract_state_instruction(reply_text=reply_text, handoff_reason=handoff_reason)
        next_number = self._extract_next_expected_number(instruction, handoff_reason, reply_text)
        next_state.update(
            {
                "last_speaker": speaker_id,
                "last_visible_reply": reply_text.strip(),
                "last_instruction": instruction,
                "baton_owner": handoff_targets[0] if handoff_targets else speaker_id,
                "pending_handoff_targets": list(dict.fromkeys(handoff_targets)),
                "source_runtrace_ref": runtrace_ref,
            }
        )
        if next_number is not None:
            next_state["next_expected_number"] = next_number
            next_state.setdefault("game", "count7")
        return next_state

    def _extract_state_instruction(self, *, reply_text: str, handoff_reason: str | None) -> str | None:
        for candidate in (handoff_reason or "", reply_text):
            if not candidate:
                continue
            matched = re.search(r"((?:重新)?继续报\s*\d{1,4})", candidate, flags=re.IGNORECASE)
            if matched:
                return re.sub(r"\s+", "", matched.group(1))
            matched = re.search(r"(报\s*\d{1,4})", candidate, flags=re.IGNORECASE)
            if matched:
                normalized = re.sub(r"\s+", "", matched.group(1))
                return normalized if normalized.startswith("继续") else f"继续{normalized}"
        return handoff_reason.strip() if handoff_reason else None

    def _extract_next_expected_number(self, *candidates: str | None) -> int | None:
        for candidate in candidates:
            if not candidate:
                continue
            matched = re.search(r"(?:继续|重新继续)?报\s*(\d{1,4})", candidate, flags=re.IGNORECASE)
            if matched:
                return int(matched.group(1))
        return None

    def _summarize_last_committed_state(self, last_committed_state: dict[str, Any]) -> str | None:
        if not last_committed_state:
            return None
        return json.dumps(last_committed_state, ensure_ascii=False, sort_keys=True)

    def _summarize_pending_handoff(self, pending_handoff: PendingHandoffState | None) -> str | None:
        if pending_handoff is None:
            return None
        fields = [f"{pending_handoff.source_agent_id} -> {pending_handoff.target_agent_id}"]
        if pending_handoff.instruction:
            fields.append(f"instruction={pending_handoff.instruction}")
        if pending_handoff.reason:
            fields.append(f"reason={pending_handoff.reason}")
        if pending_handoff.source_runtrace_ref:
            fields.append(f"runtrace={pending_handoff.source_runtrace_ref}")
        return " | ".join(fields)

    def _append_thread_state_events(
        self,
        *,
        thread_id: str,
        runtrace_ref: str,
        prior_state: dict[str, Any],
        next_state: dict[str, Any],
        prior_pending_handoff: PendingHandoffState | None,
        next_pending_handoff: PendingHandoffState | None,
    ) -> None:
        control_plane = get_control_plane_service()
        if prior_state != next_state:
            control_plane.append_run_trace_event(
                runtrace_ref,
                RunEvent(
                    event_type="last_committed_state_updated",
                    message="Thread last committed state was updated after a visible bot turn.",
                    metadata={
                        "thread_id": thread_id,
                        "runtrace_id": runtrace_ref,
                        "state_summary": self._summarize_last_committed_state(next_state) or "{}",
                    },
                ),
            )
        if self._pending_handoff_signature(prior_pending_handoff) == self._pending_handoff_signature(next_pending_handoff):
            return
        if prior_pending_handoff is None and next_pending_handoff is not None:
            control_plane.append_run_trace_event(
                runtrace_ref,
                RunEvent(
                    event_type="pending_handoff_captured",
                    message="Thread pending handoff captured from the latest visible bot turn.",
                    metadata={
                        "thread_id": thread_id,
                        "runtrace_id": runtrace_ref,
                        "source_agent": next_pending_handoff.source_agent_id,
                        "target_agent": next_pending_handoff.target_agent_id,
                        "instruction": next_pending_handoff.instruction or "",
                    },
                ),
            )
            return
        if prior_pending_handoff is not None and next_pending_handoff is None:
            control_plane.append_run_trace_event(
                runtrace_ref,
                RunEvent(
                    event_type="pending_handoff_invalidated",
                    message="Thread pending handoff was cleared by the latest visible bot turn.",
                    metadata={
                        "thread_id": thread_id,
                        "runtrace_id": runtrace_ref,
                        "source_agent": prior_pending_handoff.source_agent_id,
                        "target_agent": prior_pending_handoff.target_agent_id,
                    },
                ),
            )
            return
        if prior_pending_handoff is not None and next_pending_handoff is not None:
            control_plane.append_run_trace_event(
                runtrace_ref,
                RunEvent(
                    event_type="pending_handoff_corrected",
                    message="Thread pending handoff was corrected by the latest visible bot turn.",
                    metadata={
                        "thread_id": thread_id,
                        "runtrace_id": runtrace_ref,
                        "source_agent": next_pending_handoff.source_agent_id,
                        "target_agent": next_pending_handoff.target_agent_id,
                        "corrected_instruction": next_pending_handoff.instruction or "",
                    },
                ),
            )

    def _pending_handoff_signature(self, pending_handoff: PendingHandoffState | None) -> tuple[str, ...] | None:
        if pending_handoff is None:
            return None
        return (
            pending_handoff.source_agent_id,
            pending_handoff.target_agent_id,
            pending_handoff.instruction or "",
            pending_handoff.reason or "",
            pending_handoff.source_runtrace_ref or "",
            pending_handoff.status,
        )

    def _should_infer_semantic_handoff(
        self,
        user_message: str,
        deterministic_text_target_ids: list[str],
        dispatch_target_ids: list[str],
    ) -> bool:
        if deterministic_text_target_ids:
            return False
        normalized_message = self._normalize_human_label(user_message)
        collaboration_hints = (
            "让产品",
            "让设计",
            "让研究",
            "让工程",
            "让质量",
            "请产品",
            "请设计",
            "请研究",
            "接棒",
            "判断",
            "评估",
            "需要产品",
            "需要设计",
            "需要研究",
            "需要工程",
            "需要质量",
            "need product",
            "need design",
            "need research",
            "need engineering",
            "product",
            "design",
            "research",
        )
        if any(hint in user_message.lower() for hint in collaboration_hints):
            return True
        return len(dispatch_target_ids) == 1 and any(token in normalized_message for token in ("判断", "评估", "意见"))

    def _infer_semantic_target_ids(
        self,
        *,
        receiving_employee_id: str,
        user_message: str,
        channel_id: str,
        surface: ConversationSurface,
        chat_id: str,
        current_app_id: str,
        candidate_employee_ids: list[str],
        allow_current_employee: bool = False,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        dialogue_service = get_openclaw_dialogue_service()
        infer_method = getattr(dialogue_service, "infer_visible_handoff_targets", None)
        if not callable(infer_method):
            return [], []

        candidate_employee_ids = [
            employee_id
            for employee_id in candidate_employee_ids
            if employee_id != receiving_employee_id or allow_current_employee
        ]
        if not candidate_employee_ids:
            return [], []

        history = self._build_channel_visible_history(
            surface=surface,
            chat_id=chat_id,
            current_app_id=current_app_id,
        )
        result = infer_method(
            employee_id=receiving_employee_id,
            user_message=user_message,
            channel_id=channel_id,
            surface=surface.value,
            conversation_history=history,
            candidate_employee_ids=candidate_employee_ids,
            allow_current_employee=allow_current_employee,
        )
        target_ids = [candidate.employee_id for candidate in result.targets]
        candidates = [
            {
                "employee_id": candidate.employee_id,
                "confidence": round(candidate.confidence, 4),
                "reason": candidate.reason,
            }
            for candidate in result.targets
        ]
        return target_ids, candidates

    def _infer_semantic_handoff_targets(
        self,
        *,
        receiving_employee_id: str,
        user_message: str,
        channel_id: str,
        surface: ConversationSurface,
        chat_id: str,
        current_app_id: str,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        return self._infer_semantic_target_ids(
            receiving_employee_id=receiving_employee_id,
            user_message=user_message,
            channel_id=channel_id,
            surface=surface,
            chat_id=chat_id,
            current_app_id=current_app_id,
            candidate_employee_ids=[
                binding.virtual_employee
                for binding in self._conversation.list_bot_seat_bindings()
                if binding.virtual_employee != receiving_employee_id
            ],
        )

    def _should_process_group_message(self, event: dict[str, Any], binding: Any) -> bool:
        return self._group_match_result(event, binding.virtual_employee).matched

    def _message_mentions(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        mentions = (event.get("message") or {}).get("mentions")
        parsed_mentions = [mention for mention in mentions if isinstance(mention, dict)] if mentions is not None else []
        parsed_mentions.extend(self._synthetic_mentions_from_content((event.get("message") or {}).get("content", "")))
        deduplicated: list[dict[str, Any]] = []
        seen: set[str] = set()
        for mention in parsed_mentions:
            signature = json.dumps(mention, ensure_ascii=False, sort_keys=True)
            if signature in seen:
                continue
            seen.add(signature)
            deduplicated.append(mention)
        return deduplicated

    def _build_channel_visible_history(
        self,
        *,
        surface: ConversationSurface,
        chat_id: str,
        current_app_id: str,
    ) -> str:
        entries: list[tuple[float, str]] = []
        for inbound in self._inbound.list():
            if inbound.surface != surface or inbound.chat_id != chat_id or not inbound.text:
                continue
            sender = inbound.sender_id or "unknown-user"
            entries.append((inbound.processed_at.timestamp(), f"[user:{sender}] {inbound.text}"))

        for outbound in self._outbound.list():
            if outbound.receive_id != chat_id:
                continue
            actor = "assistant" if outbound.app_id == current_app_id else f"visible-peer:{outbound.app_id}"
            entries.append((outbound.created_at.timestamp(), f"[{actor}] {outbound.text}"))

        if not entries:
            return ""
        entries.sort(key=lambda item: item[0])
        return "\n".join(text for _, text in entries[-12:])

    def _build_participants(
        self,
        event: dict[str, Any],
        receiving_employee_id: str,
        mentioned_agent_ids: list[str],
    ) -> list[str]:
        participants = [self._resolve_initiator(event), f"feishu-{receiving_employee_id}"]
        participants.extend(f"feishu-{agent_id}" for agent_id in mentioned_agent_ids if agent_id != receiving_employee_id)
        return list(dict.fromkeys(participants))

    def _resolve_initiator(self, event: dict[str, Any]) -> str:
        sender_id = self._sender_raw_id(event)
        if not sender_id:
            return "feishu-user:unknown"
        for binding in self._conversation.list_bot_seat_bindings():
            config = get_feishu_bot_app_config_by_employee_id(binding.virtual_employee)
            if config and sender_id in self._bot_identity_tokens(config):
                return f"feishu-{binding.virtual_employee}"
        return f"feishu-user:{sender_id}"

    def _sender_raw_id(self, event: dict[str, Any]) -> str | None:
        sender = event.get("sender", {})
        sender_id = sender.get("sender_id", {})
        return sender_id.get("open_id") or sender_id.get("user_id") or sender_id.get("union_id")

    def _compose_text_with_mentions(self, text: str, mention_employee_ids: list[str]) -> str:
        mention_prefixes: list[str] = []
        for employee_id in mention_employee_ids:
            config = get_feishu_bot_app_config_by_employee_id(employee_id)
            mention_user_id = self._mention_user_id(config) if config is not None else ""
            if config is None or not mention_user_id:
                continue
            display_name = config.display_name or employee_id
            mention_prefixes.append(f'<at user_id="{mention_user_id}">{display_name}</at>')
        if not mention_prefixes:
            return text
        return f"{' '.join(mention_prefixes)} {text}".strip()

    def _synthetic_mentions_from_content(self, content: str) -> list[dict[str, Any]]:
        if not content:
            return []
        text = content
        try:
            payload = json.loads(content)
            if isinstance(payload, dict):
                text = str(payload.get("text") or content)
        except json.JSONDecodeError:
            text = content
        mentions: list[dict[str, Any]] = []
        pattern = re.compile(
            r"<at\b[^>]*?(?:user_id|open_id|union_id)=['\"]([^'\"]+)['\"][^>]*>(.*?)</at>",
            re.IGNORECASE,
        )
        for match in pattern.finditer(text):
            mention_user_id = match.group(1).strip()
            mention_name = match.group(2).strip()
            if not mention_user_id:
                continue
            mentions.append({"id": {"user_id": mention_user_id}, "name": mention_name})
        return mentions

    def _summarize_mentions(self, mentions: list[dict[str, Any]]) -> list[str]:
        summaries: list[str] = []
        for mention in mentions:
            mention_id = mention.get("id") or {}
            parts = [
                f"open_id={mention_id.get('open_id') or ''}",
                f"user_id={mention_id.get('user_id') or ''}",
                f"union_id={mention_id.get('union_id') or ''}",
                f"key={mention.get('key') or ''}",
                f"name={mention.get('name') or ''}",
            ]
            summaries.append(" | ".join(parts))
        return summaries

    def _record_group_debug_event(
        self,
        *,
        app_id: str,
        header: dict[str, Any],
        event: dict[str, Any],
        message_id: str,
        surface: ConversationSurface,
        dispatch_mode: str | None,
        processed_status: str,
        dispatch_targets: list[str] | None = None,
        dispatch_resolution_basis: str | None = None,
        collaboration_intent: str | None = None,
        matched_employee_id: str | None = None,
        match_basis: str | None = None,
        target_agent_ids: list[str] | None = None,
        deterministic_name_target_ids: list[str] | None = None,
        semantic_dispatch_target_ids: list[str] | None = None,
        deterministic_text_target_ids: list[str] | None = None,
        semantic_handoff_target_ids: list[str] | None = None,
        semantic_handoff_candidates: list[dict[str, Any]] | None = None,
        target_resolution_basis: str | None = None,
        raw_mentions_summary: list[str] | None = None,
        detail: str | None = None,
    ) -> None:
        if surface != ConversationSurface.FEISHU_GROUP:
            return
        message = event.get("message") or {}
        self._group_debug.save(
            FeishuGroupDebugEventRecord(
                debug_event_id=self._record_id(app_id, message_id),
                message_id=message_id,
                event_id=header.get("event_id"),
                app_id=app_id,
                surface=surface,
                chat_id=message.get("chat_id") or "",
                sender_id=self._sender_raw_id(event),
                text=self._safe_extract_text(message.get("content", "")),
                raw_message_content=message.get("content"),
                raw_mentions=self._message_mentions(event),
                raw_mentions_summary=raw_mentions_summary or self._summarize_mentions(self._message_mentions(event)),
                dispatch_mode=dispatch_mode,
                dispatch_targets=dispatch_targets or [],
                dispatch_resolution_basis=dispatch_resolution_basis,
                collaboration_intent=collaboration_intent,
                target_agent_ids=target_agent_ids or [],
                deterministic_name_target_ids=deterministic_name_target_ids or [],
                semantic_dispatch_target_ids=semantic_dispatch_target_ids or [],
                deterministic_text_target_ids=deterministic_text_target_ids or [],
                semantic_handoff_target_ids=semantic_handoff_target_ids or [],
                semantic_handoff_candidates=semantic_handoff_candidates or [],
                matched_employee_id=matched_employee_id,
                match_basis=match_basis,
                target_resolution_basis=target_resolution_basis,
                processed_status=processed_status,
                detail=detail,
            )
        )

    def _safe_extract_text(self, content: str) -> str:
        try:
            return self._extract_text_intent(content)
        except Exception:
            return content or ""

    def _mention_targets_bot(
        self,
        mention: dict[str, Any],
        employee_id: str,
        app_config: FeishuBotAppConfig,
    ) -> bool:
        return self._match_mention_to_bot(mention, employee_id, app_config).matched

    def _group_match_result(self, event: dict[str, Any], employee_id: str) -> MentionMatchResult:
        mentions = self._message_mentions(event)
        if not mentions:
            return MentionMatchResult(False, "no_mentions")
        app_config = get_feishu_bot_app_config_by_employee_id(employee_id)
        if app_config is None:
            return MentionMatchResult(False, "missing_app_config")
        for mention in mentions:
            result = self._match_mention_to_bot(mention, employee_id, app_config)
            if result.matched:
                return result
        return MentionMatchResult(False, "no_match")

    def _match_mention_to_bot(
        self,
        mention: dict[str, Any],
        employee_id: str,
        app_config: FeishuBotAppConfig,
    ) -> MentionMatchResult:
        mention_id = mention.get("id") or {}
        candidate_ids = (
            ("open_id", (mention_id.get("open_id") or "").strip()),
            ("user_id", (mention_id.get("user_id") or "").strip()),
            ("union_id", (mention_id.get("union_id") or "").strip()),
            ("key", (mention.get("key") or "").strip()),
        )
        identity_tokens = self._bot_identity_tokens(app_config)
        for basis, candidate in candidate_ids:
            if candidate and candidate in identity_tokens:
                return MentionMatchResult(True, basis)

        mention_name = (mention.get("name") or "").strip()
        expected_name = (app_config.display_name or "").strip()
        if expected_name and mention_name and mention_name.casefold() == expected_name.casefold():
            return MentionMatchResult(True, "display_name_exact")

        normalized_mention_name = self._normalize_human_label(mention_name)
        if normalized_mention_name:
            normalized_display_name = self._normalize_human_label(expected_name)
            if normalized_display_name and normalized_mention_name == normalized_display_name:
                return MentionMatchResult(True, "normalized_display_name")
            if normalized_mention_name in self._bot_name_aliases(employee_id, app_config):
                return MentionMatchResult(True, "employee_alias")

        return MentionMatchResult(False, "no_match")

    def _bot_identity_tokens(self, app_config: FeishuBotAppConfig) -> set[str]:
        tokens = {
            (app_config.app_id or "").strip(),
            (app_config.bot_open_id or "").strip(),
            (app_config.bot_identity or "").strip(),
        }
        return {token for token in tokens if token}

    def _mention_user_id(self, app_config: FeishuBotAppConfig) -> str:
        return (app_config.bot_open_id or app_config.app_id or "").strip()

    def _bot_name_aliases(self, employee_id: str, app_config: FeishuBotAppConfig) -> set[str]:
        aliases = {
            self._normalize_human_label(app_config.display_name or ""),
            self._normalize_human_label(employee_id),
            self._normalize_human_label(employee_id.replace("-", " ").replace("_", " ")),
            self._normalize_human_label((app_config.display_name or "").removeprefix("OPC - ")),
            self._normalize_human_label((app_config.display_name or "").removeprefix("OPC-")),
            *{self._normalize_human_label(alias) for alias in ROLE_ALIAS_OVERRIDES.get(employee_id, ())},
        }
        return {alias for alias in aliases if alias}

    def _employee_aliases(self, employee_id: str) -> set[str]:
        aliases = {
            self._normalize_human_label(employee_id),
            self._normalize_human_label(employee_id.replace("-", " ").replace("_", " ")),
            *{self._normalize_human_label(alias) for alias in ROLE_ALIAS_OVERRIDES.get(employee_id, ())},
        }
        return {alias for alias in aliases if alias}

    def _department_hints_for_employee_ids(self, employee_ids: list[str]) -> list[str]:
        employee_department_map = {employee.employee_id: employee.department for employee in get_employees()}
        hints = [employee_department_map[employee_id] for employee_id in employee_ids if employee_id in employee_department_map]
        return list(dict.fromkeys(hints))

    def _target_resolution_basis(
        self,
        deterministic_text_target_ids: list[str],
        semantic_handoff_target_ids: list[str],
    ) -> str:
        if deterministic_text_target_ids and semantic_handoff_target_ids:
            return "merged"
        if deterministic_text_target_ids:
            return "deterministic_text"
        if semantic_handoff_target_ids:
            return "semantic_llm"
        return "explicit_mentions_only"

    def _dispatch_resolution_basis(
        self,
        explicit_target_ids: list[str],
        deterministic_name_target_ids: list[str],
        semantic_dispatch_target_ids: list[str],
    ) -> str:
        has_explicit = bool(explicit_target_ids)
        has_deterministic = bool(deterministic_name_target_ids)
        has_semantic = bool(semantic_dispatch_target_ids)
        active_origins = sum([has_explicit, has_deterministic, has_semantic])
        if active_origins > 1:
            return "merged"
        if has_explicit:
            return "explicit_mentions"
        if has_deterministic:
            return "deterministic_name"
        if has_semantic:
            return "semantic_dispatch"
        return "unresolved"

    def _group_dispatch_match_basis(
        self,
        *,
        employee_id: str,
        explicit_target_ids: list[str],
        explicit_match_basis: str | None,
        deterministic_name_target_ids: list[str],
        semantic_dispatch_target_ids: list[str],
    ) -> str:
        if employee_id in explicit_target_ids:
            return explicit_match_basis or "explicit_mentions"
        if employee_id in deterministic_name_target_ids:
            return "deterministic_name_dispatch"
        if employee_id in semantic_dispatch_target_ids:
            return "semantic_dispatch"
        return explicit_match_basis or "no_match"

    def _handoff_origin(
        self,
        *,
        deterministic_text_target_ids: list[str],
        semantic_handoff_target_ids: list[str],
        model_handoff_targets: list[str],
    ) -> str | None:
        has_deterministic = bool(deterministic_text_target_ids)
        has_semantic = bool(semantic_handoff_target_ids)
        has_model = bool(model_handoff_targets)
        active_origins = sum([has_deterministic, has_semantic, has_model])
        if active_origins > 1:
            return "merged"
        if has_deterministic:
            return "deterministic_text"
        if has_semantic:
            return "semantic_llm"
        if has_model:
            return "model_structured"
        return None

    def _handoff_resolution_basis(
        self,
        *,
        forced_handoff_targets: list[str],
        structured_handoff_targets: list[str],
        reply_name_targets: list[str],
        reply_semantic_handoff_targets: list[str],
    ) -> str | None:
        has_forced = bool(forced_handoff_targets)
        has_structured = bool(structured_handoff_targets)
        has_reply_name = bool(reply_name_targets)
        has_reply_semantic = bool(reply_semantic_handoff_targets)
        active_origins = sum([has_forced, has_structured, has_reply_name, has_reply_semantic])
        if active_origins > 1:
            return "merged"
        if has_forced:
            return "forced_handoff"
        if has_structured:
            return "model_structured"
        if has_reply_name:
            return "reply_name"
        if has_reply_semantic:
            return "reply_semantic"
        return None

    def _resolve_visible_handoff_targets(
        self,
        *,
        current_employee_id: str,
        reply_text: str,
        structured_handoff_targets: list[str],
        forced_handoff_targets: list[str],
        channel_id: str,
        surface: ConversationSurface,
        chat_id: str,
        current_app_id: str,
    ) -> tuple[str, list[str], list[str], list[str], str | None, bool]:
        reply_name_targets = [
            employee_id
            for employee_id in self._resolve_deterministic_name_targets(reply_text)
            if employee_id != current_employee_id
        ]
        reply_semantic_handoff_targets: list[str] = []
        if self._should_infer_semantic_handoff(
            reply_text,
            [*reply_name_targets, *structured_handoff_targets, *forced_handoff_targets],
            [],
        ):
            reply_semantic_handoff_targets, _ = self._infer_semantic_target_ids(
                receiving_employee_id=current_employee_id,
                user_message=reply_text,
                channel_id=channel_id,
                surface=surface,
                chat_id=chat_id,
                current_app_id=current_app_id,
                candidate_employee_ids=[
                    binding.virtual_employee
                    for binding in self._conversation.list_bot_seat_bindings()
                    if binding.virtual_employee != current_employee_id
                ],
            )
        final_handoff_targets = list(dict.fromkeys(reply_name_targets))
        naming_contract_violation = self._is_named_handoff_contract_violation(
            reply_text=reply_text,
            final_handoff_targets=final_handoff_targets,
            reply_name_targets=reply_name_targets,
            structured_handoff_targets=[
                *forced_handoff_targets,
                *structured_handoff_targets,
                *reply_semantic_handoff_targets,
            ],
        )
        return (
            reply_text,
            final_handoff_targets,
            reply_name_targets,
            reply_semantic_handoff_targets,
            self._handoff_resolution_basis(
                forced_handoff_targets=forced_handoff_targets,
                structured_handoff_targets=structured_handoff_targets,
                reply_name_targets=reply_name_targets,
                reply_semantic_handoff_targets=reply_semantic_handoff_targets,
            ),
            naming_contract_violation,
        )

    def _resolve_dialogue_handoff_targets(
        self,
        *,
        dialogue_service: Any,
        current_employee_id: str,
        dialogue_result: OpenClawChatResult,
        work_ticket_ref: str,
        user_message: str,
        forced_handoff_targets: list[str],
        channel_id: str,
        surface: ConversationSurface,
        chat_id: str,
        current_app_id: str,
        visible_participants: list[str],
        conversation_history: str | None,
        collaboration_context: OpenClawCollaborationContext | None,
        turn_mode: str,
        handoff_context: OpenClawHandoffContext | None = None,
    ) -> tuple[OpenClawChatResult, list[str], list[str], list[str], str | None, bool]:
        def resolve(
            result: OpenClawChatResult,
        ) -> tuple[str, list[str], list[str], list[str], str | None, bool]:
            return self._resolve_visible_handoff_targets(
                current_employee_id=current_employee_id,
                reply_text=result.reply_text,
                structured_handoff_targets=result.handoff_targets,
                forced_handoff_targets=forced_handoff_targets,
                channel_id=channel_id,
                surface=surface,
                chat_id=chat_id,
                current_app_id=current_app_id,
            )

        (
            reply_text,
            final_handoff_targets,
            reply_visible_named_targets,
            reply_semantic_handoff_targets,
            handoff_resolution_basis,
            handoff_name_contract_violation,
        ) = resolve(dialogue_result)
        content_contract_violation = self._is_handoff_contract_violation(
            dialogue_result.reply_text,
            list(dict.fromkeys([*forced_handoff_targets, *dialogue_result.handoff_targets])),
        )
        dialogue_result = dialogue_result.model_copy(update={"reply_text": reply_text})
        should_retry = handoff_name_contract_violation or content_contract_violation
        if not should_retry:
            return (
                dialogue_result,
                final_handoff_targets,
                reply_visible_named_targets,
                reply_semantic_handoff_targets,
                handoff_resolution_basis,
                False,
            )

        retry_collaboration_context = (
            collaboration_context.model_copy(
                update={
                    "retry_reason": "name_next_bot_in_visible_text",
                    "prior_reply_text": dialogue_result.reply_text,
                }
            )
            if collaboration_context is not None
            else None
        )
        retry_handoff_context = (
            handoff_context.model_copy(
                update={
                    "retry_reason": "name_next_bot_in_visible_text",
                    "prior_target_reply": dialogue_result.reply_text,
                }
            )
            if handoff_context is not None
            else None
        )
        retry_result = dialogue_service.generate_reply(
            employee_id=current_employee_id,
            user_message=user_message,
            work_ticket=get_control_plane_service().get_required_work_ticket(work_ticket_ref),
            channel_id=channel_id,
            surface=surface.value,
            app_id=current_app_id,
            visible_participants=visible_participants,
            conversation_history=conversation_history,
            forced_handoff_targets=forced_handoff_targets,
            turn_mode=turn_mode,
            handoff_context=retry_handoff_context,
            collaboration_context=retry_collaboration_context,
        )
        (
            reply_text,
            final_handoff_targets,
            reply_visible_named_targets,
            reply_semantic_handoff_targets,
            handoff_resolution_basis,
            handoff_name_contract_violation,
        ) = resolve(retry_result)
        retry_result = retry_result.model_copy(update={"reply_text": reply_text})
        final_contract_violation = handoff_name_contract_violation or self._is_handoff_contract_violation(
            retry_result.reply_text,
            list(dict.fromkeys([*forced_handoff_targets, *retry_result.handoff_targets])),
        )
        return (
            retry_result,
            final_handoff_targets,
            reply_visible_named_targets,
            reply_semantic_handoff_targets,
            handoff_resolution_basis,
            final_contract_violation,
        )

    def _is_handoff_contract_violation(self, reply_text: str, forced_handoff_targets: list[str]) -> bool:
        if not forced_handoff_targets:
            return False
        normalized = reply_text.casefold()
        return any(marker.casefold() in normalized for marker in HANDOFF_CONTRACT_VIOLATION_MARKERS)

    def _is_named_handoff_contract_violation(
        self,
        *,
        reply_text: str,
        final_handoff_targets: list[str],
        reply_name_targets: list[str],
        structured_handoff_targets: list[str],
    ) -> bool:
        normalized = self._normalize_human_label(reply_text)
        generic_handoff_request = any(marker in normalized for marker in GENERIC_HANDOFF_REPLY_MARKERS)
        if structured_handoff_targets and not reply_name_targets:
            return True
        if generic_handoff_request and not reply_name_targets and not structured_handoff_targets:
            return True
        return False

    def _is_handoff_repetition_violation(self, *, source_reply: str, target_reply: str) -> bool:
        normalized_source = self._normalize_visible_reply(source_reply)
        normalized_target = self._normalize_visible_reply(target_reply)
        if not normalized_source or not normalized_target:
            return False
        if normalized_source == normalized_target:
            return True
        similarity = SequenceMatcher(a=normalized_source, b=normalized_target).ratio()
        if similarity >= 0.86:
            return True
        return len(normalized_source) > 32 and (
            normalized_source in normalized_target or normalized_target in normalized_source
        )

    def _rewrite_visible_handoff_reply(
        self,
        *,
        source_employee_id: str,
        target_employee_ids: list[str],
    ) -> str:
        target_labels = ", ".join(self._human_employee_label(employee_id) for employee_id in target_employee_ids)
        source_label = self._human_employee_label(source_employee_id)
        return f"收到。{source_label} 先做当前问题的组织和 framing，并请 {target_labels} 在同一群里接棒补充。"

    def _rewrite_handoff_target_reply(self, *, target_employee_id: str, source_employee_id: str) -> str:
        target_label = self._human_employee_label(target_employee_id)
        source_label = self._human_employee_label(source_employee_id)
        try:
            pack = get_employee_pack_compiler().compile_employee_pack(target_employee_id)
            decision_lens = pack.role_contract.decision_lens[0] if pack.role_contract.decision_lens else pack.department
            deliverable = (
                pack.role_contract.preferred_deliverables[0]
                if pack.role_contract.preferred_deliverables
                else "role-specific analysis"
            )
            boundary = (
                pack.role_contract.role_boundaries[0]
                if pack.role_contract.role_boundaries
                else f"只回答 {target_label} 的职责范围"
            )
        except KeyError:
            decision_lens = target_label
            deliverable = "role-specific analysis"
            boundary = f"只回答 {target_label} 的职责范围"
        return (
            f"收到。作为 {target_label}，我补充 {decision_lens} 这一侧的判断。"
            f"我会围绕 {deliverable} 继续回应，并且 {boundary}，不重复 {source_label} 的组织和 framing。"
        )

    def _ensure_named_handoff_reply(self, reply_text: str, target_employee_ids: list[str]) -> str:
        named_targets = "、".join(self._human_employee_label(employee_id) for employee_id in target_employee_ids)
        suffix = f"下一位由 {named_targets} 回复。"
        if suffix in reply_text:
            return reply_text
        stripped = reply_text.strip()
        if not stripped:
            return suffix
        return f"{stripped}\n\n{suffix}"

    def _human_employee_label(self, employee_id: str) -> str:
        config = get_feishu_bot_app_config_by_employee_id(employee_id)
        display_name = (config.display_name if config else "") or employee_id
        normalized = re.sub(r"^OPC\s*[-–—:：]?\s*", "", display_name, flags=re.IGNORECASE).strip()
        return normalized or employee_id

    def _normalize_visible_reply(self, value: str) -> str:
        normalized = self._normalize_human_label(value)
        normalized = re.sub(r"[^\w\u4e00-\u9fff]+", "", normalized)
        return normalized

    def _normalize_human_label(self, value: str) -> str:
        if not value:
            return ""
        normalized = value.strip().casefold()
        normalized = re.sub(r"^opc\s*[-–—:：]?\s*", "", normalized)
        normalized = re.sub(r"[_\-–—:：./]+", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def _record_id(self, app_id: str, message_id: str) -> str:
        return f"{app_id}:{message_id}"

    def _build_idempotency_key(self, request: FeishuSendMessageRequest) -> str:
        payload = "|".join(
            [
                request.app_id,
                request.receive_id_type,
                request.chat_id,
                request.thread_ref or "",
                request.runtrace_ref or "",
                request.source_kind,
                ",".join(sorted(request.mention_employee_ids)),
                request.text,
            ]
        )
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    def _auto_reply_idempotency_key(
        self,
        *,
        app_id: str,
        message_id: str,
        source_kind: str,
        ordinal: int,
        text: str,
    ) -> str:
        payload = f"{app_id}|{message_id}|{source_kind}|{ordinal}|{text}"
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    def _find_successful_outbound(self, idempotency_key: str) -> FeishuOutboundMessageRecord | None:
        for record in reversed(self._outbound.list()):
            if record.idempotency_key == idempotency_key and record.status == "sent":
                return record
        return None

    def _delivery_guard_drop_reason(self, request: FeishuSendMessageRequest) -> str | None:
        if not request.thread_ref or not request.runtrace_ref:
            return None
        thread = self._conversation.get_thread(request.thread_ref)
        if thread is None:
            return None
        active_runtrace_ref = thread.active_runtrace_ref or thread.runtrace_ref
        if active_runtrace_ref and active_runtrace_ref != request.runtrace_ref:
            return "superseded_run"
        if request.delivery_guard_epoch is not None and thread.delivery_guard_epoch != request.delivery_guard_epoch:
            return "stale_epoch"
        return None

    def _get_required_outbound(self, outbound_id: str) -> FeishuOutboundMessageRecord:
        record = self._outbound.get(outbound_id)
        if record is None:
            raise KeyError(outbound_id)
        return record


_feishu_surface_adapter_service = FeishuSurfaceAdapterService(
    inbound_store=build_model_store(FeishuInboundEventRecord, "record_id", "feishu_inbound_events"),
    group_debug_store=build_model_store(FeishuGroupDebugEventRecord, "debug_event_id", "feishu_group_debug_events"),
    outbound_store=build_model_store(FeishuOutboundMessageRecord, "outbound_id", "feishu_outbound_messages"),
    conversation_service=get_conversation_service(),
)


def get_feishu_surface_adapter_service() -> FeishuSurfaceAdapterService:
    return _feishu_surface_adapter_service


def feishu_sdk_event_to_payload(event: Any) -> dict[str, Any]:
    def convert(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [convert(item) for item in value]
        if isinstance(value, dict):
            return {key: convert(item) for key, item in value.items()}
        if hasattr(value, "__dict__"):
            return {
                key: convert(item)
                for key, item in value.__dict__.items()
                if not key.startswith("_")
            }
        return value

    return convert(event)
