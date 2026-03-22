from fastapi import APIRouter

from app.control_plane.services import get_control_plane_service
from app.executive_office.models import CEOCommand
from app.executive_office.services import ExecutiveOfficeService

router = APIRouter()


@router.post("/classify")
def classify_command(command: CEOCommand):
    service = ExecutiveOfficeService()
    return service.classify_command(command)


@router.post("/intake")
def intake_command(command: CEOCommand):
    return get_control_plane_service().intake_command(command)
