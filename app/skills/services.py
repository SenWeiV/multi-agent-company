from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.company.bootstrap import get_employees
from app.skills.models import (
    EmployeeSkillPack,
    NativeSkillExport,
    NativeSkillExportFile,
    SkillCatalogValidationResult,
    SkillInvocationRecord,
    SkillInvocationRequest,
    SkillInvocationResult,
    SkillManifest,
    SkillSourceRef,
    SkillValidationIssue,
)
from app.store import ModelStore, build_model_store


@dataclass(frozen=True)
class LockedRepository:
    repo_name: str
    repo_url: str
    commit_sha: str
    license: str
    default_branch: str
    include_paths: tuple[str, ...]
    exclude_names: tuple[str, ...]


@dataclass(frozen=True)
class SkillCandidate:
    repo_name: str
    repo_url: str
    commit_sha: str
    license: str
    path: str
    local_path: Path
    name: str
    summary: str
    tags: tuple[str, ...]


LOCK_PATH = Path(__file__).with_name("skill_sources.lock.json")
SYNC_ROOT = Path.cwd() / "third_party" / "skills" / "repos"

GENERAL_SKILL_PATHS: tuple[tuple[str, str], ...] = (
    ("awesome-claude-code-subagents", "categories/01-core-development/api-designer.md"),
    ("awesome-claude-code-subagents", "categories/08-business-product/business-analyst.md"),
    ("awesome-claude-code-subagents", "categories/06-developer-experience/documentation-engineer.md"),
    ("awesome-claude-code-subagents", "categories/04-quality-security/debugger.md"),
    ("awesome-claude-code-subagents", "categories/04-quality-security/code-reviewer.md"),
    ("awesome-claude-code-subagents", "categories/04-quality-security/architect-reviewer.md"),
    ("awesome-claude-code-subagents", "categories/05-data-ai/data-analyst.md"),
    ("awesome-claude-code-subagents", "categories/05-data-ai/prompt-engineer.md"),
    ("awesome-claude-code-subagents", "categories/06-developer-experience/refactoring-specialist.md"),
    ("awesome-claude-code-subagents", "categories/06-developer-experience/dependency-manager.md"),
)

ROLE_PRIORITY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "chief-of-staff": (
        "chief",
        "staff",
        "orchestrator",
        "producer",
        "project",
        "manager",
        "business",
        "strategy",
        "legal",
        "compliance",
        "executive",
        "documentation",
        "reviewer",
        "facilitation",
        "ops",
    ),
    "product-lead": (
        "product",
        "prioritizer",
        "business",
        "journey",
        "pricing",
        "discovery",
        "roadmap",
        "opportunity",
        "story",
        "epic",
        "persona",
        "problem",
        "strategy",
        "market",
        "customer",
        "positioning",
    ),
    "research-lead": (
        "research",
        "trend",
        "signal",
        "analyst",
        "data",
        "scientist",
        "llm",
        "nlp",
        "market",
        "prompt",
        "company",
        "competitor",
        "paper",
    ),
    "delivery-lead": (
        "project",
        "manager",
        "workflow",
        "delivery",
        "roadmap",
        "dependency",
        "documentation",
        "build",
        "planning",
        "ops",
        "incident",
        "refactoring",
        "facilitation",
    ),
    "design-lead": (
        "design",
        "ux",
        "ui",
        "visual",
        "storyboard",
        "journey",
        "persona",
        "accessibility",
        "interaction",
        "content",
        "architecture",
    ),
    "engineering-lead": (
        "engineering",
        "backend",
        "frontend",
        "fullstack",
        "api",
        "graphql",
        "microservices",
        "websocket",
        "database",
        "cloud",
        "deployment",
        "devops",
        "docker",
        "kubernetes",
        "python",
        "typescript",
        "java",
        "react",
        "architect",
        "security",
        "sre",
    ),
    "quality-lead": (
        "quality",
        "qa",
        "test",
        "testing",
        "reviewer",
        "review",
        "evidence",
        "reality",
        "debugger",
        "security",
        "performance",
        "chaos",
        "compliance",
        "accessibility",
        "contract",
        "visual",
        "reporting",
    ),
}

ROLE_ADJACENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "chief-of-staff": ("product", "delivery", "quality", "research"),
    "product-lead": ("design", "research", "quality", "delivery"),
    "research-lead": ("product", "design", "strategy"),
    "delivery-lead": ("engineering", "quality", "product"),
    "design-lead": ("product", "research", "accessibility"),
    "engineering-lead": ("quality", "delivery", "design"),
    "quality-lead": ("engineering", "delivery", "security"),
}

ROLE_SUMMARY_HINTS: dict[str, str] = {
    "chief-of-staff": "适合 Chief of Staff 做组织、framing、路由和高层综合。",
    "product-lead": "适合 Product Lead 做价值、优先级、范围和版本判断。",
    "research-lead": "适合 Research Lead 做趋势、竞品、市场和证据研究。",
    "delivery-lead": "适合 Delivery Lead 做推进、依赖、计划和风险收口。",
    "design-lead": "适合 Design Lead 做用户洞察、信息架构和体验判断。",
    "engineering-lead": "适合 Engineering Lead 做技术方案、实现路径和工程风险判断。",
    "quality-lead": "适合 Quality Lead 做验证、证据收集、质量门禁和 go/no-go 判断。",
}


class SkillCatalogService:
    def __init__(self, invocation_store: ModelStore[SkillInvocationRecord]) -> None:
        self._invocations = invocation_store

    def build_employee_skill_pack(self, employee_id: str) -> EmployeeSkillPack:
        employee = next((item for item in get_employees() if item.employee_id == employee_id), None)
        if employee is None:
            raise KeyError(employee_id)

        candidates = self._scan_skill_candidates()
        general_skills = [self._manifest_for_general(candidate) for candidate in candidates if self._is_general_candidate(candidate)]
        general_skills = general_skills[:10]

        professional_candidates = [
            candidate
            for candidate in candidates
            if not self._is_general_candidate(candidate)
        ]
        scored = sorted(
            professional_candidates,
            key=lambda candidate: (
                self._role_score(employee_id, candidate),
                self._source_priority(candidate),
                candidate.name,
            ),
            reverse=True,
        )
        selected: list[SkillManifest] = []
        selected_ids: set[str] = set()
        for candidate in scored:
            if self._role_score(employee_id, candidate) <= 0:
                continue
            manifest = self._manifest_for_role(employee_id, candidate)
            if manifest.skill_id in selected_ids:
                continue
            selected.append(manifest)
            selected_ids.add(manifest.skill_id)
            if len(selected) >= 30:
                break

        if len(selected) < 30:
            fallback_candidates = [candidate for candidate in professional_candidates if self._skill_id_for(candidate) not in selected_ids]
            for candidate in fallback_candidates:
                manifest = self._manifest_for_role(employee_id, candidate)
                selected.append(manifest)
                selected_ids.add(manifest.skill_id)
                if len(selected) >= 30:
                    break

        return EmployeeSkillPack(
            professional_skills=selected[:30],
            general_skills=general_skills[:10],
        )

    def build_native_skill_exports(self, employee_id: str) -> list[NativeSkillExport]:
        pack = self.build_employee_skill_pack(employee_id)
        exports: list[NativeSkillExport] = []
        for manifest in [*pack.professional_skills, *pack.general_skills]:
            exports.append(self._native_export_for(employee_id, manifest))
        return exports

    def invoke_skill(
        self,
        *,
        employee_id: str,
        skill_id: str,
        request: SkillInvocationRequest | None = None,
    ) -> SkillInvocationResult:
        request = request or SkillInvocationRequest()
        skill = self._get_skill_for_employee(employee_id, skill_id)
        source_path = Path(skill.source_ref.local_path)
        if not source_path.exists():
            detail = f"Local skill source missing: {source_path}"
            self._record_invocation(employee_id, skill_id, skill.scope, "failed", detail)
            return SkillInvocationResult(
                employee_id=employee_id,
                skill_id=skill.skill_id,
                skill_name=skill.skill_name,
                scope=skill.scope,
                entrypoint_type=skill.entrypoint_type,
                source_ref=skill.source_ref,
                invocation_prompt="",
                source_excerpt="",
                status="failed",
                detail=detail,
            )

        source_text = source_path.read_text(encoding="utf-8")
        excerpt = self._source_excerpt(source_text)
        invocation_prompt = (
            f"Skill `{skill.skill_name}` ({skill.skill_id})\n"
            f"Role owner: {employee_id}\n"
            f"Use case: {request.user_goal or 'general'}\n"
            f"Source: {skill.source_ref.repo_name}@{skill.source_ref.commit_sha}:{skill.source_ref.path}\n"
            f"Why this skill fits: {skill.fit_rationale or 'role-aligned skill'}\n\n"
            "Apply the following GitHub-sourced skill contract:\n"
            f"{excerpt}\n"
        )
        self._record_invocation(employee_id, skill_id, skill.scope, "ready", None)
        return SkillInvocationResult(
            employee_id=employee_id,
            skill_id=skill.skill_id,
            skill_name=skill.skill_name,
            scope=skill.scope,
            entrypoint_type=skill.entrypoint_type,
            source_ref=skill.source_ref,
            invocation_prompt=invocation_prompt,
            source_excerpt=excerpt,
            status="ready",
        )

    def list_invocations(self, limit: int = 50) -> list[SkillInvocationRecord]:
        records = self._invocations.list()
        records.sort(key=lambda item: item.created_at, reverse=True)
        return records[:limit]

    def validate_catalog(self) -> SkillCatalogValidationResult:
        issues: list[SkillValidationIssue] = []
        professional_skill_count_by_employee: dict[str, int] = {}
        general_skill_count_by_employee: dict[str, int] = {}

        for employee in get_employees():
            if employee.department not in {
                "Executive Office",
                "Product",
                "Research & Intelligence",
                "Project Management",
                "Design & UX",
                "Engineering",
                "Quality",
            }:
                continue
            pack = self.build_employee_skill_pack(employee.employee_id)
            professional_skill_count_by_employee[employee.employee_id] = len(pack.professional_skills)
            general_skill_count_by_employee[employee.employee_id] = len(pack.general_skills)

            if len(pack.professional_skills) < 30:
                issues.append(
                    SkillValidationIssue(
                        employee_id=employee.employee_id,
                        issue_type="professional_skill_count",
                        detail=f"{employee.employee_id} has only {len(pack.professional_skills)} professional skills.",
                    )
                )
            if len(pack.general_skills) < 10:
                issues.append(
                    SkillValidationIssue(
                        employee_id=employee.employee_id,
                        issue_type="general_skill_count",
                        detail=f"{employee.employee_id} has only {len(pack.general_skills)} general skills.",
                    )
                )

            for manifest in [*pack.professional_skills, *pack.general_skills]:
                issue = self.validate_manifest(employee.employee_id, manifest)
                if issue is not None:
                    issues.append(issue)
                    continue
                invocation_result = self.invoke_skill(
                    employee_id=employee.employee_id,
                    skill_id=manifest.skill_id,
                    request=SkillInvocationRequest(user_goal=f"verify {manifest.skill_id}"),
                )
                if invocation_result.status != "ready" or not invocation_result.source_excerpt.strip():
                    issues.append(
                        SkillValidationIssue(
                            employee_id=employee.employee_id,
                            skill_id=manifest.skill_id,
                            issue_type="result_validation",
                            detail=invocation_result.detail or "skill invocation returned empty excerpt",
                        )
                    )

        return SkillCatalogValidationResult(
            ok=not issues,
            professional_skill_count_by_employee=professional_skill_count_by_employee,
            general_skill_count_by_employee=general_skill_count_by_employee,
            issues=issues,
        )

    def validate_manifest(self, employee_id: str, manifest: SkillManifest) -> SkillValidationIssue | None:
        return self._validate_manifest(employee_id, manifest)

    def _validate_manifest(self, employee_id: str, manifest: SkillManifest) -> SkillValidationIssue | None:
        source = manifest.source_ref
        if not all(
            [
                source.repo_url,
                source.repo_name,
                source.commit_sha,
                source.path,
                source.license,
                source.install_method,
                source.verify_command,
                source.local_path,
            ]
        ):
            return SkillValidationIssue(
                employee_id=employee_id,
                skill_id=manifest.skill_id,
                issue_type="source_validation",
                detail="source metadata incomplete",
            )
        if source.license.strip().lower() not in {"mit", "apache-2.0", "bsd-3-clause", "bsd-2-clause"}:
            return SkillValidationIssue(
                employee_id=employee_id,
                skill_id=manifest.skill_id,
                issue_type="license_validation",
                detail=f"unsupported license: {source.license}",
            )
        if not Path(source.local_path).exists():
            return SkillValidationIssue(
                employee_id=employee_id,
                skill_id=manifest.skill_id,
                issue_type="install_validation",
                detail=f"missing local source file: {source.local_path}",
            )
        return None

    def _get_skill_for_employee(self, employee_id: str, skill_id: str) -> SkillManifest:
        pack = self.build_employee_skill_pack(employee_id)
        for manifest in [*pack.professional_skills, *pack.general_skills]:
            if manifest.skill_id == skill_id:
                return manifest
        raise KeyError(skill_id)

    def _record_invocation(
        self,
        employee_id: str,
        skill_id: str,
        scope: str,
        status: str,
        detail: str | None,
    ) -> None:
        self._invocations.save(
            SkillInvocationRecord(
                invocation_id=f"si-{uuid4().hex[:8]}",
                employee_id=employee_id,
                skill_id=skill_id,
                scope=scope,  # type: ignore[arg-type]
                status=status,  # type: ignore[arg-type]
                detail=detail,
            )
        )

    def _manifest_for_general(self, candidate: SkillCandidate) -> SkillManifest:
        skill_id = self._skill_id_for(candidate)
        return SkillManifest(
            skill_id=skill_id,
            skill_name=candidate.name,
            summary=candidate.summary,
            scope="general",
            role_owner=None,
            source_ref=self._source_ref_for(candidate),
            invocation_contract=self._invocation_contract(candidate, scope="general"),
            dependencies=[],
            tags=list(candidate.tags),
            fit_rationale="Shared general-purpose GitHub skill used across all seven core bots.",
        )

    def _manifest_for_role(self, employee_id: str, candidate: SkillCandidate) -> SkillManifest:
        skill_id = self._skill_id_for(candidate)
        return SkillManifest(
            skill_id=skill_id,
            skill_name=candidate.name,
            summary=candidate.summary,
            scope="professional",
            role_owner=employee_id,
            source_ref=self._source_ref_for(candidate),
            invocation_contract=self._invocation_contract(candidate, scope="professional"),
            dependencies=[],
            tags=list(candidate.tags),
            fit_rationale=ROLE_SUMMARY_HINTS.get(employee_id, "Role-aligned GitHub skill."),
        )

    def _native_export_for(self, employee_id: str, manifest: SkillManifest) -> NativeSkillExport:
        native_skill_name = self._native_skill_name_for(employee_id, manifest)
        relative_dir = f"skills/{native_skill_name}"
        skill_md_path = f"{relative_dir}/SKILL.md"
        skill_md_content = self._render_native_skill_markdown(employee_id, manifest, native_skill_name)
        files = [
            NativeSkillExportFile(
                path=skill_md_path,
                content=skill_md_content,
            )
        ]
        return NativeSkillExport(
            employee_id=employee_id,
            skill_id=manifest.skill_id,
            skill_name=manifest.skill_name,
            scope=manifest.scope,
            native_skill_name=native_skill_name,
            relative_dir=relative_dir,
            skill_md_path=skill_md_path,
            skill_md_content=skill_md_content,
            files=files,
            source_ref=manifest.source_ref,
            entrypoint_type=manifest.entrypoint_type,
            fit_rationale=manifest.fit_rationale,
        )

    def _native_skill_name_for(self, employee_id: str, manifest: SkillManifest) -> str:
        source_slug = f"{manifest.source_ref.repo_name}-{manifest.source_ref.path}"
        normalized = re.sub(r"[^a-z0-9]+", "-", source_slug.lower()).strip("-")
        digest = hashlib.sha1(f"{employee_id}:{manifest.skill_id}".encode("utf-8")).hexdigest()[:10]
        return f"opc-{employee_id}--{normalized[:72].rstrip('-')}-{digest}"

    def _render_native_skill_markdown(
        self,
        employee_id: str,
        manifest: SkillManifest,
        native_skill_name: str,
    ) -> str:
        source_path = Path(manifest.source_ref.local_path)
        excerpt = self._source_excerpt(source_path.read_text(encoding="utf-8")) if source_path.exists() else ""
        metadata = json.dumps(
            {
                "openclaw": {
                    "skillKey": native_skill_name,
                    "always": True,
                }
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        tags = ", ".join(manifest.tags or []) or "none"
        dependencies = ", ".join(manifest.dependencies or []) or "none"
        invocation_contract = json.dumps(manifest.invocation_contract or {}, ensure_ascii=False, sort_keys=True)
        return (
            "---\n"
            f"name: {native_skill_name}\n"
            f"description: {manifest.summary[:180]}\n"
            f"metadata: {metadata}\n"
            "user-invocable: true\n"
            "---\n\n"
            f"# {manifest.skill_name}\n\n"
            f"- Employee owner: `{employee_id}`\n"
            f"- Scope: `{manifest.scope}`\n"
            f"- Source: `{manifest.source_ref.repo_name}@{manifest.source_ref.commit_sha}:{manifest.source_ref.path}`\n"
            f"- License: `{manifest.source_ref.license}`\n"
            f"- Install: `{manifest.source_ref.install_method}`\n"
            f"- Verify: `{manifest.source_ref.verify_command}`\n"
            f"- Entrypoint type: `{manifest.entrypoint_type}`\n"
            f"- Tags: {tags}\n"
            f"- Dependencies: {dependencies}\n"
            f"- Fit rationale: {manifest.fit_rationale or 'role-aligned GitHub skill'}\n"
            f"- Invocation contract: `{invocation_contract}`\n\n"
            "## When To Use\n"
            f"{manifest.summary}\n\n"
            "## GitHub-Sourced Skill Contract\n"
            f"{excerpt or '- no local excerpt available'}\n"
        )

    def _source_ref_for(self, candidate: SkillCandidate) -> SkillSourceRef:
        return SkillSourceRef(
            repo_url=candidate.repo_url,
            repo_name=candidate.repo_name,
            commit_sha=candidate.commit_sha,
            path=candidate.path,
            license=candidate.license,
            install_method=f"python scripts/sync_skills.py --repo {candidate.repo_name}",
            verify_command="python -m pytest -q tests/test_skill_catalog.py",
            local_path=str(candidate.local_path),
        )

    def _invocation_contract(self, candidate: SkillCandidate, *, scope: str) -> dict[str, Any]:
        return {
            "entrypoint": "skill_catalog_runner",
            "scope": scope,
            "mode": "instructional_skill",
            "source_repo": candidate.repo_name,
            "path": candidate.path,
        }

    def _scan_skill_candidates(self) -> list[SkillCandidate]:
        repositories = self._locked_repositories()
        candidates: list[SkillCandidate] = []
        for repo in repositories:
            repo_root = SYNC_ROOT / repo.repo_name / repo.commit_sha
            if not repo_root.exists():
                continue
            for include_path in repo.include_paths:
                include_root = repo_root / include_path
                if not include_root.exists():
                    continue
                for source_path in include_root.rglob("*.md"):
                    if source_path.name in repo.exclude_names:
                        continue
                    relative_path = source_path.relative_to(repo_root).as_posix()
                    tags = self._tags_for(relative_path)
                    summary = self._summary_for(source_path)
                    candidates.append(
                        SkillCandidate(
                            repo_name=repo.repo_name,
                            repo_url=repo.repo_url,
                            commit_sha=repo.commit_sha,
                            license=repo.license,
                            path=relative_path,
                            local_path=source_path,
                            name=self._skill_name_for(relative_path),
                            summary=summary,
                            tags=tags,
                        )
                    )
        deduped: dict[str, SkillCandidate] = {}
        for candidate in candidates:
            deduped[self._skill_id_for(candidate)] = candidate
        return list(deduped.values())

    def _source_priority(self, candidate: SkillCandidate) -> int:
        if candidate.repo_name == "agency-agents":
            return 3
        if candidate.repo_name == "awesome-claude-code-subagents":
            return 2
        return 1

    def _role_score(self, employee_id: str, candidate: SkillCandidate) -> int:
        tags = set(candidate.tags)
        keywords = ROLE_PRIORITY_KEYWORDS.get(employee_id, ())
        adjacent = ROLE_ADJACENT_KEYWORDS.get(employee_id, ())
        score = 0
        for keyword in keywords:
            if keyword in tags:
                score += 4
        for keyword in adjacent:
            if keyword in tags:
                score += 2

        if employee_id == "chief-of-staff" and candidate.repo_name == "agency-agents":
            if any(token in tags for token in ("project", "specialized", "orchestrator")):
                score += 8
        if employee_id == "product-lead" and candidate.repo_name == "agency-agents" and "product" in tags:
            score += 8
        if employee_id == "research-lead" and candidate.repo_name == "agency-agents" and any(token in tags for token in ("research", "trend")):
            score += 8
        if employee_id == "delivery-lead" and candidate.repo_name == "agency-agents" and any(token in tags for token in ("project", "delivery")):
            score += 8
        if employee_id == "design-lead" and candidate.repo_name == "agency-agents" and "design" in tags:
            score += 8
        if employee_id == "engineering-lead" and candidate.repo_name == "agency-agents" and "engineering" in tags:
            score += 8
        if employee_id == "quality-lead" and candidate.repo_name == "agency-agents" and any(token in tags for token in ("testing", "quality")):
            score += 8
        return score

    def _skill_name_for(self, relative_path: str) -> str:
        stem = Path(relative_path).stem.replace("-", " ").replace("_", " ").strip()
        return " ".join(part.capitalize() for part in stem.split())

    def _summary_for(self, source_path: Path) -> str:
        text = source_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip().lstrip("#").strip()
            if len(stripped) >= 16:
                return stripped[:180]
        return self._skill_name_for(source_path.name)

    def _tags_for(self, relative_path: str) -> tuple[str, ...]:
        normalized = relative_path.lower().replace(".md", "")
        tokens = re.split(r"[^a-z0-9]+", normalized)
        alias_tokens: list[str] = []
        if "project-management" in normalized:
            alias_tokens.extend(["project", "delivery"])
        if "testing" in normalized or "qa" in normalized:
            alias_tokens.extend(["quality", "testing"])
        if "design" in normalized:
            alias_tokens.extend(["design", "ux", "ui"])
        if "product" in normalized:
            alias_tokens.extend(["product", "business"])
        if "engineering" in normalized:
            alias_tokens.extend(["engineering", "architect"])
        if "specialized" in normalized:
            alias_tokens.extend(["specialized", "orchestrator"])
        return tuple(dict.fromkeys([*(token for token in tokens if token), *alias_tokens]))

    def _skill_id_for(self, candidate: SkillCandidate) -> str:
        slug = candidate.path.replace("/", "__").replace(".md", "").replace("-", "_")
        return f"{candidate.repo_name}::{slug}"

    def _is_general_candidate(self, candidate: SkillCandidate) -> bool:
        return (candidate.repo_name, candidate.path) in GENERAL_SKILL_PATHS

    def _source_excerpt(self, source_text: str) -> str:
        lines = [line.rstrip() for line in source_text.splitlines() if line.strip()]
        excerpt = "\n".join(lines[:40]).strip()
        return excerpt[:4000]

    def _locked_repositories(self) -> list[LockedRepository]:
        payload = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        return [
            LockedRepository(
                repo_name=item["repo_name"],
                repo_url=item["repo_url"],
                commit_sha=item["commit_sha"],
                license=item["license"],
                default_branch=item.get("default_branch", "main"),
                include_paths=tuple(item.get("include_paths", [])),
                exclude_names=tuple(item.get("exclude_names", [])),
            )
            for item in payload.get("repositories", [])
        ]


_skill_catalog_service = SkillCatalogService(
    invocation_store=build_model_store(SkillInvocationRecord, "invocation_id", "skill_invocations"),
)


def get_skill_catalog_service() -> SkillCatalogService:
    return _skill_catalog_service


def sync_skill_repositories() -> list[str]:
    payload = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    SYNC_ROOT.mkdir(parents=True, exist_ok=True)
    synced_paths: list[str] = []
    for repo in payload.get("repositories", []):
        repo_name = repo["repo_name"]
        repo_url = repo["repo_url"]
        commit_sha = repo["commit_sha"]
        include_paths = repo.get("include_paths", [])
        target_root = SYNC_ROOT / repo_name / commit_sha
        target_root.mkdir(parents=True, exist_ok=True)
        tmp_root = Path(subprocess.check_output(["mktemp", "-d"], text=True).strip())
        clone_root = tmp_root / repo_name
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(clone_root)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(["git", "-C", str(clone_root), "checkout", commit_sha], check=True, capture_output=True, text=True)
        for include_path in include_paths:
            include_root = clone_root / include_path
            if not include_root.exists():
                continue
            for source_path in include_root.rglob("*.md"):
                if source_path.name in set(repo.get("exclude_names", [])):
                    continue
                relative_path = source_path.relative_to(clone_root)
                destination = target_root / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
                synced_paths.append(str(destination))
        license_src = clone_root / "LICENSE"
        if license_src.exists():
            (target_root / "LICENSE").write_text(license_src.read_text(encoding="utf-8"), encoding="utf-8")
    return synced_paths
