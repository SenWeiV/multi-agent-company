from app.company.models import (
    ActivationLevel,
    BudgetPolicy,
    BudgetScope,
    CompanyProfile,
    DepartmentSeatMapEntry,
    TriggerPolicy,
    TriggerType,
    VirtualDepartment,
    VirtualEmployee,
)

MANUAL_TRIGGER = TriggerPolicy(
    trigger_type=TriggerType.MANUAL,
    routing_rule="executive_office_intake",
)

EVENT_TRIGGER = TriggerPolicy(
    trigger_type=TriggerType.EVENT_BASED,
    event_source="system_event_bus",
    routing_rule="chief_of_staff_triage",
)

HEARTBEAT_TRIGGER = TriggerPolicy(
    trigger_type=TriggerType.SCHEDULED_HEARTBEAT,
    schedule="0 */6 * * *",
    routing_rule="heartbeat_summary_then_route",
)

COMPANY_PROFILE = CompanyProfile(
    company_id="default",
    company_name="One-Person Company",
    company_type="AI Product Studio",
    stage="v1_bootstrap",
    strategic_focus=[
        "构建一个 human CEO 驱动的虚拟公司操作系统",
        "优先落地 Executive Office、核心 7 部门和最小 control plane",
    ],
    default_departments=[
        "Executive Office",
        "Product",
        "Research & Intelligence",
        "Project Management",
        "Design & UX",
        "Engineering",
        "Quality",
    ],
    activation_policy={
        "always_on": [
            "Executive Office",
            "Product",
            "Research & Intelligence",
            "Project Management",
            "Design & UX",
            "Engineering",
            "Quality",
        ],
        "on_demand": [
            "Growth & Marketing",
            "Customer Success & Support",
        ],
        "situational_expansion": [
            "Sales & Partnerships",
            "Business Operations",
            "Trust / Security / Legal",
        ],
    },
    budget_policy=[
        BudgetPolicy(
            scope=BudgetScope.COMPANY,
            limit=5000,
            override_rule="ceo_or_chief_of_staff_approval",
        ),
        BudgetPolicy(
            scope=BudgetScope.DEPARTMENT,
            limit=1000,
            override_rule="chief_of_staff_approval",
        ),
        BudgetPolicy(
            scope=BudgetScope.EMPLOYEE,
            limit=500,
            override_rule="chief_of_staff_approval",
        ),
        BudgetPolicy(
            scope=BudgetScope.TASK,
            limit=100,
            override_rule="ticket_level_override",
        ),
    ],
    trigger_defaults=[
        MANUAL_TRIGGER,
        EVENT_TRIGGER,
        HEARTBEAT_TRIGGER,
    ],
)

DEPARTMENTS = [
    VirtualDepartment(
        department_name="Executive Office",
        charter="公司 intake、路由、综合与经营节奏管理。",
        activation_level=ActivationLevel.ALWAYS_ON,
        default_employee="chief-of-staff",
        upstream_sources=[
            "Studio Producer",
            "Senior Project Manager",
            "Agents Orchestrator",
        ],
        budget_scope=BudgetScope.DEPARTMENT,
        heartbeat_policy=HEARTBEAT_TRIGGER,
    ),
    VirtualDepartment(
        department_name="Product",
        charter="产品方向、优先级与版本取舍。",
        activation_level=ActivationLevel.ALWAYS_ON,
        default_employee="product-lead",
        upstream_sources=["Sprint Prioritizer"],
        budget_scope=BudgetScope.DEPARTMENT,
    ),
    VirtualDepartment(
        department_name="Research & Intelligence",
        charter="趋势、竞品、用户与市场信号采集。",
        activation_level=ActivationLevel.ALWAYS_ON,
        default_employee="research-lead",
        upstream_sources=["Trend Researcher"],
        budget_scope=BudgetScope.DEPARTMENT,
        heartbeat_policy=HEARTBEAT_TRIGGER,
    ),
    VirtualDepartment(
        department_name="Project Management",
        charter="任务图、依赖、范围与推进节奏管理。",
        activation_level=ActivationLevel.ALWAYS_ON,
        default_employee="delivery-lead",
        upstream_sources=["Senior Project Manager", "Project Shepherd"],
        budget_scope=BudgetScope.DEPARTMENT,
        heartbeat_policy=HEARTBEAT_TRIGGER,
    ),
    VirtualDepartment(
        department_name="Design & UX",
        charter="体验结构、研究转设计与交互方案。",
        activation_level=ActivationLevel.ALWAYS_ON,
        default_employee="design-lead",
        upstream_sources=["UX Researcher", "UX Architect"],
        budget_scope=BudgetScope.DEPARTMENT,
    ),
    VirtualDepartment(
        department_name="Engineering",
        charter="架构、实现、技术交付。",
        activation_level=ActivationLevel.ALWAYS_ON,
        default_employee="engineering-lead",
        upstream_sources=[
            "Backend Architect",
            "Frontend Developer",
            "Rapid Prototyper",
        ],
        budget_scope=BudgetScope.DEPARTMENT,
    ),
    VirtualDepartment(
        department_name="Quality",
        charter="证据采集、验收与 GO / NO-GO verdict。",
        activation_level=ActivationLevel.ALWAYS_ON,
        default_employee="quality-lead",
        upstream_sources=["Evidence Collector", "Reality Checker"],
        budget_scope=BudgetScope.DEPARTMENT,
    ),
    VirtualDepartment(
        department_name="Growth & Marketing",
        charter="增长、品牌、上线传播与分发。",
        activation_level=ActivationLevel.ON_DEMAND,
        default_employee="growth-lead",
        upstream_sources=["Growth Hacker", "Brand Guardian"],
        budget_scope=BudgetScope.DEPARTMENT,
        heartbeat_policy=HEARTBEAT_TRIGGER,
    ),
    VirtualDepartment(
        department_name="Sales & Partnerships",
        charter="合作、外联、BD 与商业机会。",
        activation_level=ActivationLevel.SITUATIONAL_EXPANSION,
        default_employee="partnerships-lead",
        upstream_sources=["Outbound Strategist", "Account Strategist"],
        budget_scope=BudgetScope.DEPARTMENT,
    ),
    VirtualDepartment(
        department_name="Customer Success & Support",
        charter="支持、反馈、留存与 FAQ。",
        activation_level=ActivationLevel.ON_DEMAND,
        default_employee="customer-success-lead",
        upstream_sources=["Support Responder"],
        budget_scope=BudgetScope.DEPARTMENT,
        heartbeat_policy=HEARTBEAT_TRIGGER,
    ),
    VirtualDepartment(
        department_name="Business Operations",
        charter="经营指标、预算口径与内部流程。",
        activation_level=ActivationLevel.SITUATIONAL_EXPANSION,
        default_employee="operations-lead",
        upstream_sources=["Studio Operations", "Finance Tracker"],
        budget_scope=BudgetScope.DEPARTMENT,
        heartbeat_policy=HEARTBEAT_TRIGGER,
    ),
    VirtualDepartment(
        department_name="Trust / Security / Legal",
        charter="合规、身份、风险与审计。",
        activation_level=ActivationLevel.SITUATIONAL_EXPANSION,
        default_employee="trust-compliance-lead",
        upstream_sources=[
            "Legal Compliance Checker",
            "Agentic Identity & Trust Architect",
            "Identity Graph Operator",
        ],
        budget_scope=BudgetScope.DEPARTMENT,
    ),
]

EMPLOYEES = [
    VirtualEmployee(
        employee_id="chief-of-staff",
        department="Executive Office",
        employee_name="Chief of Staff",
        source_persona_packs=[
            "Studio Producer",
            "Senior Project Manager",
            "Agents Orchestrator",
        ],
        operating_modes=["intake", "routing", "synthesis", "cadence"],
        kpis=["routing_accuracy", "sync_back_rate", "checkpoint_completion"],
        budget_scope=BudgetScope.EMPLOYEE,
        heartbeat_policy=HEARTBEAT_TRIGGER,
    ),
    VirtualEmployee(
        employee_id="product-lead",
        department="Product",
        employee_name="Product Lead",
        source_persona_packs=["Sprint Prioritizer"],
        operating_modes=["strategy", "build"],
        kpis=["priority_clarity", "scope_quality"],
        budget_scope=BudgetScope.EMPLOYEE,
    ),
    VirtualEmployee(
        employee_id="research-lead",
        department="Research & Intelligence",
        employee_name="Research Lead",
        source_persona_packs=["Trend Researcher"],
        operating_modes=["strategy", "discovery", "heartbeat"],
        kpis=["signal_quality", "reuse_rate"],
        budget_scope=BudgetScope.EMPLOYEE,
        heartbeat_policy=HEARTBEAT_TRIGGER,
    ),
    VirtualEmployee(
        employee_id="delivery-lead",
        department="Project Management",
        employee_name="Delivery Lead",
        source_persona_packs=["Senior Project Manager", "Project Shepherd"],
        operating_modes=["build", "heartbeat"],
        kpis=["dependency_health", "cycle_time"],
        budget_scope=BudgetScope.EMPLOYEE,
        heartbeat_policy=HEARTBEAT_TRIGGER,
    ),
    VirtualEmployee(
        employee_id="design-lead",
        department="Design & UX",
        employee_name="Design Lead",
        source_persona_packs=["UX Researcher", "UX Architect"],
        operating_modes=["discovery", "build"],
        kpis=["ux_clarity", "artifact_quality"],
        budget_scope=BudgetScope.EMPLOYEE,
    ),
    VirtualEmployee(
        employee_id="engineering-lead",
        department="Engineering",
        employee_name="Engineering Lead",
        source_persona_packs=[
            "Backend Architect",
            "Frontend Developer",
            "Rapid Prototyper",
        ],
        operating_modes=["build"],
        kpis=["delivery_success", "retry_rate"],
        budget_scope=BudgetScope.EMPLOYEE,
    ),
    VirtualEmployee(
        employee_id="quality-lead",
        department="Quality",
        employee_name="Quality Lead",
        source_persona_packs=["Evidence Collector", "Reality Checker"],
        operating_modes=["evidence", "verdict"],
        kpis=["evidence_quality", "go_no_go_precision"],
        budget_scope=BudgetScope.EMPLOYEE,
    ),
    VirtualEmployee(
        employee_id="growth-lead",
        department="Growth & Marketing",
        employee_name="Growth Lead",
        source_persona_packs=["Growth Hacker", "Brand Guardian"],
        operating_modes=["launch", "discovery"],
        kpis=["channel_fit", "message_quality"],
        budget_scope=BudgetScope.EMPLOYEE,
        heartbeat_policy=HEARTBEAT_TRIGGER,
    ),
    VirtualEmployee(
        employee_id="partnerships-lead",
        department="Sales & Partnerships",
        employee_name="Partnerships Lead",
        source_persona_packs=["Outbound Strategist", "Account Strategist"],
        operating_modes=["launch", "expansion"],
        kpis=["partner_quality", "pipeline_health"],
        budget_scope=BudgetScope.EMPLOYEE,
    ),
    VirtualEmployee(
        employee_id="customer-success-lead",
        department="Customer Success & Support",
        employee_name="Customer Success Lead",
        source_persona_packs=["Support Responder"],
        operating_modes=["launch", "post_launch"],
        kpis=["resolution_time", "feedback_quality"],
        budget_scope=BudgetScope.EMPLOYEE,
        heartbeat_policy=HEARTBEAT_TRIGGER,
    ),
    VirtualEmployee(
        employee_id="operations-lead",
        department="Business Operations",
        employee_name="Operations Lead",
        source_persona_packs=["Studio Operations", "Finance Tracker"],
        operating_modes=["monthly_review", "expansion"],
        kpis=["budget_health", "ops_consistency"],
        budget_scope=BudgetScope.EMPLOYEE,
        heartbeat_policy=HEARTBEAT_TRIGGER,
    ),
    VirtualEmployee(
        employee_id="trust-compliance-lead",
        department="Trust / Security / Legal",
        employee_name="Trust & Compliance Lead",
        source_persona_packs=[
            "Legal Compliance Checker",
            "Agentic Identity & Trust Architect",
            "Identity Graph Operator",
        ],
        operating_modes=["high_risk_review", "launch"],
        kpis=["risk_coverage", "audit_quality"],
        budget_scope=BudgetScope.EMPLOYEE,
    ),
]

SEAT_MAP = [
    DepartmentSeatMapEntry(
        department=employee.department,
        employee=employee.employee_id,
        source_persona_packs=employee.source_persona_packs,
        recipe_eligibility=employee.operating_modes,
        private_namespace=f"employee:{employee.employee_id}",
        department_namespace=f"department:{employee.department.lower().replace(' ', '-').replace('&', 'and').replace('/', '-')}",
        company_access_profile="authorized_company_shared",
    )
    for employee in EMPLOYEES
]


def get_company_profile() -> CompanyProfile:
    return COMPANY_PROFILE


def get_departments() -> list[VirtualDepartment]:
    return DEPARTMENTS


def get_employees() -> list[VirtualEmployee]:
    return EMPLOYEES


def get_seat_map() -> list[DepartmentSeatMapEntry]:
    return SEAT_MAP
