from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings
from app.ui.router import router as ui_router

settings = get_settings()
STATIC_DIR = Path(__file__).resolve().parent / "ui" / "static"
DIST_DIR = Path(__file__).resolve().parent / "ui" / "dist"

DIST_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Foundation backend for the one-person-company V1 control plane.",
)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "environment": settings.app_env,
        "api_prefix": settings.api_prefix,
        "status": "bootstrap_ready",
    }


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
    }


app.include_router(ui_router)
app.mount("/dashboard-static", StaticFiles(directory=DIST_DIR), name="dashboard-static")
app.mount("/dashboard-legacy-static", StaticFiles(directory=STATIC_DIR), name="dashboard-legacy-static")
app.include_router(api_router, prefix=settings.api_prefix)
