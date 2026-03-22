from fastapi import APIRouter

from app.company.bootstrap import (
    get_company_profile,
    get_departments,
    get_seat_map,
)

router = APIRouter()


@router.get("/company")
def company_profile():
    return get_company_profile()


@router.get("/departments")
def departments():
    return get_departments()


@router.get("/seat-map")
def seat_map():
    return get_seat_map()

