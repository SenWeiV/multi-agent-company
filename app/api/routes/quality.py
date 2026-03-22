from fastapi import APIRouter, HTTPException

from app.quality.models import QualityEvaluationRequest
from app.quality.services import get_quality_service

router = APIRouter()


@router.post("/evaluate")
def evaluate_quality(request: QualityEvaluationRequest):
    try:
        return get_quality_service().evaluate(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Referenced object not found: {exc.args[0]}") from exc


@router.get("/work-tickets/{ticket_id}/artifacts")
def list_quality_artifacts(ticket_id: str):
    return get_quality_service().list_artifacts_for_ticket(ticket_id)
