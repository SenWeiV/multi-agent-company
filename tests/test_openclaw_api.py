from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.company.models import WorkTicket
from app.conversation.models import PendingHandoffState
from app.conversation.services import get_conversation_service
from app.core.config import get_settings
from app.control_plane.models import RunEvent
from app.control_plane.services import get_control_plane_service
from app.main import app
from app.openclaw.services import get_openclaw_gateway_adapter

client = TestClient(app)


def test_openclaw_agent_config_compiles_model_identity_and_soul() -> None:
    response = client.get("/api/v1/openclaw/agents/chief-of-staff")

    assert response.status_code == 200
    payload = response.json()
    assert payload["employee_id"] == "chief-of-staff"
    assert payload["primary_model_ref"] == "bailian/kimi-k2.5"
    assert payload["provider_name"] == "bailian"
    assert payload["model_id"] == "kimi-k2.5"
    assert "One-Person Company" in payload["identity_profile"]["identity"]
    assert payload["identity_profile"]["soul"]
    assert "Studio Producer" in payload["source_persona_roles"]


def test_openclaw_agent_list_contains_product_lead() -> None:
    response = client.get("/api/v1/openclaw/agents")

    assert response.status_code == 200
    payload = response.json()
    employee_ids = {agent["employee_id"] for agent in payload}
    assert employee_ids == {
        "chief-of-staff",
        "product-lead",
        "research-lead",
        "delivery-lead",
        "design-lead",
        "engineering-lead",
        "quality-lead",
    }


def test_openclaw_core_agents_have_distinct_role_contracts() -> None:
    product = client.get("/api/v1/openclaw/agents/product-lead")
    design = client.get("/api/v1/openclaw/agents/design-lead")

    assert product.status_code == 200
    assert design.status_code == 200

    product_payload = product.json()
    design_payload = design.json()

    assert product_payload["identity_profile"]["decision_lens"]
    assert design_payload["identity_profile"]["decision_lens"]
    assert product_payload["identity_profile"]["decision_lens"] != design_payload["identity_profile"]["decision_lens"]
    assert product_payload["identity_profile"]["role_boundaries"] != design_payload["identity_profile"]["role_boundaries"]
    assert any("优先级" in item or "范围" in item for item in product_payload["identity_profile"]["decision_lens"])
    assert any("体验" in item or "交互" in item for item in design_payload["identity_profile"]["decision_lens"])


def test_openclaw_binding_and_workspace_bundle_are_exposed() -> None:
    binding_response = client.get("/api/v1/openclaw/bindings/chief-of-staff")
    bundle_response = client.get("/api/v1/openclaw/workspace-bundles/chief-of-staff")

    assert binding_response.status_code == 200
    assert bundle_response.status_code == 200

    binding = binding_response.json()
    bundle = bundle_response.json()

    assert binding["employee_id"] == "chief-of-staff"
    assert binding["openclaw_agent_id"] == "opc-chief-of-staff"
    assert binding["tool_profile"] == "coordination/messaging"
    assert bundle["workspace_path"].endswith("/chief-of-staff")
    assert any(file["path"] == "SOUL.md" for file in bundle["bootstrap_files"])
    assert any(file["path"] == "SKILLS.md" for file in bundle["bootstrap_files"])
    assert any(file["path"] == "TOOLS.md" for file in bundle["bootstrap_files"])
    identity_file = next(file for file in bundle["bootstrap_files"] if file["path"] == "IDENTITY.md")
    skills_file = next(file for file in bundle["bootstrap_files"] if file["path"] == "SKILLS.md")
    assert "Role Charter" in identity_file["content"]
    assert "Role Boundaries" in identity_file["content"]
    assert "Professional Skills" in skills_file["content"]
    assert "General Skills" in skills_file["content"]
    native_skill_paths = [file["path"] for file in bundle["bootstrap_files"] if file["path"].startswith("skills/")]
    assert native_skill_paths
    assert any(path.endswith("/SKILL.md") for path in native_skill_paths)
    assert len(native_skill_paths) >= 40


def test_openclaw_adapter_deduplicates_and_emits_multiple_follow_ups(monkeypatch) -> None:
    adapter = get_openclaw_gateway_adapter()
    settings = get_settings()
    sequence = iter(
        [
            "第一部分：多 agent 协作先要明确分工、共享目标和可见状态，这样 Chief of Staff 才能做真正的协调。",
            "第一部分：多 agent 协作先要明确分工、共享目标和可见状态，这样 Chief of Staff 才能做真正的协调。",
            "第二部分：他们需要共享 thread、ticket 和 checkpoint，避免每个 agent 按自己的理解单独推进。",
            "第三部分：最后一定要有 review 和 escalation 机制，让冲突能回到 CEO 可见空间里解决。",
            "DONE",
        ]
    )

    monkeypatch.setattr(settings, "openclaw_visible_follow_up_limit", 3)
    monkeypatch.setattr(settings, "openclaw_runtime_mode", "compat")
    monkeypatch.setattr(settings, "openclaw_gateway_base_url", "")
    monkeypatch.setattr(settings, "openclaw_gateway_api_key", "")
    monkeypatch.setattr(settings, "openclaw_gateway_timeout_seconds", 25)
    monkeypatch.setattr(adapter, "_should_use_native_gateway", lambda: False)
    monkeypatch.setattr(adapter, "_should_use_live_provider", lambda surface, app_id: True)
    monkeypatch.setattr(
        adapter,
        "_call_openai_compatible_chat",
        lambda **kwargs: next(sequence),
    )

    result = adapter.invoke_agent(
        employee_id="chief-of-staff",
        user_message="你觉得多agent相互配合是什么样的，你分多次给我答案",
        work_ticket=WorkTicket(
            ticket_id="wt-followup",
            title="多 agent 协作说明",
            ticket_type="consult",
        ),
        channel_id="feishu:dm:test",
        surface="feishu_dm",
        app_id="cli-test",
        visible_participants=["ceo"],
        conversation_history="[user:ceo] 你觉得多agent相互配合是什么样的，你分多次给我答案",
    )

    assert result.strategy == "openclaw_gateway_live"
    assert result.reply_text.startswith("第一部分")
    assert result.follow_up_texts == [
        "第二部分：他们需要共享 thread、ticket 和 checkpoint，避免每个 agent 按自己的理解单独推进。",
        "第三部分：最后一定要有 review 和 escalation 机制，让冲突能回到 CEO 可见空间里解决。",
    ]


def test_openclaw_adapter_prefers_native_gateway_when_configured(monkeypatch) -> None:
    adapter = get_openclaw_gateway_adapter()
    settings = get_settings()

    monkeypatch.setattr(settings, "openclaw_visible_follow_up_limit", 0)
    monkeypatch.setattr(settings, "openclaw_runtime_mode", "gateway")
    monkeypatch.setattr(settings, "openclaw_gateway_base_url", "http://gateway.example")
    monkeypatch.setattr(settings, "openclaw_gateway_api_key", "gateway-token")
    monkeypatch.setattr(settings, "openclaw_gateway_timeout_seconds", 25)
    monkeypatch.setattr(
        adapter,
        "_call_openclaw_native_gateway_chat",
        lambda **kwargs: "这是来自 OpenClaw native gateway 的回复。",
    )
    monkeypatch.setattr(
        adapter,
        "_call_openai_compatible_chat",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("compat path should not be used")),
    )

    result = adapter.invoke_agent(
        employee_id="product-lead",
        user_message="给我一个产品判断",
        work_ticket=WorkTicket(
            ticket_id="wt-native",
            title="产品判断",
            ticket_type="consult",
        ),
        channel_id="feishu:dm:native",
        surface="feishu_dm",
        app_id="cli-native",
        visible_participants=["ceo"],
        conversation_history="[user:ceo] 给我一个产品判断",
    )

    assert result.strategy == "openclaw_native_gateway"
    assert result.model_ref == "openclaw:opc-product-lead"
    assert result.reply_text == "这是来自 OpenClaw native gateway 的回复。"


def test_openclaw_semantic_handoff_inference_accepts_high_confidence_targets(monkeypatch) -> None:
    adapter = get_openclaw_gateway_adapter()

    monkeypatch.setattr(adapter, "_should_use_native_gateway", lambda: False)
    monkeypatch.setattr(
        adapter,
        "_call_runtime_completion",
        lambda **kwargs: json.dumps(
            {
                "needs_handoff": True,
                "targets": [
                    {
                        "employee_id": "product-lead",
                        "confidence": 0.92,
                        "reason": "需要产品判断价值",
                    },
                    {
                        "employee_id": "design-lead",
                        "confidence": 0.82,
                        "reason": "需要设计给体验建议",
                    },
                    {
                        "employee_id": "chief-of-staff",
                        "confidence": 0.99,
                        "reason": "当前 bot 自己不应重复进入",
                    },
                    {
                        "employee_id": "quality-lead",
                        "confidence": 0.51,
                        "reason": "低置信候选不应被采纳",
                    },
                ],
            },
            ensure_ascii=False,
        ),
    )

    result = adapter.infer_visible_handoff_targets(
        employee_id="chief-of-staff",
        user_message="需要产品来判断价值，也想听设计给体验建议。",
        channel_id="feishu:group:test-handoff-router",
        surface="feishu_group",
        conversation_history="[user:ceo] 需要产品来判断价值，也想听设计给体验建议。",
        candidate_employee_ids=["product-lead", "design-lead", "quality-lead"],
    )

    assert result.needs_handoff is True
    assert [candidate.employee_id for candidate in result.targets] == ["product-lead", "design-lead"]


def test_openclaw_provision_sync_materializes_runtime_home(tmp_path, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openclaw_runtime_home", str(tmp_path / "openclaw-home"))
    monkeypatch.setattr(settings, "openclaw_gateway_token", "sync-test-token")
    monkeypatch.setattr(settings, "openclaw_gateway_host_port", 18789)

    response = client.post("/api/v1/openclaw/provision/sync")

    assert response.status_code == 200
    payload = response.json()
    assert payload["workspace_count"] == 7
    assert "bootstrap-extra-files" in payload["enabled_hooks"]

    runtime_home = tmp_path / "openclaw-home"
    config_path = runtime_home / "config" / "openclaw.json"
    bootstrap_path = runtime_home / "workspace" / "chief-of-staff" / "BOOTSTRAP.md"
    soul_path = runtime_home / "workspace" / "chief-of-staff" / "SOUL.md"
    agents_path = runtime_home / "workspace" / "chief-of-staff" / "AGENTS.md"
    skills_path = runtime_home / "workspace" / "chief-of-staff" / "SKILLS.md"
    native_skill_path = runtime_home / "workspace" / "chief-of-staff" / "skills"

    assert config_path.exists()
    assert bootstrap_path.exists()
    assert soul_path.exists()
    assert agents_path.exists()
    assert skills_path.exists()
    assert native_skill_path.exists()
    exported_skill_files = sorted(native_skill_path.glob("*/SKILL.md"))
    assert len(exported_skill_files) >= 40
    assert "Chief of Staff" in bootstrap_path.read_text(encoding="utf-8")

    config_payload = json.loads(config_path.read_text(encoding="utf-8"))
    assert config_payload["gateway"]["bind"] == "lan"
    assert config_payload["gateway"]["http"]["endpoints"]["chatCompletions"]["enabled"] is True
    assert config_payload["gateway"]["controlUi"]["dangerouslyDisableDeviceAuth"] is True
    assert config_payload["hooks"]["internal"]["enabled"] is True
    assert config_payload["hooks"]["internal"]["entries"]["bootstrap-extra-files"]["enabled"] is True
    assert config_payload["hooks"]["internal"]["entries"]["bootstrap-extra-files"]["paths"] == [
        "AGENTS.md",
        "IDENTITY.md",
        "SOUL.md",
        "SKILLS.md",
        "TOOLS.md",
        "HEARTBEAT.md",
        "USER.md",
    ]
    assert config_payload["hooks"]["internal"]["entries"]["command-logger"]["enabled"] is True
    assert config_payload["hooks"]["internal"]["entries"]["session-memory"]["enabled"] is False
    assert config_payload["skills"]["load"]["watch"] is True
    assert len(config_payload["agents"]["list"]) == 7
    compat_formats = [
        model["compat"]["thinkingFormat"]
        for provider in config_payload["models"]["providers"].values()
        for model in provider["models"]
    ]
    assert set(compat_formats).issubset({"openai", "qwen", "zai"})


def test_openclaw_agent_detail_exposes_workspace_native_skills_memory_and_runtime() -> None:
    response = client.get("/api/v1/openclaw/agents/chief-of-staff/detail")

    assert response.status_code == 200
    payload = response.json()
    assert payload["agent"]["employee_id"] == "chief-of-staff"
    assert payload["binding"]["openclaw_agent_id"] == "opc-chief-of-staff"
    assert any(file["path"] == "AGENTS.md" for file in payload["workspace_files"])
    assert any(file["path"] == "SKILLS.md" for file in payload["workspace_files"])
    assert len(payload["native_skills"]) >= 40
    assert payload["native_skills"][0]["native_skill_name"].startswith("opc-chief-of-staff--")
    assert "verification_status" in payload["native_skills"][0]
    assert "discovery_detail" in payload["native_skills"][0]
    assert "company:default" in {namespace["namespace_id"] for namespace in payload["memory_namespaces"]}


def test_openclaw_agent_sync_and_skill_recheck_endpoints_return_runtime_discovered_skills(tmp_path, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openclaw_runtime_home", str(tmp_path / "openclaw-home"))
    monkeypatch.setattr(settings, "openclaw_gateway_token", "agent-sync-token")
    monkeypatch.setattr(settings, "openclaw_gateway_host_port", 18789)

    sync_response = client.post("/api/v1/openclaw/agents/chief-of-staff/sync")
    recheck_response = client.post("/api/v1/openclaw/agents/chief-of-staff/skills/recheck")

    assert sync_response.status_code == 200
    assert recheck_response.status_code == 200

    sync_payload = sync_response.json()
    recheck_payload = recheck_response.json()

    assert sync_payload["agent"]["employee_id"] == "chief-of-staff"
    assert recheck_payload["agent"]["employee_id"] == "chief-of-staff"
    assert sync_payload["native_skills"]
    assert recheck_payload["native_skills"]
    assert all(item["discovered"] is True for item in sync_payload["native_skills"][:5])
    assert all(item["verification_status"] == "ready" for item in recheck_payload["native_skills"][:5])


def test_openclaw_gateway_health_and_runtime_mode_endpoints(monkeypatch) -> None:
    class FakeHealthService:
        def health(self):
            return {
                "status": "healthy",
                "runtime_mode": "gateway",
                "gateway_base_url": "http://openclaw-gateway:18789",
                "control_ui_url": "http://127.0.0.1:18789/",
                "runtime_home": ".runtime/openclaw/home",
                "config_path": ".runtime/openclaw/home/config/openclaw.json",
                "config_exists": True,
                "reachable": True,
                "active_session_refs": 2,
            }

        def get_runtime_mode_view(self):
            return {
                "runtime_mode": "gateway",
                "gateway_base_url": "http://openclaw-gateway:18789",
                "control_ui_url": "http://127.0.0.1:18789/",
                "runtime_home": ".runtime/openclaw/home",
            }

        def get_control_ui_token_setup_view(self):
            return {
                "runtime_mode": "gateway",
                "control_ui_url": "http://127.0.0.1:18789/",
                "launch_url": "/openclaw-control-ui/launch",
                "token_configured": True,
                "token_env_key": "OPENCLAW_GATEWAY_TOKEN",
                "token_source": ".env",
                "pairing_ready": True,
                "setup_steps": [
                    "通过 launch route 打开 Control UI",
                    "检查 Gateway health",
                ],
            }

        def list_session_views(self, search=None, surface=None, status=None):
            return [
                {
                    "thread_id": "ct-123",
                    "title": "Chief of Staff DM",
                    "surface": "feishu_dm",
                    "channel_id": "feishu:dm:chief-of-staff",
                    "status": "linked",
                    "work_ticket_ref": "wt-123",
                    "runtrace_ref": "rt-123",
                    "bound_agent_ids": ["chief-of-staff"],
                    "openclaw_session_refs": {"chief-of-staff": "agent:opc-chief-of-staff:feishu:dm:test"},
                    "visible_room_ref": None,
                }
            ]

        def get_session_detail(self, thread_id):
            return {
                "thread_id": thread_id,
                "title": "Chief of Staff DM",
                "surface": "feishu_dm",
                "channel_id": "feishu:dm:chief-of-staff",
                "status": "linked",
                "work_ticket_ref": "wt-123",
                "runtrace_ref": "rt-123",
                "taskgraph_ref": None,
                "bound_agent_ids": ["chief-of-staff"],
                "participant_ids": ["ceo", "feishu-chief-of-staff"],
                "openclaw_session_refs": {"chief-of-staff": "agent:opc-chief-of-staff:feishu:dm:test"},
                "visible_room_ref": None,
                "transcript_count": 1,
                "last_transcript_at": "2026-03-15T12:00:00Z",
                "transcript": [
                    {
                        "source": "feishu_inbound",
                        "actor": "feishu-user:ou-demo",
                        "text": "给我一个判断",
                        "created_at": "2026-03-15T12:00:00Z",
                        "app_id": "cli-demo",
                    }
                ],
                "recent_run_strategies": ["openclaw_native_gateway"],
            }

        def get_hook_config_view(self):
            return {
                "runtime_home": ".runtime/openclaw/home",
                "config_path": ".runtime/openclaw/home/config/openclaw.json",
                "internal_enabled": True,
                "entries": [
                    {
                        "hook_id": "bootstrap-extra-files",
                        "enabled": True,
                        "source": "internal",
                        "config": {"paths": ["SOUL.md", "TOOLS.md"]},
                    }
                ],
            }

        def list_recent_native_runs(self, limit=12, search=None, surface=None, status=None):
            return [
                {
                    "runtrace_id": "rt-123",
                    "work_ticket_ref": "wt-123",
                    "thread_ref": "ct-123",
                    "surface": "feishu_dm",
                    "interaction_mode": "quick_consult",
                    "status": "completed",
                    "model_ref": "openclaw:opc-chief-of-staff",
                    "strategy": "openclaw_native_gateway",
                    "session_refs": {"chief-of-staff": "agent:opc-chief-of-staff:feishu:dm:test"},
                    "last_event_at": "2026-03-15T12:00:00Z",
                    "error_detail": None,
                }
            ]

        def get_run_detail(self, runtrace_id):
            return {
                "runtrace_id": runtrace_id,
                "work_ticket_ref": "wt-123",
                "thread_ref": "ct-123",
                "taskgraph_ref": "tg-123",
                "surface": "feishu_dm",
                "interaction_mode": "quick_consult",
                "status": "completed",
                "trigger_type": "manual",
                "model_ref": "openclaw:opc-chief-of-staff",
                "strategy": "openclaw_native_gateway",
                "dispatch_targets": ["chief-of-staff"],
                "agent_turn_refs": [],
                "activated_departments": ["Executive Office"],
                "visible_speakers": ["Chief of Staff"],
                "session_refs": {"chief-of-staff": "agent:opc-chief-of-staff:feishu:dm:test"},
                "last_event_at": "2026-03-15T12:00:00Z",
                "event_count": 2,
                "error_detail": None,
                "events": [
                    {
                        "event_type": "agent_dialogue_generated",
                        "message": "reply generated",
                        "created_at": "2026-03-15T12:00:00Z",
                        "metadata": {"strategy": "openclaw_native_gateway"},
                    }
                ],
            }

        def list_ops_issues(self, limit=10):
            return [
                {
                    "source": "feishu_delivery",
                    "severity": "medium",
                    "title": "Feishu outbound failed for oc_xxx",
                    "detail": "timeout",
                    "ref": "fo-123",
                    "created_at": "2026-03-15T12:01:00Z",
                }
            ]

    monkeypatch.setattr(
        "app.api.routes.openclaw.get_openclaw_gateway_health_service",
        lambda: FakeHealthService(),
    )

    health_response = client.get("/api/v1/openclaw/gateway/health")
    mode_response = client.get("/api/v1/openclaw/gateway/runtime-mode")
    token_setup_response = client.get("/api/v1/openclaw/gateway/token-setup")
    sessions_response = client.get("/api/v1/openclaw/gateway/sessions")
    session_detail_response = client.get("/api/v1/openclaw/gateway/sessions/ct-123")
    runs_response = client.get("/api/v1/openclaw/gateway/recent-runs")
    run_detail_response = client.get("/api/v1/openclaw/gateway/recent-runs/rt-123")
    issues_response = client.get("/api/v1/openclaw/gateway/issues")
    hooks_response = client.get("/api/v1/openclaw/gateway/hooks")

    assert health_response.status_code == 200
    assert mode_response.status_code == 200
    assert token_setup_response.status_code == 200
    assert sessions_response.status_code == 200
    assert session_detail_response.status_code == 200
    assert runs_response.status_code == 200
    assert run_detail_response.status_code == 200
    assert issues_response.status_code == 200
    assert hooks_response.status_code == 200
    assert health_response.json()["status"] == "healthy"
    assert mode_response.json()["runtime_mode"] == "gateway"
    assert token_setup_response.json()["token_env_key"] == "OPENCLAW_GATEWAY_TOKEN"
    assert token_setup_response.json()["launch_url"] == "/openclaw-control-ui/launch"
    assert sessions_response.json()[0]["thread_id"] == "ct-123"
    assert session_detail_response.json()["transcript_count"] == 1
    assert runs_response.json()[0]["strategy"] == "openclaw_native_gateway"
    assert run_detail_response.json()["event_count"] == 2
    assert issues_response.json()[0]["source"] == "feishu_delivery"
    assert hooks_response.json()["entries"][0]["hook_id"] == "bootstrap-extra-files"


def test_openclaw_session_and_run_detail_endpoints() -> None:
    intake_response = client.post(
        "/api/v1/conversations/intake",
        json={
            "surface": "feishu_dm",
            "channel_id": "feishu:dm:openclaw-detail",
            "participant_ids": ["ceo", "feishu-chief-of-staff"],
            "bound_agent_ids": ["chief-of-staff"],
            "command": {"intent": "给我一个多 agent 协作判断"},
        },
    )
    assert intake_response.status_code == 200
    payload = intake_response.json()
    thread_id = payload["thread"]["thread_id"]
    runtrace_id = payload["command_result"]["run_trace"]["runtrace_id"]

    get_conversation_service().attach_openclaw_session(
        thread_id,
        "chief-of-staff",
        "agent:opc-chief-of-staff:feishu:dm:openclaw-detail",
    )
    get_conversation_service().set_active_runtrace(
        thread_id,
        runtrace_id=runtrace_id,
        delivery_guard_epoch=3,
    )
    get_conversation_service().set_last_committed_state(
        thread_id,
        {
            "game": "count7",
            "last_speaker": "quality-lead",
            "baton_owner": "chief-of-staff",
            "next_expected_number": 8,
        },
    )
    get_conversation_service().set_pending_handoff(
        thread_id,
        PendingHandoffState(
            source_agent_id="quality-lead",
            target_agent_id="chief-of-staff",
            instruction="继续报8",
            reason="纠正上一跳",
            source_runtrace_ref=runtrace_id,
        ),
    )
    get_control_plane_service().set_run_trace_visible_turn_count(runtrace_id, 3)
    get_control_plane_service().set_run_trace_delivery_guard_epoch(runtrace_id, 3)
    get_control_plane_service().set_run_trace_interruption_reason(runtrace_id, "user_interruption")
    get_control_plane_service().set_run_trace_interruption_dispatch_targets(
        runtrace_id,
        ["chief-of-staff", "quality-lead"],
    )
    get_control_plane_service().set_run_trace_supersedes_runtrace_ref(runtrace_id, "rt-prev")
    get_control_plane_service().append_run_trace_event(
        runtrace_id,
        RunEvent(
            event_type="agent_dialogue_generated",
            message="Chief of Staff generated a native gateway reply.",
            metadata={
                "strategy": "openclaw_native_gateway",
                "model_ref": "openclaw:opc-chief-of-staff",
            },
        ),
    )
    get_control_plane_service().append_run_trace_event(
        runtrace_id,
        RunEvent(
            event_type="visible_agent_handoff",
            message="quality-lead handed off to chief-of-staff in visible room.",
            metadata={
                "handoff_source_agent": "quality-lead",
                "handoff_targets": "chief-of-staff",
                "handoff_reason": "继续报8",
                "visible_turn_index": "3",
            },
        ),
    )

    session_response = client.get(f"/api/v1/openclaw/gateway/sessions/{thread_id}")
    runs_response = client.get("/api/v1/openclaw/gateway/recent-runs?surface=feishu_dm")
    run_response = client.get(f"/api/v1/openclaw/gateway/recent-runs/{runtrace_id}")

    assert session_response.status_code == 200
    assert runs_response.status_code == 200
    assert run_response.status_code == 200
    assert session_response.json()["thread_id"] == thread_id
    assert session_response.json()["openclaw_session_refs"]["chief-of-staff"].startswith("agent:opc-chief-of-staff")
    assert session_response.json()["active_runtrace_ref"] == runtrace_id
    assert session_response.json()["delivery_guard_epoch"] == 3
    assert session_response.json()["last_committed_state"]["next_expected_number"] == 8
    assert session_response.json()["pending_handoff"]["instruction"] == "继续报8"
    run_list_item = next(item for item in runs_response.json() if item["runtrace_id"] == runtrace_id)
    assert run_list_item["visible_turn_count"] == 3
    assert run_list_item["delivery_guard_epoch"] == 3
    assert run_list_item["interruption_reason"] == "user_interruption"
    assert run_list_item["interruption_dispatch_targets"] == ["chief-of-staff", "quality-lead"]
    assert run_list_item["supersedes_runtrace_ref"] == "rt-prev"
    assert run_list_item["turn_limit_scope"] == "run"
    assert run_response.json()["runtrace_id"] == runtrace_id
    assert run_response.json()["strategy"] == "openclaw_native_gateway"
    assert run_response.json()["visible_turn_count"] == 3
    assert run_response.json()["delivery_guard_epoch"] == 3
    assert run_response.json()["interruption_reason"] == "user_interruption"
    assert run_response.json()["interruption_dispatch_targets"] == ["chief-of-staff", "quality-lead"]
    assert run_response.json()["supersedes_runtrace_ref"] == "rt-prev"
    assert run_response.json()["turn_limit_scope"] == "run"
    event_types = [event["event_type"] for event in run_response.json()["events"]]
    assert "agent_dialogue_generated" in event_types
    assert event_types[-1] == "visible_agent_handoff"


def test_openclaw_binding_and_hook_update_endpoints(tmp_path, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "openclaw_runtime_home", str(tmp_path / "openclaw-home"))
    monkeypatch.setattr(settings, "openclaw_gateway_token", "sync-test-token")
    monkeypatch.setattr(settings, "openclaw_gateway_host_port", 18789)

    binding_response = client.put(
        "/api/v1/openclaw/bindings/chief-of-staff",
        json={
            "tool_profile": "coordination/escalation",
            "sandbox_profile": "workspace-admin",
        },
    )
    hook_response = client.put(
        "/api/v1/openclaw/gateway/hooks/command-logger",
        json={
            "enabled": True,
            "config": {"level": "debug"},
        },
    )
    hooks_view_response = client.get("/api/v1/openclaw/gateway/hooks")

    assert binding_response.status_code == 200
    assert hook_response.status_code == 200
    assert hooks_view_response.status_code == 200
    assert binding_response.json()["tool_profile"] == "coordination/escalation"
    assert binding_response.json()["sandbox_profile"] == "workspace-admin"
    hook_entry = next(entry for entry in hooks_view_response.json()["entries"] if entry["hook_id"] == "command-logger")
    assert hook_entry["config"]["level"] == "debug"


def test_openclaw_session_and_run_list_support_filters() -> None:
    intake_response = client.post(
        "/api/v1/conversations/intake",
        json={
            "surface": "feishu_group",
            "channel_id": "feishu:group:filter-room",
            "participant_ids": ["ceo", "feishu-chief-of-staff"],
            "bound_agent_ids": ["chief-of-staff"],
            "command": {"intent": "在群聊里给我一个协调意见"},
        },
    )
    assert intake_response.status_code == 200
    payload = intake_response.json()
    thread_id = payload["thread"]["thread_id"]
    runtrace_id = payload["command_result"]["run_trace"]["runtrace_id"]

    get_conversation_service().attach_openclaw_session(
        thread_id,
        "chief-of-staff",
        "agent:opc-chief-of-staff:feishu:group:filter-room",
    )
    get_control_plane_service().append_run_trace_event(
        runtrace_id,
        RunEvent(
            event_type="agent_dialogue_generated",
            message="Chief of Staff generated a native gateway reply.",
            metadata={
                "strategy": "openclaw_native_gateway",
                "model_ref": "openclaw:opc-chief-of-staff",
            },
        ),
    )

    sessions_response = client.get("/api/v1/openclaw/gateway/sessions?search=filter-room&surface=feishu_group")
    runs_response = client.get("/api/v1/openclaw/gateway/recent-runs?search=openclaw_native_gateway&surface=feishu_group")

    assert sessions_response.status_code == 200
    assert runs_response.status_code == 200
    assert any(item["thread_id"] == thread_id for item in sessions_response.json())
    assert any(item["runtrace_id"] == runtrace_id for item in runs_response.json())
