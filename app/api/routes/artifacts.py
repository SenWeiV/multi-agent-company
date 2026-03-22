from fastapi import APIRouter, HTTPException

from app.artifacts.services import get_artifact_store_service

router = APIRouter()


@router.get("/blobs")
def list_artifact_blobs():
    return get_artifact_store_service().list_records()


@router.get("/blobs/{object_id}")
def get_artifact_blob(object_id: str):
    record = get_artifact_store_service().get_record(object_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Artifact blob not found: {object_id}")
    return record


@router.get("/blobs/{object_id}/content")
def get_artifact_blob_content(object_id: str):
    try:
        return get_artifact_store_service().read_content(object_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Artifact blob not found: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/work-tickets/{ticket_id}/blobs")
def list_artifact_blobs_for_ticket(ticket_id: str):
    return get_artifact_store_service().list_records_for_ticket(ticket_id)
