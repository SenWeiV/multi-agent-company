from fastapi import APIRouter, HTTPException

from app.runtime.services import get_runtime_service

router = APIRouter()


@router.post("/work-tickets/{ticket_id}/execute")
def execute_work_ticket(ticket_id: str):
    runtime_service = get_runtime_service()
    try:
        return runtime_service.execute_work_ticket(ticket_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Object not found: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/work-tickets/{ticket_id}/route-post-launch-follow-up")
def route_post_launch_follow_up(ticket_id: str):
    runtime_service = get_runtime_service()
    try:
        return runtime_service.route_post_launch_follow_up(ticket_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Object not found: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/post-launch/summary")
def get_post_launch_summary():
    return get_runtime_service().get_post_launch_summary()
