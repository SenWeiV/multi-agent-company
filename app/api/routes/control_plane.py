from fastapi import APIRouter, HTTPException

from app.control_plane.services import get_control_plane_service

router = APIRouter()


@router.get("/work-tickets")
def list_work_tickets():
    return get_control_plane_service().list_work_tickets()


@router.get("/work-tickets/{ticket_id}")
def get_work_ticket(ticket_id: str):
    ticket = get_control_plane_service().get_work_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="WorkTicket not found")
    return ticket


@router.get("/task-graphs/{taskgraph_id}")
def get_task_graph(taskgraph_id: str):
    task_graph = get_control_plane_service().get_task_graph(taskgraph_id)
    if task_graph is None:
        raise HTTPException(status_code=404, detail="TaskGraph not found")
    return task_graph


@router.get("/run-traces/{runtrace_id}")
def get_run_trace(runtrace_id: str):
    run_trace = get_control_plane_service().get_run_trace(runtrace_id)
    if run_trace is None:
        raise HTTPException(status_code=404, detail="RunTrace not found")
    return run_trace


@router.get("/checkpoints/{checkpoint_id}")
def get_checkpoint(checkpoint_id: str):
    checkpoint = get_control_plane_service().get_checkpoint(checkpoint_id)
    if checkpoint is None:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    return checkpoint


@router.get("/work-tickets/{ticket_id}/checkpoints")
def list_checkpoints_for_ticket(ticket_id: str):
    return get_control_plane_service().list_checkpoints_for_ticket(ticket_id)


@router.post("/checkpoints/{checkpoint_id}/restore")
def restore_checkpoint(checkpoint_id: str):
    service = get_control_plane_service()
    checkpoint = service.get_checkpoint(checkpoint_id)
    if checkpoint is None:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    restored_checkpoint, work_ticket, task_graph, run_trace = service.restore_checkpoint(checkpoint_id)
    return {
        "checkpoint": restored_checkpoint,
        "work_ticket": work_ticket,
        "task_graph": task_graph,
        "run_trace": run_trace,
    }
