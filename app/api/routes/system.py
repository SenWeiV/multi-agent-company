from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()


@router.get("/health")
@router.get("/system/health")
def health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "environment": settings.app_env,
        "state_store_backend": settings.state_store_backend,
    }
