from fastapi import APIRouter, HTTPException

from app.skills.models import SkillInvocationRequest
from app.skills.services import get_skill_catalog_service
from app.persona.services import get_employee_pack_compiler, get_persona_source_adapter

router = APIRouter()


@router.get("/persona-packs")
def list_persona_packs():
    return get_persona_source_adapter().list_persona_packs()


@router.get("/persona-packs/{role_name}")
def get_persona_pack(role_name: str):
    try:
        return get_persona_source_adapter().get_persona_pack(role_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"PersonaPack not found: {exc.args[0]}") from exc


@router.get("/employee-packs")
def list_employee_packs(core_only: bool = False):
    return get_employee_pack_compiler().list_employee_packs(core_only=core_only)


@router.get("/employee-packs/{employee_id}")
def get_employee_pack(employee_id: str):
    try:
        return get_employee_pack_compiler().compile_employee_pack(employee_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"EmployeePack not found: {exc.args[0]}") from exc


@router.get("/employee-packs/{employee_id}/skills")
def get_employee_skill_pack(employee_id: str):
    try:
        pack = get_employee_pack_compiler().compile_employee_pack(employee_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"EmployeePack not found: {exc.args[0]}") from exc
    return {
        "employee_id": pack.employee_id,
        "employee_name": pack.employee_name,
        "professional_skills": pack.professional_skills,
        "general_skills": pack.general_skills,
    }


@router.post("/employee-packs/{employee_id}/skills/{skill_id}/invoke")
def invoke_employee_skill(employee_id: str, skill_id: str, request: SkillInvocationRequest | None = None):
    try:
        return get_skill_catalog_service().invoke_skill(
            employee_id=employee_id,
            skill_id=skill_id,
            request=request,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Skill not found: {exc.args[0]}") from exc


@router.get("/skill-catalog/validate")
def validate_skill_catalog():
    return get_skill_catalog_service().validate_catalog()


@router.get("/skill-invocations")
def list_skill_invocations(limit: int = 50):
    return get_skill_catalog_service().list_invocations(limit=limit)
