from fastapi import APIRouter, HTTPException

from app.openclaw.runtime_home import (
    get_openclaw_gateway_health_service,
    get_openclaw_runtime_home_materializer,
)
from app.openclaw.models import (
    OpenClawAgentBindingUpdateRequest,
    OpenClawAgentWorkspaceFileUpdateRequest,
    OpenClawHookUpdateRequest,
)
from app.openclaw.services import (
    get_openclaw_config_service,
    get_openclaw_provisioning_service,
)

router = APIRouter()


@router.get("/agents")
def list_openclaw_agents():
    return get_openclaw_config_service().list_agent_configs()


@router.get("/agents/{employee_id}")
def get_openclaw_agent(employee_id: str):
    try:
        return get_openclaw_config_service().compile_agent_config(employee_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"OpenClaw agent not found: {exc.args[0]}") from exc


@router.post("/agents/{employee_id}/sync")
def sync_openclaw_agent(employee_id: str):
    try:
        return get_openclaw_provisioning_service().sync_agent_runtime(employee_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"OpenClaw agent not found: {exc.args[0]}") from exc


@router.post("/agents/{employee_id}/skills/recheck")
def recheck_openclaw_agent_skills(employee_id: str):
    try:
        return get_openclaw_provisioning_service().recheck_native_skills(employee_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"OpenClaw agent not found: {exc.args[0]}") from exc


@router.get("/agents/{employee_id}/detail")
def get_openclaw_agent_detail(employee_id: str):
    try:
        return get_openclaw_provisioning_service().build_agent_detail(employee_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"OpenClaw agent not found: {exc.args[0]}") from exc


@router.put("/agents/{employee_id}/workspace-files/{path:path}")
def update_openclaw_agent_workspace_file(
    employee_id: str,
    path: str,
    request: OpenClawAgentWorkspaceFileUpdateRequest,
):
    try:
        workspace_file = get_openclaw_provisioning_service().update_workspace_file(employee_id, path, request)
        get_openclaw_runtime_home_materializer().sync()
        return workspace_file
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"OpenClaw workspace not found: {exc.args[0]}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/bindings")
def list_openclaw_agent_bindings():
    return get_openclaw_provisioning_service().list_agent_bindings()


@router.get("/bindings/{employee_id}")
def get_openclaw_agent_binding(employee_id: str):
    try:
        return get_openclaw_provisioning_service().get_agent_binding(employee_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"OpenClaw binding not found: {exc.args[0]}") from exc


@router.put("/bindings/{employee_id}")
def update_openclaw_agent_binding(employee_id: str, request: OpenClawAgentBindingUpdateRequest):
    try:
        binding = get_openclaw_provisioning_service().update_agent_binding(employee_id, request)
        get_openclaw_runtime_home_materializer().sync()
        return binding
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"OpenClaw binding not found: {exc.args[0]}") from exc


@router.get("/workspace-bundles")
def list_openclaw_workspace_bundles():
    return get_openclaw_provisioning_service().list_workspace_bundles()


@router.get("/workspace-bundles/{employee_id}")
def get_openclaw_workspace_bundle(employee_id: str):
    try:
        return get_openclaw_provisioning_service().get_workspace_bundle(employee_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"OpenClaw workspace bundle not found: {exc.args[0]}") from exc


@router.post("/provision/sync")
def sync_openclaw_runtime_home():
    return get_openclaw_runtime_home_materializer().sync()


@router.get("/gateway/health")
def get_openclaw_gateway_health():
    return get_openclaw_gateway_health_service().health()


@router.get("/gateway/runtime-mode")
def get_openclaw_gateway_runtime_mode():
    return get_openclaw_gateway_health_service().get_runtime_mode_view()


@router.get("/gateway/token-setup")
def get_openclaw_gateway_token_setup():
    return get_openclaw_gateway_health_service().get_control_ui_token_setup_view()


@router.get("/gateway/sessions")
def list_openclaw_gateway_sessions(search: str | None = None, surface: str | None = None, status: str | None = None):
    return get_openclaw_gateway_health_service().list_session_views(
        search=search,
        surface=surface,
        status=status,
    )


@router.get("/gateway/sessions/{thread_id}")
def get_openclaw_gateway_session_detail(thread_id: str):
    try:
        return get_openclaw_gateway_health_service().get_session_detail(thread_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"OpenClaw session not found: {exc.args[0]}") from exc


@router.get("/gateway/recent-runs")
def list_openclaw_gateway_recent_runs(
    limit: int = 12,
    search: str | None = None,
    surface: str | None = None,
    status: str | None = None,
):
    return get_openclaw_gateway_health_service().list_recent_native_runs(
        limit=limit,
        search=search,
        surface=surface,
        status=status,
    )


@router.get("/gateway/recent-runs/{runtrace_id}")
def get_openclaw_gateway_run_detail(runtrace_id: str):
    try:
        return get_openclaw_gateway_health_service().get_run_detail(runtrace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"OpenClaw run not found: {exc.args[0]}") from exc


@router.get("/gateway/issues")
def list_openclaw_gateway_issues(limit: int = 10):
    return get_openclaw_gateway_health_service().list_ops_issues(limit=limit)


@router.get("/gateway/hooks")
def get_openclaw_gateway_hooks():
    return get_openclaw_gateway_health_service().get_hook_config_view()


@router.put("/gateway/hooks/{hook_id}")
def update_openclaw_gateway_hook(hook_id: str, request: OpenClawHookUpdateRequest):
    return get_openclaw_gateway_health_service().update_hook_override(hook_id, request)
