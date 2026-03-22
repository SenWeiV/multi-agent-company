from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import get_settings
from app.openclaw.runtime_home import get_openclaw_gateway_health_service

router = APIRouter()

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_DIST_DIR = Path(__file__).resolve().parent / "dist"


def _inject_runtime_config(template: str) -> str:
    settings = get_settings()
    return (
        template.replace("__API_PREFIX__", settings.api_prefix)
        .replace("__APP_NAME__", settings.app_name)
        .replace("__APP_ENV__", settings.app_env)
    )


def _render_dashboard_app() -> HTMLResponse:
    index_path = _DIST_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=503, detail="Dashboard frontend bundle missing. Run npm build in dashboard-web.")
    template = index_path.read_text(encoding="utf-8")
    return HTMLResponse(content=_inject_runtime_config(template))


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    return _render_dashboard_app()


@router.get("/dashboard/{path:path}", response_class=HTMLResponse)
def dashboard_spa(path: str) -> HTMLResponse:
    return _render_dashboard_app()


@router.get("/dashboard-legacy", response_class=HTMLResponse)
def dashboard_legacy() -> HTMLResponse:
    template = (_TEMPLATE_DIR / "dashboard.html").read_text(encoding="utf-8")
    return HTMLResponse(content=_inject_runtime_config(template))


@router.get("/openclaw-control-ui/launch")
def launch_openclaw_control_ui():
    try:
        launch_url = get_openclaw_gateway_health_service().build_control_ui_launch_url()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    response = RedirectResponse(url=launch_url, status_code=307)
    response.headers["Cache-Control"] = "no-store"
    return response
