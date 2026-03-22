from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.company.bootstrap import COMPANY_PROFILE, get_departments
from app.company.models import GoalLineage, TriggerType, WorkTicket
from app.executive_office.models import (
    CEOCommand,
    CommandClassificationResult,
    GoalRequest,
    InteractionMode,
    ParticipationScope,
)


@dataclass(frozen=True)
class ModeRule:
    mode: InteractionMode
    keywords: tuple[str, ...]


MODE_RULES: tuple[ModeRule, ...] = (
    ModeRule(InteractionMode.OVERRIDE_RECOVERY, ("回滚", "停掉", "改方向", "恢复", "不要原方案", "rollback")),
    ModeRule(InteractionMode.ESCALATION, ("高风险", "冲突", "搞不定", "升级处理", "escalate")),
    ModeRule(InteractionMode.REVIEW_DECISION, ("上线吗", "复核", "review", "拍板", "过一下")),
    ModeRule(InteractionMode.FORMAL_PROJECT, ("mvp", "启动这个项目", "完整方案", "ship", "build a")),
    ModeRule(InteractionMode.DEPARTMENT_TASK, ("帮我做", "小任务", "让工程", "让设计", "让产品")),
    ModeRule(
        InteractionMode.QUICK_CONSULT,
        (
            "怎么看",
            "分析",
            "建议",
            "consult",
            "opinion",
            "研究",
            "调研",
            "趋势",
            "洞察",
            "上线",
            "发布",
            "增长",
            "推广",
            "分发",
            "渠道",
            "反馈",
            "支持",
            "留存",
            "launch",
            "growth",
            "gtm",
            "go to market",
        ),
    ),
    ModeRule(InteractionMode.IDEA_CAPTURE, ("想法", "先记一下", "以后再说", "idea")),
)

DEPARTMENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Executive Office": ("chief of staff",),
    "Engineering": ("工程", "开发", "代码", "技术", "engineering", "engineering lead"),
    "Design & UX": ("设计", "体验", "ux", "ui", "design", "design lead"),
    "Product": ("产品", "产品方向", "roadmap", "feature", "product lead"),
    "Research & Intelligence": ("研究", "调研", "竞品", "趋势", "research", "research lead"),
    "Project Management": ("项目", "排期", "推进", "依赖", "delivery", "project lead", "delivery lead"),
    "Quality": ("质量", "测试", "验收", "quality", "quality lead"),
    "Business Operations": ("预算", "运营", "经营", "finance", "operations"),
    "Growth & Marketing": ("增长", "推广", "分发", "渠道", "品牌", "内容", "拉新", "launch", "growth", "gtm"),
    "Sales & Partnerships": ("合作", "渠道合作", "bd", "商务", "partner", "partnership", "sales"),
    "Customer Success & Support": ("支持", "客服", "反馈", "留存", "faq", "support", "customer success"),
    "Trust / Security / Legal": ("合规", "法务", "隐私", "风险", "审计", "security", "legal", "compliance"),
}

DISCOVERY_DEPARTMENTS: tuple[str, ...] = (
    "Research & Intelligence",
    "Product",
    "Design & UX",
)

LAUNCH_GROWTH_CORE_DEPARTMENTS: tuple[str, ...] = (
    "Growth & Marketing",
    "Customer Success & Support",
)

LAUNCH_GROWTH_OPTIONAL_DEPARTMENTS: tuple[str, ...] = (
    "Sales & Partnerships",
    "Trust / Security / Legal",
)


class ExecutiveOfficeService:
    def __init__(self) -> None:
        self._known_departments = {department.department_name for department in get_departments()}

    def classify_command(self, command: CEOCommand) -> CommandClassificationResult:
        mode = command.interaction_mode or self._infer_mode(command.intent)
        scope = self._participation_scope_for(mode)
        departments = self._recommended_departments(command)
        workflow_recipe = self._workflow_recipe_for(command, mode, departments)
        scope = self._participation_scope_for(mode, workflow_recipe)
        if workflow_recipe == "discovery_synthesis":
            departments = list(dict.fromkeys([*DISCOVERY_DEPARTMENTS, *departments]))
        if workflow_recipe == "launch_growth":
            departments = list(
                dict.fromkeys(
                    [
                        *LAUNCH_GROWTH_CORE_DEPARTMENTS,
                        *[department for department in LAUNCH_GROWTH_OPTIONAL_DEPARTMENTS if department in departments],
                        *departments,
                    ]
                )
            )
        goal_lineage = self._build_goal_lineage(command)
        goal_request = self._build_goal_request(command, mode, scope, goal_lineage.goal_lineage_id, workflow_recipe)
        work_ticket = self._build_work_ticket(command, mode)

        return CommandClassificationResult(
            interaction_mode=mode,
            participation_scope=scope,
            trigger_type=command.trigger_type,
            workflow_recipe=workflow_recipe,
            recommended_departments=departments,
            goal_request=goal_request,
            goal_lineage=goal_lineage,
            work_ticket=work_ticket,
        )

    def _infer_mode(self, intent: str) -> InteractionMode:
        normalized = intent.lower()
        for rule in MODE_RULES:
            if any(keyword in normalized for keyword in rule.keywords):
                return rule.mode
        return InteractionMode.IDEA_CAPTURE

    def _participation_scope_for(
        self,
        mode: InteractionMode,
        workflow_recipe: str = "default",
    ) -> ParticipationScope:
        if mode == InteractionMode.IDEA_CAPTURE:
            return ParticipationScope.EXECUTIVE_ONLY
        if workflow_recipe in {"discovery_synthesis", "launch_growth"}:
            return ParticipationScope.MULTI_DEPARTMENT
        if mode in {InteractionMode.QUICK_CONSULT, InteractionMode.DEPARTMENT_TASK}:
            return ParticipationScope.SINGLE_DEPARTMENT
        if mode == InteractionMode.FORMAL_PROJECT:
            return ParticipationScope.FULL_PROJECT_CHAIN
        return ParticipationScope.MULTI_DEPARTMENT

    def _recommended_departments(self, command: CEOCommand) -> list[str]:
        departments: list[str] = []

        for hinted in command.activation_hint:
            if hinted in self._known_departments:
                departments.append(hinted)

        normalized = command.intent.lower()
        for department, keywords in DEPARTMENT_KEYWORDS.items():
            if department not in departments and any(keyword in normalized for keyword in keywords):
                departments.append(department)

        if not departments:
            departments.append("Executive Office")

        return departments

    def _build_goal_lineage(self, command: CEOCommand) -> GoalLineage:
        suffix = uuid4().hex[:8]
        initiative = command.expected_outcome or command.intent
        return GoalLineage(
            goal_lineage_id=f"gl-{suffix}",
            company_goal=COMPANY_PROFILE.strategic_focus[0],
            initiative=initiative,
            project_goal=command.expected_outcome or command.intent,
            task_goal=command.intent,
            execution_ref="pending",
        )

    def _build_goal_request(
        self,
        command: CEOCommand,
        mode: InteractionMode,
        scope: ParticipationScope,
        goal_lineage_ref: str,
        workflow_recipe: str,
    ) -> GoalRequest:
        deliverables = self._default_deliverables_for(mode)
        return GoalRequest(
            goal=command.intent,
            constraints=["single_company_v1", "docker_first_development"],
            deliverables=deliverables,
            risk_level="normal",
            approval_policy="default",
            interaction_mode=mode,
            participation_scope=scope,
            goal_lineage_ref=goal_lineage_ref,
            workflow_recipe=workflow_recipe,
        )

    def _build_work_ticket(self, command: CEOCommand, mode: InteractionMode) -> WorkTicket:
        suffix = uuid4().hex[:8]
        return WorkTicket(
            ticket_id=f"wt-{suffix}",
            title=command.intent[:80],
            ticket_type=mode.value,
            thread_ref=command.thread_ref or f"{command.surface}:draft:{suffix}",
            channel_ref=command.entry_channel,
            status="draft",
        )

    def _default_deliverables_for(self, mode: InteractionMode) -> list[str]:
        if mode == InteractionMode.IDEA_CAPTURE:
            return ["IdeaBrief"]
        if mode == InteractionMode.QUICK_CONSULT:
            return ["ConsultNote"]
        if mode == InteractionMode.DEPARTMENT_TASK:
            return ["TaskResult"]
        if mode == InteractionMode.FORMAL_PROJECT:
            return ["Deliverable", "EvidenceArtifact", "Checkpoint"]
        if mode == InteractionMode.REVIEW_DECISION:
            return ["DecisionRecord"]
        if mode == InteractionMode.OVERRIDE_RECOVERY:
            return ["OverrideDecision"]
        return ["EscalationSummary"]

    def _workflow_recipe_for(
        self,
        command: CEOCommand,
        mode: InteractionMode,
        departments: list[str],
    ) -> str:
        if mode == InteractionMode.FORMAL_PROJECT:
            return "product_build"

        if mode == InteractionMode.QUICK_CONSULT:
            normalized = command.intent.lower()
            has_discovery_department = any(department in DISCOVERY_DEPARTMENTS for department in departments)
            touches_execution_departments = any(
                department in {"Engineering", "Quality", "Project Management"} for department in departments
            )
            discovery_keywords = ("研究", "调研", "趋势", "洞察", "竞品", "discovery", "synthesis")
            if (
                has_discovery_department
                and not touches_execution_departments
                and (
                    command.trigger_type == TriggerType.SCHEDULED_HEARTBEAT
                    or any(keyword in normalized for keyword in discovery_keywords)
                )
            ):
                return "discovery_synthesis"

            has_launch_departments = any(
                department in (*LAUNCH_GROWTH_CORE_DEPARTMENTS, *LAUNCH_GROWTH_OPTIONAL_DEPARTMENTS)
                for department in departments
            )
            launch_keywords = (
                "上线",
                "发布",
                "增长",
                "推广",
                "分发",
                "渠道",
                "反馈",
                "支持",
                "留存",
                "launch",
                "growth",
                "rollout",
                "go to market",
                "gtm",
                "support",
                "feedback",
            )
            if (
                any(keyword in normalized for keyword in launch_keywords)
                and not touches_execution_departments
                and (
                    has_launch_departments
                    or "产品" in normalized
                    or "milestone" in normalized
                    or "ready" in normalized
                )
            ):
                return "launch_growth"

        return "default"
