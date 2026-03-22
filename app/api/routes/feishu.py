from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.feishu.models import FeishuSendMessageRequest
from app.feishu.services import get_feishu_surface_adapter_service

router = APIRouter()


@router.post("/events")
async def receive_feishu_events(request: Request):
    raw_body = await request.body()
    headers = dict(request.headers.items())
    try:
        result = get_feishu_surface_adapter_service().handle_callback(raw_body, headers)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if result.status == "challenge":
        return {"challenge": result.challenge}
    return result


@router.post("/send")
def send_feishu_message(request: FeishuSendMessageRequest):
    try:
        return get_feishu_surface_adapter_service().send_text_message(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/bot-apps")
def list_feishu_bot_apps():
    return get_feishu_surface_adapter_service().list_bot_apps()


@router.get("/inbound-events")
def list_feishu_inbound_events(limit: int = 20):
    events = get_feishu_surface_adapter_service().list_inbound_events()
    return events[-limit:]


@router.get("/group-debug-events")
def list_feishu_group_debug_events(limit: int = 20, status: str | None = None):
    events = get_feishu_surface_adapter_service().list_group_debug_events()
    if status:
        events = [event for event in events if event.processed_status == status]
    return events[:limit]


@router.get("/group-debug-events/{debug_event_id}")
def get_feishu_group_debug_event(debug_event_id: str):
    try:
        return get_feishu_surface_adapter_service().get_group_debug_event(debug_event_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Feishu group debug event not found: {exc.args[0]}") from exc


@router.get("/outbound-messages")
def list_feishu_outbound_messages(limit: int = 20, status: str | None = None):
    messages = get_feishu_surface_adapter_service().list_outbound_messages()
    if status:
        messages = [message for message in messages if message.status == status]
    return messages[-limit:]


@router.get("/dead-letters")
def list_feishu_dead_letters(limit: int = 20, include_resolved: bool = False):
    messages = get_feishu_surface_adapter_service().list_dead_letters(include_resolved=include_resolved)
    return messages[:limit]


@router.get("/dead-letters/{outbound_id}")
def get_feishu_dead_letter_detail(outbound_id: str):
    try:
        return get_feishu_surface_adapter_service().get_dead_letter_detail(outbound_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Feishu outbound message not found: {exc.args[0]}") from exc


@router.get("/replay-audit")
def list_feishu_replay_audit(limit: int = 20, source_outbound_ref: str | None = None, chat_id: str | None = None):
    entries = get_feishu_surface_adapter_service().list_replay_audit(
        source_outbound_ref=source_outbound_ref,
        chat_id=chat_id,
    )
    return entries[:limit]


@router.post("/outbound-messages/{outbound_id}/replay")
def replay_feishu_outbound_message(outbound_id: str):
    try:
        return get_feishu_surface_adapter_service().replay_outbound_message(outbound_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Feishu outbound message not found: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
