from fastapi import APIRouter, HTTPException, Request

from app.approval.models import ReviewDecisionRequest
from app.approval.services import get_approval_service

router = APIRouter()


@router.post("/review-decision")
def review_decision(request: ReviewDecisionRequest):
    try:
        return get_approval_service().review_decision(request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Referenced object not found: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/work-tickets/{ticket_id}")
def list_approvals_for_ticket(ticket_id: str):
    return get_approval_service().list_approvals_for_ticket(ticket_id)


@router.post("/feishu-card-review-decision")
async def review_decision_from_feishu_card(request: Request):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid Feishu card callback payload")
    payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge")}
    try:
        result = get_approval_service().review_decision_from_feishu_card(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Referenced object not found: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "toast": {
            "type": "success",
            "content": "审批结果已记录",
        },
        "result": result,
    }
