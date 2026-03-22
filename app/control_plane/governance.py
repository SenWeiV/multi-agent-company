from __future__ import annotations

from app.company.bootstrap import COMPANY_PROFILE
from app.company.models import BudgetScope, BudgetPolicy, TriggerPolicy, TriggerType
from app.control_plane.models import (
    BudgetCheck,
    BudgetDecisionStatus,
    TriggerContext,
    TriggerValidationStatus,
)
from app.executive_office.models import CEOCommand, CommandClassificationResult, InteractionMode

DEFAULT_COST_BY_MODE: dict[InteractionMode, float] = {
    InteractionMode.IDEA_CAPTURE: 5,
    InteractionMode.QUICK_CONSULT: 20,
    InteractionMode.DEPARTMENT_TASK: 60,
    InteractionMode.FORMAL_PROJECT: 90,
    InteractionMode.REVIEW_DECISION: 30,
    InteractionMode.OVERRIDE_RECOVERY: 20,
    InteractionMode.ESCALATION: 25,
}

HEARTBEAT_ALLOWED_DEPARTMENTS = {
    "Executive Office",
    "Research & Intelligence",
    "Project Management",
    "Business Operations",
    "Growth & Marketing",
    "Customer Success & Support",
}


class BudgetPolicyService:
    def evaluate(
        self,
        command: CEOCommand,
        classification: CommandClassificationResult,
    ) -> list[BudgetCheck]:
        estimated_cost = command.budget_estimate or DEFAULT_COST_BY_MODE[classification.interaction_mode]
        checks: list[BudgetCheck] = []

        for policy in COMPANY_PROFILE.budget_policy:
            checks.append(
                self._evaluate_policy(
                    policy=policy,
                    estimated_cost=estimated_cost,
                    override_requested=command.budget_override_requested,
                )
            )

        return checks

    def has_blocking_issue(self, checks: list[BudgetCheck]) -> bool:
        return any(check.status == BudgetDecisionStatus.BLOCKED for check in checks)

    def _evaluate_policy(
        self,
        policy: BudgetPolicy,
        estimated_cost: float,
        override_requested: bool,
    ) -> BudgetCheck:
        if policy.limit is None:
            return BudgetCheck(
                scope=policy.scope,
                estimated_cost=estimated_cost,
                limit=None,
                warning_threshold=policy.warning_threshold,
                status=BudgetDecisionStatus.OK,
                requires_approval=False,
                override_rule=policy.override_rule,
                message="No hard limit configured for this scope.",
            )

        warning_limit = policy.limit * policy.warning_threshold
        if estimated_cost > policy.limit and policy.hard_stop and not override_requested:
            return BudgetCheck(
                scope=policy.scope,
                estimated_cost=estimated_cost,
                limit=policy.limit,
                warning_threshold=policy.warning_threshold,
                status=BudgetDecisionStatus.BLOCKED,
                requires_approval=True,
                override_rule=policy.override_rule,
                message=f"Estimated cost exceeds {policy.scope.value} hard limit.",
            )

        if estimated_cost > policy.limit and override_requested:
            return BudgetCheck(
                scope=policy.scope,
                estimated_cost=estimated_cost,
                limit=policy.limit,
                warning_threshold=policy.warning_threshold,
                status=BudgetDecisionStatus.WARNING,
                requires_approval=True,
                override_rule=policy.override_rule,
                message=f"Estimated cost exceeds {policy.scope.value} hard limit but override was requested.",
            )

        if estimated_cost >= warning_limit:
            return BudgetCheck(
                scope=policy.scope,
                estimated_cost=estimated_cost,
                limit=policy.limit,
                warning_threshold=policy.warning_threshold,
                status=BudgetDecisionStatus.WARNING,
                requires_approval=False,
                override_rule=policy.override_rule,
                message=f"Estimated cost reached {policy.scope.value} warning threshold.",
            )

        return BudgetCheck(
            scope=policy.scope,
            estimated_cost=estimated_cost,
            limit=policy.limit,
            warning_threshold=policy.warning_threshold,
            status=BudgetDecisionStatus.OK,
            requires_approval=False,
            override_rule=policy.override_rule,
            message=f"Estimated cost is within {policy.scope.value} budget.",
        )


class TriggerScheduler:
    def validate(
        self,
        command: CEOCommand,
        classification: CommandClassificationResult,
    ) -> TriggerContext:
        policy = self._policy_for(command.trigger_type)

        if command.trigger_type != TriggerType.SCHEDULED_HEARTBEAT:
            return TriggerContext(
                trigger_type=command.trigger_type,
                status=TriggerValidationStatus.ACCEPTED,
                routing_rule=policy.routing_rule,
                recurring_work=None,
                message="Trigger accepted for V1 intake.",
            )

        allowed_departments = [
            department
            for department in classification.recommended_departments
            if department in HEARTBEAT_ALLOWED_DEPARTMENTS
        ]

        if not allowed_departments:
            return TriggerContext(
                trigger_type=command.trigger_type,
                status=TriggerValidationStatus.REJECTED,
                routing_rule=policy.routing_rule,
                recurring_work=None,
                message="Heartbeat can only activate predefined recurring-work departments in V1.",
            )

        return TriggerContext(
            trigger_type=command.trigger_type,
            status=TriggerValidationStatus.ACCEPTED,
            routing_rule=policy.routing_rule,
            recurring_work=", ".join(allowed_departments),
            message="Heartbeat accepted and routed to recurring-work intake.",
        )

    def _policy_for(self, trigger_type: TriggerType) -> TriggerPolicy:
        for policy in COMPANY_PROFILE.trigger_defaults:
            if policy.trigger_type == trigger_type:
                return policy
        raise ValueError(f"Unsupported trigger type: {trigger_type}")


def budget_scope_rank(scope: BudgetScope) -> int:
    order = {
        BudgetScope.COMPANY: 0,
        BudgetScope.DEPARTMENT: 1,
        BudgetScope.EMPLOYEE: 2,
        BudgetScope.TASK: 3,
    }
    return order[scope]
