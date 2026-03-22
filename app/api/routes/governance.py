from fastapi import APIRouter, HTTPException

from app.governance.models import EscalationRequest, OverrideRecoveryRequest
from app.governance.services import get_governance_service

router = APIRouter()


@router.post("/override-recovery")
def override_recovery(request: OverrideRecoveryRequest):
    try:
        return get_governance_service().override_recovery(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Referenced object not found: {exc.args[0]}") from exc


@router.post("/escalate")
def escalate(request: EscalationRequest):
    try:
        return get_governance_service().escalate(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Referenced object not found: {exc.args[0]}") from exc
