from fastapi import APIRouter, HTTPException

from app.conversation.models import ChannelBindingUpdateRequest, ConversationIntakeRequest, RoomPolicyUpdateRequest
from app.conversation.services import get_conversation_service

router = APIRouter()


@router.post("/intake")
def intake_conversation(request: ConversationIntakeRequest):
    try:
        return get_conversation_service().intake(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Referenced object not found: {exc.args[0]}") from exc


@router.get("/threads")
def list_threads():
    return get_conversation_service().list_threads()


@router.get("/threads/{thread_id}")
def get_thread(thread_id: str):
    thread = get_conversation_service().get_thread(thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail=f"ConversationThread not found: {thread_id}")
    return thread


@router.get("/channel-bindings")
def list_channel_bindings():
    return get_conversation_service().list_channel_bindings()


@router.get("/bot-seat-bindings")
def list_bot_seat_bindings():
    return get_conversation_service().list_bot_seat_bindings()


@router.get("/room-policies")
def list_room_policies():
    return get_conversation_service().list_room_policies()


@router.put("/channel-bindings/{binding_id}")
def update_channel_binding(binding_id: str, request: ChannelBindingUpdateRequest):
    try:
        return get_conversation_service().update_channel_binding(binding_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"ChannelBinding not found: {exc.args[0]}") from exc


@router.put("/room-policies/{room_policy_id}")
def update_room_policy(room_policy_id: str, request: RoomPolicyUpdateRequest):
    try:
        return get_conversation_service().update_room_policy(room_policy_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"RoomPolicy not found: {exc.args[0]}") from exc
