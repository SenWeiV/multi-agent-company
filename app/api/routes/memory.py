from fastapi import APIRouter, HTTPException

from app.memory.models import MemoryWriteRequest, RecallQuery
from app.memory.services import get_memory_service

router = APIRouter()


@router.get("/namespaces")
def list_namespaces():
    return get_memory_service().list_namespaces()


@router.get("/records")
def list_records():
    return get_memory_service().list_records()


@router.get("/work-tickets/{ticket_id}")
def list_records_for_ticket(ticket_id: str):
    return get_memory_service().list_records_for_ticket(ticket_id)


@router.post("/write")
def write_memory(request: MemoryWriteRequest):
    try:
        return get_memory_service().write(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"MemoryNamespace not found: {exc.args[0]}") from exc


@router.post("/recall")
def recall_memory(query: RecallQuery):
    return get_memory_service().recall(query)
