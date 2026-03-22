from __future__ import annotations

from app.skills.models import SkillInvocationRequest
from app.skills.services import get_skill_catalog_service

CORE_EMPLOYEE_IDS = (
    "chief-of-staff",
    "product-lead",
    "research-lead",
    "delivery-lead",
    "design-lead",
    "engineering-lead",
    "quality-lead",
)


def test_skill_catalog_has_real_installable_skills_for_all_core_bots() -> None:
    service = get_skill_catalog_service()

    for employee_id in CORE_EMPLOYEE_IDS:
        pack = service.build_employee_skill_pack(employee_id)

        assert len(pack.professional_skills) >= 30
        assert len(pack.general_skills) >= 10

        for skill in [*pack.professional_skills, *pack.general_skills]:
            assert skill.skill_id
            assert skill.source_ref.repo_url.startswith("https://github.com/")
            assert skill.source_ref.repo_name
            assert skill.source_ref.commit_sha
            assert skill.source_ref.path
            assert skill.source_ref.license
            assert skill.source_ref.install_method
            assert skill.source_ref.verify_command
            assert skill.source_ref.local_path


def test_skill_catalog_validation_invokes_every_installed_skill() -> None:
    result = get_skill_catalog_service().validate_catalog()

    assert result.ok is True
    assert result.issues == []
    for employee_id in CORE_EMPLOYEE_IDS:
        assert result.professional_skill_count_by_employee[employee_id] >= 30
        assert result.general_skill_count_by_employee[employee_id] >= 10


def test_skill_catalog_exports_native_openclaw_skills_for_core_agents() -> None:
    service = get_skill_catalog_service()

    for employee_id in CORE_EMPLOYEE_IDS:
        exports = service.build_native_skill_exports(employee_id)

        assert len(exports) >= 40
        assert all(item.relative_dir.startswith("skills/") for item in exports)
        assert all(item.skill_md_path.endswith("/SKILL.md") for item in exports)
        assert all(item.native_skill_name.startswith(f"opc-{employee_id}--") for item in exports)
        assert all(item.skill_md_content.startswith("---\nname: ") for item in exports)
        assert all("metadata:" in item.skill_md_content for item in exports)


def test_skill_invocation_endpoint_contract_is_ready() -> None:
    service = get_skill_catalog_service()
    pack = service.build_employee_skill_pack("design-lead")
    skill = pack.professional_skills[0]

    result = service.invoke_skill(
        employee_id="design-lead",
        skill_id=skill.skill_id,
        request=SkillInvocationRequest(user_goal="为一个 B2B dashboard 给出 UX 结构建议"),
    )

    assert result.status == "ready"
    assert result.skill_id == skill.skill_id
    assert result.source_ref.repo_name == skill.source_ref.repo_name
    assert result.source_excerpt.strip()
    assert "GitHub-sourced skill contract" in result.invocation_prompt
