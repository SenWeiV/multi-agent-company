from fastapi import APIRouter

from app.api.routes.artifacts import router as artifacts_router
from app.api.routes.approval import router as approval_router
from app.api.routes.bootstrap import router as bootstrap_router
from app.api.routes.commands import router as commands_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.control_plane import router as control_plane_router
from app.api.routes.feishu import router as feishu_router
from app.api.routes.governance import router as governance_router
from app.api.routes.memory import router as memory_router
from app.api.routes.openclaw import router as openclaw_router
from app.api.routes.persona import router as persona_router
from app.api.routes.quality import router as quality_router
from app.api.routes.runtime import router as runtime_router
from app.api.routes.system import router as system_router

api_router = APIRouter()
api_router.include_router(system_router, tags=["system"])
api_router.include_router(artifacts_router, prefix="/artifacts", tags=["artifacts"])
api_router.include_router(bootstrap_router, prefix="/bootstrap", tags=["bootstrap"])
api_router.include_router(commands_router, prefix="/commands", tags=["commands"])
api_router.include_router(conversations_router, prefix="/conversations", tags=["conversations"])
api_router.include_router(feishu_router, prefix="/feishu", tags=["feishu"])
api_router.include_router(control_plane_router, prefix="/control-plane", tags=["control-plane"])
api_router.include_router(runtime_router, prefix="/runtime", tags=["runtime"])
api_router.include_router(governance_router, prefix="/governance", tags=["governance"])
api_router.include_router(memory_router, prefix="/memory", tags=["memory"])
api_router.include_router(openclaw_router, prefix="/openclaw", tags=["openclaw"])
api_router.include_router(persona_router, prefix="/persona", tags=["persona"])
api_router.include_router(quality_router, prefix="/quality", tags=["quality"])
api_router.include_router(approval_router, prefix="/approvals", tags=["approvals"])
