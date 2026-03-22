from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.feishu.models import FeishuBotAppConfig
from app.main import app

client = TestClient(app)


def test_quality_evidence_persists_artifact_blob_to_minio() -> None:
    intake_response = client.post(
        "/api/v1/commands/intake",
        json={"intent": "做一个 AI 产品 MVP，给我一套完整方案"},
    )
    ticket_id = intake_response.json()["work_ticket"]["ticket_id"]

    quality_response = client.post(
        "/api/v1/quality/evaluate",
        json={
            "work_ticket_id": ticket_id,
            "verdict": "go",
            "summary": "证据齐全，可以继续推进。",
            "evidence_points": ["demo link attached", "acceptance notes complete"],
        },
    )

    assert quality_response.status_code == 200
    artifact = quality_response.json()["evidence_artifact"]
    assert artifact["object_ref"]
    assert artifact["object_bucket"] == "opc-artifacts"
    assert artifact["object_key"]

    blob_response = client.get(f"/api/v1/artifacts/work-tickets/{ticket_id}/blobs")
    assert blob_response.status_code == 200
    blobs = blob_response.json()
    assert any(blob["object_id"] == artifact["object_ref"] for blob in blobs)

    content_response = client.get(f"/api/v1/artifacts/blobs/{artifact['object_ref']}/content")
    assert content_response.status_code == 200
    payload = content_response.json()
    assert payload["record"]["object_id"] == artifact["object_ref"]
    assert "证据齐全，可以继续推进。" in payload["content"]


def test_feishu_send_persists_outbound_attachment_blob(monkeypatch) -> None:
    suffix = uuid4().hex[:8]

    monkeypatch.setattr(
        "app.feishu.services.get_feishu_bot_app_config_by_app_id",
        lambda app_id: FeishuBotAppConfig(
            employee_id="chief-of-staff",
            app_id=app_id,
            app_secret="secret",
            display_name="OPC - Chief of Staff",
            bot_open_id="ou-chief",
        ),
    )
    monkeypatch.setattr(
        "app.feishu.services.FeishuSurfaceAdapterService._get_tenant_access_token",
        lambda self, app_id, app_secret: "tenant-token",
    )
    monkeypatch.setattr(
        "app.feishu.services.FeishuSurfaceAdapterService._post_json",
        lambda self, url, payload, headers=None: {"data": {"message_id": f"om-sent-{suffix}"}},
    )

    response = client.post(
        "/api/v1/feishu/send",
        json={
            "app_id": "cli-chief",
            "chat_id": f"oc_group_{suffix}",
            "text": "这是一条 Feishu test send。",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["message_id"] == f"om-sent-{suffix}"
    assert payload["attachment_object_ref"]

    outbound_response = client.get("/api/v1/feishu/outbound-messages?limit=20")
    assert outbound_response.status_code == 200
    outbound = outbound_response.json()
    matched = next(message for message in outbound if message["message_id"] == f"om-sent-{suffix}")
    assert matched["attachment_object_ref"] == payload["attachment_object_ref"]

    content_response = client.get(f"/api/v1/artifacts/blobs/{payload['attachment_object_ref']}/content")
    assert content_response.status_code == 200
    assert "Feishu test send" in content_response.json()["content"]
