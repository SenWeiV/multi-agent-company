from __future__ import annotations

import json
import shutil
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from app.conversation.services import get_conversation_service
from app.core.config import get_settings
from app.control_plane.services import get_control_plane_service
from app.feishu.services import get_feishu_surface_adapter_service
from app.openclaw.models import (
    OpenClawControlUiTokenSetupView,
    OpenClawGatewayHealth,
    OpenClawGatewayRunView,
    OpenClawGatewayRunDetailView,
    OpenClawGatewaySessionView,
    OpenClawGatewaySessionDetailView,
    OpenClawHookConfigView,
    OpenClawHookEntryView,
    OpenClawOpsIssueView,
    OpenClawGatewayRuntimeModeView,
    OpenClawProvisionSyncResult,
    OpenClawRunEventView,
    OpenClawHookOverride,
    OpenClawHookUpdateRequest,
    OpenClawTranscriptEntryView,
)
from app.openclaw.services import get_openclaw_config_service, get_openclaw_provisioning_service

CONTAINER_RUNTIME_HOME = Path("/home/node/.openclaw")


class OpenClawRuntimeHomeMaterializer:
    def __init__(self) -> None:
        self._config_service = get_openclaw_config_service()
        self._provisioning_service = get_openclaw_provisioning_service()

    def sync(self) -> OpenClawProvisionSyncResult:
        runtime_home = self.runtime_home_path()
        config_root = runtime_home / "config"
        workspace_root = runtime_home / "workspace"
        agents_root = runtime_home / "agents"
        hooks_root = runtime_home / "hooks"

        for path in (runtime_home, config_root, workspace_root, agents_root, hooks_root):
            self._ensure_dir(path)

        active_employee_ids = {bundle.employee_id for bundle in self._provisioning_service.list_workspace_bundles()}
        self._cleanup_stale_agent_dirs(workspace_root, active_employee_ids)
        self._cleanup_stale_agent_dirs(agents_root, active_employee_ids)

        generated_file_count = 0
        for bundle in self._provisioning_service.list_workspace_bundles():
            workspace_dir = workspace_root / bundle.employee_id
            agent_dir = agents_root / bundle.employee_id
            self._ensure_dir(workspace_dir)
            self._ensure_dir(agent_dir)
            for workspace_file in bundle.bootstrap_files:
                self._write_file(workspace_dir / workspace_file.path, workspace_file.content)
                generated_file_count += 1

        config_payload = self._render_openclaw_config()
        rendered_config = json.dumps(config_payload, ensure_ascii=False, indent=2) + "\n"
        self._write_file(config_root / "openclaw.json", rendered_config)
        self._write_file(runtime_home / "openclaw.json", rendered_config)
        generated_file_count += 2

        self._write_file(
            hooks_root / "README.md",
            (
                "# OpenClaw Hooks\n\n"
                "Configured via `hooks.internal.entries` in `openclaw.json`.\n\n"
                "- bootstrap-extra-files: enabled\n"
                "- command-logger: enabled\n"
                "- session-memory: disabled\n"
                "- boot-md: disabled\n"
            ),
        )
        generated_file_count += 1

        return OpenClawProvisionSyncResult(
            runtime_home=str(runtime_home),
            config_path=str(config_root / "openclaw.json"),
            workspace_root=str(workspace_root),
            hooks_root=str(hooks_root),
            workspace_count=len(self._provisioning_service.list_workspace_bundles()),
            generated_file_count=generated_file_count,
            enabled_hooks=["bootstrap-extra-files", "command-logger"],
        )

    def runtime_home_path(self) -> Path:
        configured = Path(get_settings().openclaw_runtime_home)
        if configured.is_absolute():
            return configured
        return Path.cwd() / configured

    def _render_openclaw_config(self) -> dict:
        settings = get_settings()
        runtime_config = self._config_service.get_runtime_config()
        gateway_token = settings.openclaw_gateway_token or settings.openclaw_gateway_api_key
        default_agent_config = runtime_config.agents["defaults"]
        hooks_payload = self._hook_entries_payload()

        return {
            "gateway": {
                "mode": "local",
                "port": 18789,
                "bind": "lan",
                "auth": {
                    "mode": "token",
                    "token": gateway_token,
                },
                "controlUi": {
                    "allowedOrigins": [
                        f"http://127.0.0.1:{settings.openclaw_gateway_host_port}",
                        f"http://localhost:{settings.openclaw_gateway_host_port}",
                    ],
                    "allowInsecureAuth": True,
                    "dangerouslyDisableDeviceAuth": bool(
                        settings.openclaw_control_ui_auto_pair_local
                        and settings.app_env.strip().lower() != "production"
                    ),
                },
                "http": {
                    "endpoints": {
                        "chatCompletions": {
                            "enabled": True,
                        },
                    },
                },
            },
            "models": self._normalized_models_payload(runtime_config),
            "agents": {
                "defaults": default_agent_config.model_dump(mode="json"),
                "list": [
                    {
                        "id": binding.openclaw_agent_id,
                        "workspace": str(CONTAINER_RUNTIME_HOME / "workspace" / binding.employee_id),
                        "agentDir": str(CONTAINER_RUNTIME_HOME / "agents" / binding.employee_id),
                        "model": {
                            "primary": binding.primary_model_ref,
                        },
                    }
                    for binding in self._provisioning_service.list_agent_bindings()
                ],
            },
            "hooks": {
                "internal": {
                    "enabled": True,
                    "entries": hooks_payload,
                },
            },
            "skills": {
                "load": {
                    "watch": True,
                    "watchDebounceMs": 250,
                },
                "entries": {},
            },
        }

    def _hook_entries_payload(self) -> dict[str, dict]:
        defaults = {
            "bootstrap-extra-files": {
                "enabled": True,
                "paths": ["AGENTS.md", "IDENTITY.md", "SOUL.md", "SKILLS.md", "TOOLS.md", "HEARTBEAT.md", "USER.md"],
            },
            "command-logger": {
                "enabled": True,
            },
            "session-memory": {
                "enabled": False,
            },
            "boot-md": {
                "enabled": False,
            },
        }
        for override in get_openclaw_provisioning_service().list_hook_overrides():
            defaults[override.hook_id] = {
                "enabled": override.enabled,
                **override.config,
            }
        return defaults

    def _normalized_models_payload(self, runtime_config: object) -> dict:
        payload = runtime_config.models.model_dump(mode="json")
        for provider in payload.get("providers", {}).values():
            for model in provider.get("models", []):
                compat = model.get("compat") or {}
                thinking_format = compat.get("thinkingFormat")
                compat["thinkingFormat"] = self._normalize_thinking_format(model.get("id", ""), thinking_format)
                model["compat"] = compat
        return payload

    def _normalize_thinking_format(self, model_id: str, thinking_format: str | None) -> str:
        normalized = (thinking_format or "").strip().lower()
        if normalized in {"openai", "zai", "qwen"}:
            return normalized

        model_id_lower = model_id.lower()
        if normalized == "glm" or model_id_lower.startswith("glm-"):
            return "zai"
        if normalized == "kimi" or "kimi" in model_id_lower:
            return "openai"
        return "qwen" if "qwen" in model_id_lower else "openai"

    def _ensure_dir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o777)

    def _write_file(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        path.chmod(0o666)

    def _cleanup_stale_agent_dirs(self, root: Path, active_employee_ids: set[str]) -> None:
        if not root.exists():
            return
        for child in root.iterdir():
            if child.is_dir() and child.name not in active_employee_ids:
                shutil.rmtree(child, ignore_errors=True)


class OpenClawGatewayHealthService:
    def __init__(self, materializer: OpenClawRuntimeHomeMaterializer) -> None:
        self._materializer = materializer

    def get_runtime_mode_view(self) -> OpenClawGatewayRuntimeModeView:
        settings = get_settings()
        return OpenClawGatewayRuntimeModeView(
            runtime_mode=settings.openclaw_runtime_mode,
            gateway_base_url=settings.openclaw_gateway_base_url,
            control_ui_url=f"http://127.0.0.1:{settings.openclaw_gateway_host_port}/",
            runtime_home=str(self._materializer.runtime_home_path()),
        )

    def get_control_ui_token_setup_view(self) -> OpenClawControlUiTokenSetupView:
        settings = get_settings()
        runtime_mode = settings.openclaw_runtime_mode
        control_ui_url = f"http://127.0.0.1:{settings.openclaw_gateway_host_port}/"
        token = settings.openclaw_gateway_token or settings.openclaw_gateway_api_key
        token_env_key = "OPENCLAW_GATEWAY_TOKEN" if settings.openclaw_gateway_token else "OPENCLAW_GATEWAY_API_KEY"
        token_source = ".env"
        launch_url = "/openclaw-control-ui/launch"
        pairing_ready = bool(token and runtime_mode.strip().lower() == "gateway")

        steps = [
            "点击下面的按钮，Dashboard 会通过后端 launch 路由直接打开已经注入 token 的 Control UI。",
            "当前本机开发模式已启用 local auto-pair，避免 Docker 端口映射下的 browser device pairing 卡住首连。",
            "如果仍然看到 `gateway token missing`，先检查 app-dev 与 openclaw-gateway 是否加载了同一份 Gateway token。",
            "如果 Control UI 能打开但连接不上，优先检查 Gateway health 和本机 `127.0.0.1:18789` 是否可访问。",
        ]

        return OpenClawControlUiTokenSetupView(
            runtime_mode=runtime_mode,
            control_ui_url=control_ui_url,
            launch_url=launch_url,
            token_configured=bool(token),
            token_env_key=token_env_key,
            token_source=token_source,
            pairing_ready=pairing_ready,
            setup_steps=steps,
        )

    def build_control_ui_launch_url(self) -> str:
        settings = get_settings()
        token = settings.openclaw_gateway_token or settings.openclaw_gateway_api_key
        if not token:
            raise ValueError("OpenClaw gateway token is not configured.")

        control_ui_url = f"http://127.0.0.1:{settings.openclaw_gateway_host_port}/"
        fragment = urlencode(
            {
                "token": token,
            },
            quote_via=quote,
        )
        return f"{control_ui_url}#{fragment}"

    def list_session_views(
        self,
        *,
        search: str | None = None,
        surface: str | None = None,
        status: str | None = None,
    ) -> list[OpenClawGatewaySessionView]:
        threads = sorted(
            get_conversation_service().list_threads(),
            key=lambda thread: thread.created_at,
            reverse=True,
        )
        views = [
            OpenClawGatewaySessionView(
                thread_id=thread.thread_id,
                title=thread.title,
                surface=thread.surface.value,
                channel_id=thread.channel_id,
                status=thread.status,
                work_ticket_ref=thread.work_ticket_ref,
                runtrace_ref=thread.runtrace_ref,
                active_runtrace_ref=thread.active_runtrace_ref,
                bound_agent_ids=thread.bound_agent_ids,
                openclaw_session_refs=thread.openclaw_session_refs,
                visible_room_ref=thread.visible_room_ref,
                delivery_guard_epoch=thread.delivery_guard_epoch,
                pending_handoff_summary=self._pending_handoff_summary(thread.pending_handoff),
                last_committed_state_summary=self._state_summary(thread.last_committed_state),
            )
            for thread in threads
            if thread.openclaw_session_refs
        ]
        return self._filter_session_views(views, search=search, surface=surface, status=status)

    def get_session_detail(self, thread_id: str) -> OpenClawGatewaySessionDetailView:
        thread = get_conversation_service().get_thread(thread_id)
        if thread is None:
            raise KeyError(thread_id)

        transcript: list[OpenClawTranscriptEntryView] = []
        for inbound in get_feishu_surface_adapter_service().list_inbound_events():
            if inbound.thread_ref != thread.thread_id or not inbound.text:
                continue
            transcript.append(
                OpenClawTranscriptEntryView(
                    source="feishu_inbound",
                    actor=inbound.sender_id or "user",
                    text=inbound.text,
                    created_at=inbound.processed_at,
                    app_id=inbound.app_id,
                )
            )

        for outbound in get_feishu_surface_adapter_service().list_outbound_messages():
            if outbound.thread_ref != thread.thread_id:
                continue
            transcript.append(
                OpenClawTranscriptEntryView(
                    source="feishu_outbound",
                    actor=outbound.app_id,
                    text=outbound.text,
                    created_at=outbound.created_at,
                    app_id=outbound.app_id,
                    status=outbound.status,
                    source_kind=outbound.source_kind,
                    dropped_as_stale=outbound.dropped_as_stale,
                    stale_drop_reason=outbound.stale_drop_reason,
                )
            )

        transcript.sort(key=lambda item: item.created_at)
        recent_run_strategies: list[str] = []
        strategy_runtrace_ref = thread.active_runtrace_ref or thread.runtrace_ref
        if strategy_runtrace_ref:
            trace = get_control_plane_service().get_run_trace(strategy_runtrace_ref)
            if trace is not None:
                recent_run_strategies = list(
                    dict.fromkeys(
                        [
                            event.metadata.get("strategy", "")
                            for event in reversed(trace.events)
                            if (event.metadata or {}).get("strategy")
                        ]
                    )
                )[:4]

        return OpenClawGatewaySessionDetailView(
            thread_id=thread.thread_id,
            title=thread.title,
            surface=thread.surface.value,
            channel_id=thread.channel_id,
            status=thread.status,
            work_ticket_ref=thread.work_ticket_ref,
            runtrace_ref=thread.runtrace_ref,
            active_runtrace_ref=thread.active_runtrace_ref,
            taskgraph_ref=thread.taskgraph_ref,
            bound_agent_ids=thread.bound_agent_ids,
            participant_ids=thread.participant_ids,
            openclaw_session_refs=thread.openclaw_session_refs,
            visible_room_ref=thread.visible_room_ref,
            delivery_guard_epoch=thread.delivery_guard_epoch,
            superseded_runtrace_refs=thread.superseded_runtrace_refs,
            last_committed_state=thread.last_committed_state,
            pending_handoff=thread.pending_handoff.model_dump() if thread.pending_handoff is not None else None,
            transcript_count=len(transcript),
            last_transcript_at=transcript[-1].created_at if transcript else None,
            transcript=transcript[-20:],
            recent_run_strategies=recent_run_strategies,
        )

    def list_recent_native_runs(
        self,
        limit: int = 12,
        *,
        search: str | None = None,
        surface: str | None = None,
        status: str | None = None,
    ) -> list[OpenClawGatewayRunView]:
        run_views: list[OpenClawGatewayRunView] = []
        turn_limit = max(0, get_settings().feishu_visible_handoff_turn_limit)
        for trace in get_control_plane_service().list_run_traces():
            latest_native_event = None
            latest_handoff_event = None
            latest_handoff_reply_event = None
            handoff_count = 0
            for event in reversed(trace.events):
                metadata = event.metadata or {}
                strategy = metadata.get("strategy", "")
                model_ref = metadata.get("model_ref", "")
                if strategy.startswith("openclaw") or model_ref.startswith("openclaw:"):
                    latest_native_event = event
                if event.event_type == "visible_agent_handoff" and latest_handoff_event is None:
                    latest_handoff_event = event
                if event.event_type == "handoff_target_dialogue_generated" and latest_handoff_reply_event is None:
                    latest_handoff_reply_event = event
                if event.event_type == "visible_agent_handoff":
                    handoff_count += 1
                if latest_native_event is not None and latest_handoff_event is not None and latest_handoff_reply_event is not None:
                    break

            if latest_native_event is None:
                continue

            handoff_targets = []
            handoff_source_agent = None
            handoff_reason = None
            handoff_origin = trace.handoff_origin
            handoff_resolution_basis = None
            collaboration_intent = trace.collaboration_intent
            structured_handoff_targets: list[str] = []
            reply_visible_named_targets: list[str] = list(trace.reply_visible_named_targets)
            reply_name_targets: list[str] = []
            reply_semantic_handoff_targets: list[str] = []
            final_handoff_targets: list[str] = []
            spoken_bot_ids: list[str] = list(trace.spoken_bot_ids)
            remaining_bot_ids: list[str] = list(trace.remaining_bot_ids)
            remaining_turn_budget = trace.remaining_turn_budget
            stop_reason = trace.stop_reason
            latest_turn_mode = None
            if latest_handoff_event is not None:
                metadata = latest_handoff_event.metadata or {}
                handoff_targets = [
                    target.strip()
                    for target in (metadata.get("handoff_targets") or "").split(",")
                    if target.strip()
                ]
                handoff_source_agent = metadata.get("handoff_source_agent") or None
                handoff_reason = metadata.get("handoff_reason") or None
                handoff_origin = metadata.get("handoff_origin") or handoff_origin
                handoff_resolution_basis = metadata.get("handoff_resolution_basis") or handoff_resolution_basis
                structured_handoff_targets = [
                    target.strip()
                    for target in (metadata.get("structured_handoff_targets") or "").split(",")
                    if target.strip()
                ]
                reply_visible_named_targets = [
                    target.strip()
                    for target in (metadata.get("reply_visible_named_targets") or "").split(",")
                    if target.strip()
                ] or reply_visible_named_targets
                reply_name_targets = [
                    target.strip()
                    for target in (metadata.get("reply_name_targets") or "").split(",")
                    if target.strip()
                ]
                reply_semantic_handoff_targets = [
                    target.strip()
                    for target in (metadata.get("reply_semantic_handoff_targets") or "").split(",")
                    if target.strip()
                ]
                final_handoff_targets = [
                    target.strip()
                    for target in (metadata.get("final_handoff_targets") or "").split(",")
                    if target.strip()
                ]
            if latest_handoff_reply_event is not None:
                metadata = latest_handoff_reply_event.metadata or {}
                latest_turn_mode = metadata.get("turn_mode") or None
                handoff_resolution_basis = metadata.get("handoff_resolution_basis") or handoff_resolution_basis
                if not structured_handoff_targets:
                    structured_handoff_targets = [
                        target.strip()
                        for target in (metadata.get("structured_handoff_targets") or "").split(",")
                        if target.strip()
                    ]
                if not reply_visible_named_targets:
                    reply_visible_named_targets = [
                        target.strip()
                        for target in (metadata.get("reply_visible_named_targets") or "").split(",")
                        if target.strip()
                    ]
                if not reply_name_targets:
                    reply_name_targets = [
                        target.strip()
                        for target in (metadata.get("reply_name_targets") or "").split(",")
                        if target.strip()
                    ]
                if not reply_semantic_handoff_targets:
                    reply_semantic_handoff_targets = [
                        target.strip()
                        for target in (metadata.get("reply_semantic_handoff_targets") or "").split(",")
                        if target.strip()
                    ]
                if not final_handoff_targets:
                    final_handoff_targets = [
                        target.strip()
                        for target in (metadata.get("final_handoff_targets") or "").split(",")
                        if target.strip()
                    ]

            handoff_resolution_basis = handoff_resolution_basis or trace.handoff_resolution_basis
            run_views.append(
                OpenClawGatewayRunView(
                    runtrace_id=trace.runtrace_id,
                    work_ticket_ref=trace.work_ticket_ref,
                    thread_ref=trace.thread_ref,
                    surface=trace.surface,
                    interaction_mode=trace.interaction_mode.value,
                    status=trace.status.value,
                    model_ref=latest_native_event.metadata.get("model_ref", "unknown"),
                    strategy=latest_native_event.metadata.get("strategy", "unknown"),
                    session_refs=self._session_refs_for_thread(trace.thread_ref),
                    handoff_count=handoff_count,
                    latest_handoff_targets=handoff_targets,
                    latest_handoff_source_agent=handoff_source_agent,
                    latest_handoff_reason=handoff_reason,
                    handoff_origin=handoff_origin,
                    handoff_resolution_basis=handoff_resolution_basis,
                    collaboration_intent=collaboration_intent,
                    structured_handoff_targets=structured_handoff_targets,
                    reply_visible_named_targets=reply_visible_named_targets,
                    reply_name_targets=reply_name_targets,
                    reply_semantic_handoff_targets=reply_semantic_handoff_targets,
                    final_handoff_targets=final_handoff_targets,
                    handoff_contract_violation=trace.handoff_contract_violation,
                    handoff_repetition_violation=trace.handoff_repetition_violation,
                    supersedes_runtrace_ref=trace.supersedes_runtrace_ref,
                    superseded_by_runtrace_ref=trace.superseded_by_runtrace_ref,
                    visible_turn_count=trace.visible_turn_count,
                    delivery_guard_epoch=trace.delivery_guard_epoch,
                    interruption_reason=trace.interruption_reason,
                    interruption_dispatch_targets=trace.interruption_dispatch_targets,
                    spoken_bot_ids=spoken_bot_ids,
                    remaining_bot_ids=remaining_bot_ids,
                    remaining_turn_budget=remaining_turn_budget or max(turn_limit - trace.visible_turn_count, 0),
                    stop_reason=stop_reason,
                    stopped_by_turn_limit=trace.stopped_by_turn_limit,
                    latest_turn_mode=latest_turn_mode,
                    last_event_at=latest_native_event.created_at,
                    error_detail=(latest_native_event.metadata or {}).get("error_detail") or None,
                )
            )

        run_views = self._filter_run_views(run_views, search=search, surface=surface, status=status)
        run_views.sort(key=lambda item: item.last_event_at, reverse=True)
        return run_views[:limit]

    def get_run_detail(self, runtrace_id: str) -> OpenClawGatewayRunDetailView:
        trace = get_control_plane_service().get_run_trace(runtrace_id)
        if trace is None:
            raise KeyError(runtrace_id)

        model_ref = "unknown"
        strategy = "unknown"
        error_detail: str | None = None
        for event in reversed(trace.events):
            metadata = event.metadata or {}
            if metadata.get("model_ref"):
                model_ref = metadata.get("model_ref", model_ref)
            if metadata.get("strategy"):
                strategy = metadata.get("strategy", strategy)
            if metadata.get("error_detail"):
                error_detail = metadata.get("error_detail") or error_detail
            if model_ref != "unknown" and strategy != "unknown":
                break

        last_event_at = trace.events[-1].created_at if trace.events else self._now()
        handoff_origin = trace.handoff_origin
        handoff_resolution_basis = None
        collaboration_intent = trace.collaboration_intent
        latest_turn_mode = None
        handoff_source_reply = None
        handoff_target_reply = None
        structured_handoff_targets: list[str] = []
        reply_visible_named_targets: list[str] = list(trace.reply_visible_named_targets)
        reply_name_targets: list[str] = []
        reply_semantic_handoff_targets: list[str] = []
        final_handoff_targets: list[str] = []
        spoken_bot_ids: list[str] = list(trace.spoken_bot_ids)
        remaining_bot_ids: list[str] = list(trace.remaining_bot_ids)
        remaining_turn_budget = trace.remaining_turn_budget
        stop_reason = trace.stop_reason
        for event in reversed(trace.events):
            metadata = event.metadata or {}
            if handoff_origin is None and event.event_type == "visible_agent_handoff":
                handoff_origin = metadata.get("handoff_origin") or None
            if handoff_resolution_basis is None:
                handoff_resolution_basis = metadata.get("handoff_resolution_basis") or None
            if handoff_origin is not None and handoff_resolution_basis is not None:
                break
        for event in reversed(trace.events):
            if event.event_type != "handoff_target_dialogue_generated":
                continue
            metadata = event.metadata or {}
            latest_turn_mode = metadata.get("turn_mode") or latest_turn_mode
            handoff_source_reply = metadata.get("handoff_source_reply") or handoff_source_reply
            handoff_target_reply = metadata.get("handoff_target_reply") or handoff_target_reply
            structured_handoff_targets = [
                target.strip()
                for target in (metadata.get("structured_handoff_targets") or "").split(",")
                if target.strip()
            ]
            reply_visible_named_targets = [
                target.strip()
                for target in (metadata.get("reply_visible_named_targets") or "").split(",")
                if target.strip()
            ] or reply_visible_named_targets
            reply_name_targets = [
                target.strip()
                for target in (metadata.get("reply_name_targets") or "").split(",")
                if target.strip()
            ]
            reply_semantic_handoff_targets = [
                target.strip()
                for target in (metadata.get("reply_semantic_handoff_targets") or "").split(",")
                if target.strip()
            ]
            final_handoff_targets = [
                target.strip()
                for target in (metadata.get("final_handoff_targets") or "").split(",")
                if target.strip()
            ]
            break
        if not final_handoff_targets:
            for event in reversed(trace.events):
                if event.event_type != "visible_agent_handoff":
                    continue
                metadata = event.metadata or {}
                structured_handoff_targets = structured_handoff_targets or [
                    target.strip()
                    for target in (metadata.get("structured_handoff_targets") or "").split(",")
                    if target.strip()
                ]
                reply_visible_named_targets = reply_visible_named_targets or [
                    target.strip()
                    for target in (metadata.get("reply_visible_named_targets") or "").split(",")
                    if target.strip()
                ]
                reply_name_targets = reply_name_targets or [
                    target.strip()
                    for target in (metadata.get("reply_name_targets") or "").split(",")
                    if target.strip()
                ]
                reply_semantic_handoff_targets = reply_semantic_handoff_targets or [
                    target.strip()
                    for target in (metadata.get("reply_semantic_handoff_targets") or "").split(",")
                    if target.strip()
                ]
                final_handoff_targets = [
                    target.strip()
                    for target in (metadata.get("final_handoff_targets") or "").split(",")
                    if target.strip()
                ]
                if final_handoff_targets:
                    break
        handoff_resolution_basis = handoff_resolution_basis or trace.handoff_resolution_basis
        turn_limit = max(0, get_settings().feishu_visible_handoff_turn_limit)
        handoff_count = sum(1 for event in trace.events if event.event_type == "visible_agent_handoff")
        return OpenClawGatewayRunDetailView(
            runtrace_id=trace.runtrace_id,
            work_ticket_ref=trace.work_ticket_ref,
            thread_ref=trace.thread_ref,
            taskgraph_ref=trace.taskgraph_ref,
            surface=trace.surface,
            interaction_mode=trace.interaction_mode.value,
            status=trace.status.value,
            trigger_type=trace.trigger_type.value,
            model_ref=model_ref,
            strategy=strategy,
            dispatch_targets=trace.dispatch_targets,
            agent_turn_refs=trace.agent_turn_refs,
            activated_departments=trace.activated_departments,
            visible_speakers=trace.visible_speakers,
            session_refs=self._session_refs_for_thread(trace.thread_ref),
            handoff_origin=handoff_origin,
            handoff_resolution_basis=handoff_resolution_basis,
            collaboration_intent=collaboration_intent,
            structured_handoff_targets=structured_handoff_targets,
            reply_visible_named_targets=reply_visible_named_targets,
            reply_name_targets=reply_name_targets,
            reply_semantic_handoff_targets=reply_semantic_handoff_targets,
            final_handoff_targets=final_handoff_targets,
            handoff_contract_violation=trace.handoff_contract_violation,
            handoff_repetition_violation=trace.handoff_repetition_violation,
            supersedes_runtrace_ref=trace.supersedes_runtrace_ref,
            superseded_by_runtrace_ref=trace.superseded_by_runtrace_ref,
            visible_turn_count=trace.visible_turn_count,
            delivery_guard_epoch=trace.delivery_guard_epoch,
            interruption_reason=trace.interruption_reason,
            interruption_dispatch_targets=trace.interruption_dispatch_targets,
            spoken_bot_ids=spoken_bot_ids,
            remaining_bot_ids=remaining_bot_ids,
            remaining_turn_budget=remaining_turn_budget or max(turn_limit - trace.visible_turn_count, 0),
            stop_reason=stop_reason,
            stopped_by_turn_limit=trace.stopped_by_turn_limit,
            latest_turn_mode=latest_turn_mode,
            handoff_source_reply=handoff_source_reply,
            handoff_target_reply=handoff_target_reply,
            last_event_at=last_event_at,
            event_count=len(trace.events),
            error_detail=error_detail,
            events=[
                OpenClawRunEventView(
                    event_type=event.event_type,
                    message=event.message,
                    created_at=event.created_at,
                    metadata=event.metadata,
                )
                for event in trace.events[-20:]
            ],
        )

    def _state_summary(self, payload: dict[str, object]) -> str | None:
        if not payload:
            return None
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def _pending_handoff_summary(self, pending_handoff: object | None) -> str | None:
        if pending_handoff is None:
            return None
        if hasattr(pending_handoff, "source_agent_id") and hasattr(pending_handoff, "target_agent_id"):
            source_agent_id = getattr(pending_handoff, "source_agent_id", "")
            target_agent_id = getattr(pending_handoff, "target_agent_id", "")
            instruction = getattr(pending_handoff, "instruction", None)
            reason = getattr(pending_handoff, "reason", None)
            pieces = [f"{source_agent_id} -> {target_agent_id}"]
            if instruction:
                pieces.append(f"instruction={instruction}")
            if reason:
                pieces.append(f"reason={reason}")
            return " | ".join(pieces)
        return str(pending_handoff)

    def list_ops_issues(self, limit: int = 10) -> list[OpenClawOpsIssueView]:
        issues: list[OpenClawOpsIssueView] = []
        gateway_health = self.health()
        if gateway_health.status != "healthy":
            issues.append(
                OpenClawOpsIssueView(
                    source="openclaw_gateway",
                    severity="high",
                    title="OpenClaw Gateway unhealthy",
                    detail=gateway_health.error_detail or gateway_health.status,
                    ref=gateway_health.gateway_base_url,
                )
            )

        for run in self.list_recent_native_runs(limit=limit):
            if not run.error_detail:
                continue
            issues.append(
                OpenClawOpsIssueView(
                    source="openclaw_runtime",
                    severity="medium",
                    title=f"{run.strategy} on {run.work_ticket_ref}",
                    detail=run.error_detail,
                    ref=run.runtrace_id,
                )
            )

        for outbound in get_feishu_surface_adapter_service().list_outbound_messages():
            if outbound.replayed_by_outbound_ref:
                continue
            if outbound.status == "failed":
                issues.append(
                    OpenClawOpsIssueView(
                        source="feishu_delivery",
                        severity="medium",
                        title=f"Feishu outbound failed for {outbound.receive_id}",
                        detail=outbound.error_detail or "unknown error",
                        ref=outbound.outbound_id,
                    )
                )
                continue
            if outbound.status == "dropped_stale":
                issues.append(
                    OpenClawOpsIssueView(
                        source="feishu_delivery",
                        severity="low",
                        title=f"Feishu outbound dropped as stale for {outbound.receive_id}",
                        detail=outbound.stale_drop_reason or "stale_reply_dropped",
                        ref=outbound.outbound_id,
                    )
                )

        issues.sort(key=lambda item: item.created_at, reverse=True)
        return issues[:limit]

    def get_hook_config_view(self) -> OpenClawHookConfigView:
        runtime_home = self._materializer.runtime_home_path()
        config_path = runtime_home / "config" / "openclaw.json"
        entries: list[OpenClawHookEntryView] = []
        internal_enabled = False

        if config_path.exists():
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            internal = ((payload.get("hooks") or {}).get("internal") or {})
            internal_enabled = bool(internal.get("enabled"))
            raw_entries = internal.get("entries") or {}
            entries = [
                OpenClawHookEntryView(
                    hook_id=hook_id,
                    enabled=bool(config.get("enabled")),
                    config={key: value for key, value in config.items() if key != "enabled"},
                )
                for hook_id, config in raw_entries.items()
            ]

        return OpenClawHookConfigView(
            runtime_home=str(runtime_home),
            config_path=str(config_path),
            internal_enabled=internal_enabled,
            entries=entries,
        )

    def update_hook_override(self, hook_id: str, request: OpenClawHookUpdateRequest) -> OpenClawHookEntryView:
        override = get_openclaw_provisioning_service().save_hook_override(
            OpenClawHookOverride(
                hook_id=hook_id,
                enabled=request.enabled,
                config=request.config,
            )
        )
        self._materializer.sync()
        return OpenClawHookEntryView(
            hook_id=override.hook_id,
            enabled=override.enabled,
            source="internal",
            config=override.config,
        )

    def health(self) -> OpenClawGatewayHealth:
        settings = get_settings()
        runtime_home = self._materializer.runtime_home_path()
        config_path = runtime_home / "config" / "openclaw.json"
        base_url = settings.openclaw_gateway_base_url.rstrip("/")
        control_ui_url = f"http://127.0.0.1:{settings.openclaw_gateway_host_port}/"
        active_session_refs = sum(
            len(thread.openclaw_session_refs)
            for thread in get_conversation_service().list_threads()
        )

        if settings.openclaw_runtime_mode.strip().lower() != "gateway":
            return OpenClawGatewayHealth(
                status="compat_mode",
                runtime_mode=settings.openclaw_runtime_mode,
                gateway_base_url=base_url,
                control_ui_url=control_ui_url,
                runtime_home=str(runtime_home),
                config_path=str(config_path),
                config_exists=config_path.exists(),
                reachable=False,
                active_session_refs=active_session_refs,
            )

        if not base_url:
            return OpenClawGatewayHealth(
                status="gateway_not_configured",
                runtime_mode=settings.openclaw_runtime_mode,
                gateway_base_url=base_url,
                control_ui_url=control_ui_url,
                runtime_home=str(runtime_home),
                config_path=str(config_path),
                config_exists=config_path.exists(),
                reachable=False,
                active_session_refs=active_session_refs,
                error_detail="OPENCLAW_GATEWAY_BASE_URL is empty",
            )

        try:
            with urlopen(f"{base_url}/healthz", timeout=5) as response:
                response.read()
                healthy = response.status == 200
        except HTTPError as exc:
            return OpenClawGatewayHealth(
                status="gateway_unhealthy",
                runtime_mode=settings.openclaw_runtime_mode,
                gateway_base_url=base_url,
                control_ui_url=control_ui_url,
                runtime_home=str(runtime_home),
                config_path=str(config_path),
                config_exists=config_path.exists(),
                reachable=False,
                active_session_refs=active_session_refs,
                error_detail=f"{exc.code}: {exc.reason}",
            )
        except URLError as exc:
            return OpenClawGatewayHealth(
                status="gateway_unreachable",
                runtime_mode=settings.openclaw_runtime_mode,
                gateway_base_url=base_url,
                control_ui_url=control_ui_url,
                runtime_home=str(runtime_home),
                config_path=str(config_path),
                config_exists=config_path.exists(),
                reachable=False,
                active_session_refs=active_session_refs,
                error_detail=str(exc.reason),
            )

        return OpenClawGatewayHealth(
            status="healthy" if healthy else "gateway_unhealthy",
            runtime_mode=settings.openclaw_runtime_mode,
            gateway_base_url=base_url,
            control_ui_url=control_ui_url,
            runtime_home=str(runtime_home),
            config_path=str(config_path),
            config_exists=config_path.exists(),
            reachable=healthy,
            active_session_refs=active_session_refs,
        )

    def _session_refs_for_thread(self, thread_ref: str | None) -> dict[str, str]:
        if not thread_ref:
            return {}
        thread = get_conversation_service().get_thread(thread_ref)
        if thread is None:
            return {}
        return thread.openclaw_session_refs

    def _filter_session_views(
        self,
        views: list[OpenClawGatewaySessionView],
        *,
        search: str | None,
        surface: str | None,
        status: str | None,
    ) -> list[OpenClawGatewaySessionView]:
        filtered = views
        if surface:
            filtered = [view for view in filtered if view.surface == surface]
        if status:
            filtered = [view for view in filtered if view.status == status]
        if search:
            needle = search.strip().lower()
            filtered = [
                view
                for view in filtered
                if needle in " ".join(
                    [
                        view.thread_id,
                        view.title,
                        view.channel_id,
                        view.work_ticket_ref or "",
                        ",".join(view.bound_agent_ids),
                        ",".join(view.openclaw_session_refs.values()),
                    ]
                ).lower()
            ]
        return filtered

    def _filter_run_views(
        self,
        views: list[OpenClawGatewayRunView],
        *,
        search: str | None,
        surface: str | None,
        status: str | None,
    ) -> list[OpenClawGatewayRunView]:
        filtered = views
        if surface:
            filtered = [view for view in filtered if view.surface == surface]
        if status:
            filtered = [view for view in filtered if view.status == status]
        if search:
            needle = search.strip().lower()
            filtered = [
                view
                for view in filtered
                if needle in " ".join(
                    [
                        view.runtrace_id,
                        view.work_ticket_ref,
                        view.thread_ref or "",
                        view.model_ref,
                        view.strategy,
                        view.surface,
                        view.interaction_mode,
                    ]
                ).lower()
            ]
        return filtered

    def _now(self):
        from datetime import UTC, datetime

        return datetime.now(UTC)


_openclaw_runtime_home_materializer = OpenClawRuntimeHomeMaterializer()
_openclaw_gateway_health_service = OpenClawGatewayHealthService(_openclaw_runtime_home_materializer)


def get_openclaw_runtime_home_materializer() -> OpenClawRuntimeHomeMaterializer:
    return _openclaw_runtime_home_materializer


def get_openclaw_gateway_health_service() -> OpenClawGatewayHealthService:
    return _openclaw_gateway_health_service


def main() -> None:
    result = get_openclaw_runtime_home_materializer().sync()
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
