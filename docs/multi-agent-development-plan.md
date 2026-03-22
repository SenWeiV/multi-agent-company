# One-Person Company：用户担任 CEO 的虚拟公司操作系统

本文将 `one-person-company` 定义为当前项目的上层产品概念。用户不是“调用多智能体系统的人”，而是这家虚拟公司的 `CEO`；系统内的 agents 不再主要以抽象 worker 叙事出现，而是作为各部门的 `虚拟员工` 协同工作。底层技术架构仍由 `multi-agent-company` 提供，但其职责已经进一步收敛为 `company control plane / governance / memory fabric / visible communication orchestration`；单个 agent 的原生 runtime、skills、tools、sessions、sandbox 与 provider/model routing 统一下沉到 `OpenClaw Agent Plane`。

组织原型固定为 `AI 产品工作室`。V1 采用“完整组织图 + 分层激活 + 每部门一个虚拟员工席位”的策略：公司图谱完整，默认只激活核心研发链路；每个席位可以由多个上游 `PersonaPack` 组合实现。

## 1. 目标与边界

### 目标

- 把当前方案从“部门化多智能体系统”升级为“用户担任 CEO 的一人公司操作系统”。
- 在不推翻底层引擎的前提下，新增 `Human CEO Layer`、`Executive Office Layer`、`Virtual Department Layer` 三层上层模型。
- 固定一套可执行的公司 operating model：
  `CEO Command -> Chief of Staff -> GoalRequest -> TaskGraph -> Department Activation -> WorkflowRecipe -> Quality Gate -> Synthesis`
- 将 `agency-agents` 的上游 role/recipe 资产重映射为 `department seat + employee pack`，而不是直接当运行时角色表。
- 为 V1 定义完整但分层激活的 12 个部门，并为每个部门给出默认 charter、席位与激活级别。

### 非目标

- 不把 `one-person-company` 误写成已经具备完全自治经营能力的“自动创业公司”。
- 不把 `agency-agents`、`Chief of Staff` 或 `Agents Orchestrator` 误写成底层 scheduler 实现。
- 不在本阶段更改仓库名、目录名或底层技术名；`multi-agent-company` 仍是引擎名。
- 不要求 V1 一次性让所有部门常驻参与所有工作流。
- 不把“每部门一个员工”硬编码成“一席位只能绑定一个 persona”。

### 成功标准

- 文档能清楚区分：
  `产品概念层(one-person-company)` 与 `技术架构层(multi-agent-company)`。
- 用户角色、部门角色、席位角色、上游 PersonaPack 的关系明确可映射。
- 至少四类正式 operating recipe 写清楚：
  `CEO Strategy Loop`
  `Product Build Loop`
  `Launch / Growth Loop`
  `Discovery / Synthesis Loop`
- 12 个部门都具备 charter、默认席位、激活策略、默认参与流程。
- Quality、memory、approval、checkpoint 都能用公司语义表达，但仍保持底层治理能力不变。

## 2. 架构分层

### 总体分层

```text
Human CEO Layer
  User intent, direction setting, priority, final approval

Executive Office Layer
  Chief of Staff, strategic routing, task normalization, company cadence

Virtual Department Layer
  Department charters, seat map, activation policy, virtual employees

Orchestration Layer
  Goal intake, task graph, scheduling, retries, synthesis

Workflow Recipe Layer
  CEO Strategy / Product Build / Launch / Discovery recipes

OpenClaw Agent Plane
  OpenClaw native agents
  workspace bootstrap
  tools / skills / sessions / sandbox / provider routing

Company Control Plane
  Goal intake
  WorkTicket / TaskGraph / RunTrace / Checkpoint
  company workflow orchestration

Visible Communication Orchestration
  FeishuMentionDispatch
  VisibleRoomPolicy
  fan-out, room mirroring, CEO-visible agent-to-agent exchange

Persona Asset Layer
  PersonaSourceAdapter
  EmployeePackCompiler
  PersonaPack, upstream role mapping, composite employee packs

Tool & Sandbox Layer
  Search, browser, code, docs, APIs, files, safe execution

Memory Fabric & Artifact Layer
  MemoryBridgeService
  CheckpointStore
  MemoryGovernanceService
  run / private / department / company memory, checkpoints, evidence, traces

Distribution Layer
  Claude Code / Cursor / OpenCode / Aider / Windsurf

Governance & Observability Layer
  Policy, approval, audit, metrics, replay, trust
```

### 默认正式项目流

```text
CEOCommand
  -> Executive Office intake
  -> GoalRequest normalization
  -> Department activation
  -> WorkflowRecipe selection
  -> TaskGraph execution
  -> Quality gate
  -> Executive synthesis
  -> CEO review / approval
  -> RunTrace + company checkpoint
```

### CEO Interaction Model

“默认正式项目流”不是 CEO 与虚拟员工交互的唯一入口。当前方案正式支持两大类交互：

- `正式项目流程`：
  明确 deliverable、跨部门协作、需要 Quality Gate 和 checkpoint。
- `轻量局部流程`：
  CEO 只是提想法、做咨询、下发单部门小任务、review、改向或升级冲突。

为此新增统一交互分类：

| 分类 | 说明 |
| --- | --- |
| `InteractionMode` | `idea_capture`、`quick_consult`、`department_task`、`formal_project`、`review_decision`、`override_recovery`、`escalation` |
| `ParticipationScope` | `executive_only`、`single_department`、`multi_department`、`full_project_chain` |
| `SyncBackPolicy` | `none`、`executive_summary_only`、`taskgraph_update`、`memory_and_taskgraph` |

默认原则：

- `formal_project` 才使用当前的默认正式项目流。
- 轻量流程不是绕过治理，而是减少参与范围和流程负担。
- 所有轻量流程都必须最终 `sync-back` 到 `Chief of Staff`，并留下最小 `MemoryRecord` 或 `RunTrace`。

### 分层职责

| 层 | 责任 | 本次升级点 |
| --- | --- | --- |
| `Human CEO Layer` | 定目标、做取舍、拍板 | 新增 |
| `Executive Office Layer` | 做归一、派单、同步、节奏管理 | 新增 |
| `Virtual Department Layer` | 定义部门 charter、席位和激活策略 | 新增 |
| `Orchestration Layer` | `GoalRequest -> TaskGraph -> ExecutionTask` | 保留 |
| `Workflow Recipe Layer` | 保存正式 operating recipe | 保留并改写成公司流程 |
| `OpenClaw Agent Plane` | 承接单 agent runtime、skills、tools、sessions、sandbox | 新增为正式能力层 |
| `Company Control Plane` | 承接公司级 workflow、工单、任务图、治理与可见协作 | 保留并上升为正式定义 |
| `Visible Communication Orchestration` | 承接 Feishu mention dispatch、visible room 与多 agent fan-out | 新增 |
| `Persona Asset Layer` | 管理上游角色与 seat mapping | 保留并升级 |
| `Memory Fabric & Artifact Layer` | 管理多作用域 memory、checkpoint、evidence 与 recall | 新增为正式子系统 |
| `Distribution Layer` | 多工具产物编译和分发 | 保留 |
| `Governance & Observability Layer` | 审批、证据、回放、审计 | 保留并改写语义 |

### 默认技术取舍

- 顶层叙事升级为 `one-person-company`，底层技术描述继续使用 `multi-agent-company`。
- `Chief of Staff` 是默认操作入口，不是装饰性角色。
- 用户仍可直达某个部门，但系统必须通过 `ExecutiveRoutingPolicy` 做补同步与回写。
- `agency-agents` 仅作为上游 `PersonaPack`、workflow pattern 和 distribution 参考，不作为 runtime 或 scheduler。
- `OpenClaw` 是正式 `Agent Plane`，不是简单的模型配置来源。
- `LangGraph` 继续只承接 company workflow orchestration，不再被表述为单 agent runtime。
- `Feishu` 在 V1 走项目内 `visible-room fan-out`，不直接等于 OpenClaw shared groups。
- memory 保持平台中立设计，但 V1 推荐采用 `Redis + Postgres + Vector DB + Object Store + Versioned Registry` 的组合。

### 公开库整合架构

当前默认主栈固定为：
[OpenClaw](https://docs.openclaw.ai/) + [LangGraph](https://github.com/langchain-ai/langgraph) + [agency-agents](https://github.com/msitarzewski/agency-agents) + 当前项目自定义 `Memory Fabric`

| 当前方案层 | 默认绑定 | 说明 |
| --- | --- | --- |
| `Human CEO Layer` | 当前项目自定义 | 不外包给公开库 |
| `Executive Office Layer` | 当前项目自定义 | `Chief of Staff` 仍是控制面概念 |
| `Virtual Department Layer` | 当前项目自定义 | 部门、席位和激活策略保持当前定义 |
| `OpenClaw Agent Plane` | `OpenClawProvisioningService -> OpenClawGatewayAdapter -> OpenClaw native agents` | 承接单 agent runtime、skills、tools、sessions、sandbox |
| `Orchestration Layer` | `LangGraphRuntimeAdapter -> LangGraph` | 只承接公司级 workflow graph、subgraph、checkpoint |
| `Workflow Recipe Layer` | 当前项目 recipe 定义 + `LangGraphRuntimeAdapter` | recipe 语义仍由当前方案定义 |
| `Persona Asset Layer` | `PersonaSourceAdapter -> agency-agents` | 上游角色先编译成 `PersonaPack` |
| `Employee Pack Layer` | `EmployeePackCompiler -> OpenClawWorkspaceCompiler` | 多 persona 组合成单席位 `VirtualEmployee`，再编成 `OpenClawWorkspaceBundle` |
| `Memory Fabric & Artifact Layer` | 当前项目治理层 + memory/tool bridge | 长期公司记忆、checkpoint、approval、evidence 仍由当前项目定义 |
| `Visible Communication Orchestration` | `FeishuMentionDispatch + VisibleRoomOrchestrator` | V1 Feishu 采用项目内 visible-room fan-out，而不是 OpenClaw shared groups |
| `Distribution Layer` | 当前项目定义，参考 `agency-agents` | 参考上游分发模式，不直接当运行时 |

默认边界：

- 产品语义层不外包给公开库。
- agent 原生能力层优先复用 `OpenClaw`。
- company workflow orchestration 优先复用 `LangGraph`。
- 治理、审批、promotion、checkpoint 仍由当前方案定义。

## 3. 公司组织模型

完整组织图定义在 [one-person-company-org-model.md](/Users/weisen/Documents/small-project/multi-agent-company/docs/one-person-company-org-model.md)。主方案只保留实现所需的核心摘要。

### 组织图

```text
CEO
  |
  +-- Executive Office
  |
  +-- Product
  +-- Research & Intelligence
  +-- Project Management
  +-- Design & UX
  +-- Engineering
  +-- Quality
  +-- Growth & Marketing
  +-- Sales & Partnerships
  +-- Customer Success & Support
  +-- Business Operations
  +-- Trust / Security / Legal
```

### V1 部门与席位

| 部门 | 默认席位 | 激活级别 | 核心职责 |
| --- | --- | --- | --- |
| Executive Office | `Chief of Staff` | always-on | intake、路由、节奏、综合汇报 |
| Product | `Product Lead` | always-on | 产品目标、优先级、版本判断 |
| Research & Intelligence | `Research Lead` | always-on | 趋势、竞品、用户与市场信号 |
| Project Management | `Delivery Lead` | always-on | 任务图、依赖、范围、推进 |
| Design & UX | `Design Lead` | always-on | 研究转设计、结构与体验 |
| Engineering | `Engineering Lead` | always-on | 架构、实现、技术交付 |
| Quality | `Quality Lead` | always-on | 证据采集、GO / NO-GO 判定 |
| Growth & Marketing | `Growth Lead` | on-demand | 上线、增长、品牌和分发 |
| Sales & Partnerships | `Partnerships Lead` | situational / expansion | BD、合作、外部渠道 |
| Customer Success & Support | `Customer Success Lead` | on-demand | 反馈、支持、留存、FAQ |
| Business Operations | `Operations Lead` | situational / expansion | 财务、流程、内部运营 |
| Trust / Security / Legal | `Trust & Compliance Lead` | situational / expansion | 合规、风险、身份与审计 |

### 组织设计约束

- V1 每个部门只有一个虚拟员工席位。
- 一个席位可以由多个上游 `PersonaPack` 组合实现。
- `Quality` 部门在 V1 采用“单席位、双模式”：
  `Evidence mode` 负责证据采集；
  `Verdict mode` 负责放行与驳回。
- `Executive Office` 是默认中枢，CEO 直达部门不等于绕过中枢。

## 4. V1 Operating Recipes

完整交互模型定义在 [ceo-agent-interaction-flows.md](/Users/weisen/Documents/small-project/multi-agent-company/docs/ceo-agent-interaction-flows.md)。本节保留 V1 需要直接依赖的摘要。

### 交互流程摘要

| mode | 适用场景 | 默认参与 | 默认输出 | 默认升级目标 |
| --- | --- | --- | --- | --- |
| `idea_capture` | 想法、灵感、方向、疑问 | `CEO + Chief of Staff` | `IdeaBrief` | `department_task` 或 `formal_project` |
| `quick_consult` | 问意见、要建议、做轻分析 | `CEO + 1 个部门` | `ConsultNote` | `department_task` 或 `review_decision` |
| `department_task` | 单部门小任务 | `CEO + 1 个部门` | `TaskResult` | `formal_project` 或 `escalation` |
| `formal_project` | 正式交付链路 | `Chief of Staff + 核心部门链` | deliverable + evidence + checkpoint | 不适用 |
| `review_decision` | review、拍板、复核 | `CEO + Chief of Staff + optional Quality/Product/Trust` | `DecisionRecord` | `override_recovery` 或 `formal_project` |
| `override_recovery` | 停掉、改向、回滚 | `CEO + Chief of Staff + 相关部门` | `OverrideDecision` | `formal_project` 或 `escalation` |
| `escalation` | 风险、冲突、连续失败 | `Chief of Staff + 相关部门 + optional CEO` | `EscalationSummary` | 回到任一合适主流程 |

### Recipe A：CEO Strategy Loop

```text
CEOCommand
  -> Chief of Staff
  -> Product Lead + Research Lead
  -> strategic options
  -> CEO decision
  -> company checkpoint
```

默认规则：

- 处理方向、优先级、资源取舍、阶段目标与月度 checkpoint。
- 产出必须区分 `事实 / 推断 / 决策 / 待确认`。
- 所有战略决策进入 `CEO intent memory`。

### Recipe B：Product Build Loop

```text
CEO / Product request
  -> Chief of Staff
  -> Product Lead
  -> Delivery Lead
  -> Design Lead
  -> Engineering Lead
  -> Quality Lead
  -> Executive synthesis
  -> CEO review
```

默认规则：

- `Product -> PM -> Design -> Engineering -> Quality` 是默认研发链路。
- `Quality Lead` 先走 `Evidence mode`，再走 `Verdict mode`。
- 默认最多 3 次 retry；超过阈值进入 `Chief of Staff + CEO` 决策。
- 交付物必须带 `EvidenceArtifact`、`HandoffTag` 和 `Checkpoint`。

### Recipe C：Launch / Growth Loop

```text
Product milestone ready
  -> Growth Lead
  -> Customer Success Lead
  -> optional Partnerships Lead
  -> Executive Office synthesis
  -> CEO approval
```

默认规则：

- 不常驻参与所有研发流程，只在上线、推广、用户反馈阶段按需激活。
- 输出包括消息、渠道、支持材料、反馈闭环与必要的销售/合作动作。
- 所有对外材料默认经过 `Trust & Compliance Lead` 的按需校验。

### Recipe D：Discovery / Synthesis Loop

```text
CEOCommand
  -> Chief of Staff
  -> Research / Product / Design / optional Growth (parallel)
  -> Cross-Agent Synthesis
  -> CEO review
```

默认规则：

- 支持并行产出，但必须经过单独的综合阶段。
- 综合结果必须显式标注结论来源，避免把不同部门观点混成单一答案。
- 当任务涉及市场、产品、设计和执行的多维判断时，优先使用该 recipe。

### CEO 直达部门规则

- 允许 CEO 直接对某个部门发指令。
- 直接指令仍必须通过 `ExecutiveRoutingPolicy` 回写：
  `Chief of Staff`
  `MemoryRecord`
  `TaskGraph`
- CEO 可使用三种 delegation mode：
  `default`
  `direct`
  `override`

### V1 技术落地映射

V1 的正式技术落地不再是“当前项目直接调用模型”，而是三层协同：

- `agency-agents` 提供上游 persona / workflow asset。
- `OpenClaw` 提供单 agent 原生 runtime。
- `LangGraph` 提供公司级 workflow orchestration。

| Recipe | 上游角色来源 | agent 执行承载 | company workflow 承载 | communication 承载 | 当前状态 |
| --- | --- | --- | --- | --- | --- |
| `Product Build Loop` | `agency-agents` 的 Product / PM / Design / Engineering / Quality 角色资产 | `OpenClaw native agents` | `LangGraphRuntimeAdapter -> LangGraph` | Dashboard + Feishu visible-room fan-out | V1 主线 |
| `Discovery / Synthesis Loop` | `agency-agents` 的 Research / Product / Design 角色资产 | `OpenClaw native agents` | `LangGraphRuntimeAdapter -> LangGraph` | Dashboard + Feishu visible-room fan-out | V1 主线 |

其余 recipe 的当前处理方式：

- `CEO Strategy Loop`：
  V1 先保留为 company control plane 流程，重点写清 route、checkpoint、strategic memory 与 visible trace。
- `Launch / Growth Loop`：
  延后到 `V1.5`，当前只保留组织和流程定义，不进入第一批技术承接范围。

### Goal Lineage、Budget、Trigger 与 WorkTicket

当前方案吸收 [Paperclip README](https://github.com/paperclipai/paperclip/blob/master/README.md) 中已被公开验证的 control-plane 能力，但保持 `human CEO + Chief of Staff + Memory Fabric` 的主叙事不变。

- `Goal Lineage`：
  每个正式任务都必须可追溯到：
  `CEO 战略 -> 公司目标 -> 项目目标 -> 任务目标 -> ExecutionTask`
- `Budget Governance`：
  V1 正式引入：
  `company budget`
  `department budget`
  `employee budget`
  `task budget`
- `Trigger Model`：
  V1 的触发源固定为：
  `manual CEO trigger`
  `event trigger`
  `scheduled heartbeat`
- `WorkTicket`：
  作为 `TaskGraph + ConversationThread + RunTrace + artifacts` 之外的统一工作项，承接正式项目、轻量任务、review 和 escalation。

默认约束：

- 轻量流程可以只建立最小 `WorkTicket`，不强制完整 `TaskGraph`。
- 正式项目必须同时拥有：
  `WorkTicket`
  `TaskGraph`
  `RunTrace`
  `Checkpoint`
- 高影响预算 override 必须进入 `ApprovalGate`。
- `scheduled heartbeat` 只能触发预定义 recurring work，不得绕过 `Executive Office`。

## 5. 公共接口 / 类型

### 新增公司层接口

| 接口 | 核心字段 | 说明 |
| --- | --- | --- |
| `CompanyProfile` | `company_name`、`company_type`、`stage`、`strategic_focus`、`default_departments`、`activation_policy`、`budget_policy`、`trigger_defaults` | 定义这家一人公司的经营形态 |
| `CEOCommand` | `intent`、`priority`、`time_horizon`、`delegation_mode`、`expected_outcome`、`interaction_mode`、`activation_hint` | CEO 发出的原始经营指令 |
| `VirtualDepartment` | `department_name`、`charter`、`activation_level`、`default_employee`、`upstream_sources`、`budget_scope`、`heartbeat_policy` | 部门而不是单一 runtime role |
| `VirtualEmployee` | `employee_id`、`department`、`employee_name`、`source_persona_packs`、`operating_modes`、`kpis`、`budget_scope`、`heartbeat_policy` | V1 的部门席位实体 |
| `ExecutiveRoutingPolicy` | `default_route`、`direct_access_rules`、`escalation_rules`、`sync_back_rules` | 定义 CEO 直达部门后的同步规则 |
| `CompanyCadence` | `daily_sync`、`weekly_review`、`monthly_checkpoint`、`strategy_refresh` | 定义公司级经营节奏 |
| `GoalLineage` | `company_goal`、`initiative`、`project_goal`、`task_goal`、`execution_ref` | 目标血缘链 |
| `BudgetPolicy` | `scope`、`limit`、`warning_threshold`、`hard_stop`、`override_rule` | 公司级预算与成本治理规则 |
| `TriggerPolicy` | `trigger_type`、`schedule`、`event_source`、`routing_rule` | 手动、事件、heartbeat 统一触发策略 |
| `WorkTicket` | `ticket_id`、`title`、`ticket_type`、`thread_ref`、`taskgraph_ref`、`runtrace_ref`、`artifacts`、`status` | 统一正式工作项 |
| `InteractionMode` | `idea_capture`、`quick_consult`、`department_task`、`formal_project`、`review_decision`、`override_recovery`、`escalation` | CEO 与虚拟员工交互模式枚举 |
| `ParticipationScope` | `executive_only`、`single_department`、`multi_department`、`full_project_chain` | 任务参与粒度枚举 |
| `SyncBackPolicy` | `none`、`executive_summary_only`、`taskgraph_update`、`memory_and_taskgraph` | 交互完成后的回写策略 |
| `DepartmentSeatMap` | `department`、`employee`、`source_persona_packs`、`recipe_eligibility`、`private_namespace`、`department_namespace`、`company_access_profile` | 上游 PersonaPack 到席位与 memory namespace 的映射 |
| `MemoryScope` | `run`、`agent_private`、`department_shared`、`company_shared` | memory 作用域枚举 |
| `MemoryKind` | `working`、`episodic`、`semantic`、`procedural`、`evidence` | memory 类型枚举 |
| `MemoryNamespace` | `namespace_id`、`scope`、`owner`、`read_policy`、`write_policy`、`promotion_policy` | 每个作用域的正式命名空间 |
| `RecallQuery` | `scope_filter`、`kind_filter`、`tags`、`project`、`department`、`receiver`、`time_window`、`min_confidence` | recall / search 的统一查询对象 |
| `LearningCandidate` | `source_run`、`agent_id`、`candidate_type`、`proposed_scope`、`evidence_refs`、`confidence`、`expected_reuse` | 从运行中提炼出的学习候选 |
| `EvolutionReview` | `candidate_id`、`reviewer`、`decision`、`reason`、`target_scope`、`version_action` | 共享 memory 升级审批记录 |
| `IdeaBrief` | `idea`、`why_now`、`possible_departments`、`next_step_hint` | 想法记录产物 |
| `ConsultNote` | `question`、`analysis`、`recommendations`、`follow_up` | 快速咨询产物 |
| `TaskResult` | `task`、`result`、`artifacts`、`handoff_needed` | 单部门任务结果 |
| `DecisionRecord` | `subject`、`evidence_refs`、`decision`、`reason`、`next_action` | review / 拍板记录 |
| `OverrideDecision` | `target`、`new_direction`、`rollback_ref`、`supersede_refs` | 改向与恢复记录 |
| `EscalationSummary` | `issue`、`conflicts`、`risk_level`、`options`、`decision_needed` | 升级处理摘要 |

### 保留并重命名语义的引擎接口

| 接口 | 核心字段 | 新语义 |
| --- | --- | --- |
| `GoalRequest` | `goal`、`constraints`、`deliverables`、`risk_level`、`approval_policy`、`interaction_mode`、`participation_scope`、`goal_lineage_ref` | 从 `CEOCommand` 归一后的执行目标 |
| `TaskGraph` | `graph_id`、`nodes`、`edges`、`status`、`artifacts`、`active_recipe`、`goal_lineage_ref`、`work_ticket_ref` | 公司任务运行的唯一真相源 |
| `WorkflowRecipe` | `name`、`stages`、`handoff_mode`、`quality_gates`、`retry_policy`、`entry_mode` | 公司 operating recipe |
| `AgentProfile` | `role`、`capabilities`、`allowed_tools`、`escalation_rules` | 由 `VirtualEmployee + PersonaPack` 生成 |
| `ExecutionTask` | `task_id`、`agent_profile`、`input_context`、`tool_budget`、`deadline`、`goal_lineage_ref`、`work_ticket_ref` | 编排层给执行层的任务单元 |
| `MemoryRecord` | `scope`、`scope_id`、`owner_id`、`kind`、`visibility`、`content`、`confidence`、`promotion_state`、`version`、`checkpoint_ref`、`artifact_refs`、`retention`、`source_trace` | 统一表达多作用域、多类型的 company memory |
| `ToolContract` | `tool_name`、`risk_tier`、`sandbox_policy`、`failure_mode` | 工具治理契约 |
| `RunTrace` | `run_id`、`interaction_mode`、`task_events`、`tool_calls`、`approvals`、`artifacts`、`metrics`、`goal_lineage_ref`、`work_ticket_ref` | 经营过程的可观测轨迹 |
| `EvidenceArtifact` | `source`、`kind`、`spec_quote`、`observation`、`verdict` | 质量与审批证据 |
| `Checkpoint` | `checkpoint_id`、`graph_id`、`stage`、`artifacts`、`memory_snapshot_refs`、`promotion_state_refs`、`rollback_scope`、`rollback_to` | memory-aware 公司级阶段快照 |
| `PersonaPack` | `division`、`role`、`mission`、`rules`、`workflow`、`deliverables`、`success_metrics` | 上游角色资产 |
| `RoleActivationPolicy` | `always_on`、`on_demand`、`situational_expansion` | 公司级部门激活策略 |

### 关键接口关系

```text
CEOCommand
  -> GoalRequest

GoalLineage
  -> GoalRequest / TaskGraph / ExecutionTask / RunTrace

VirtualEmployee + PersonaPack(s)
  -> AgentProfile

BudgetPolicy + TriggerPolicy
  -> CompanyProfile / VirtualDepartment / VirtualEmployee

Department activation + task type
  -> WorkflowRecipe

Company operations
  -> WorkTicket + TaskGraph + RunTrace + Checkpoint

RecallQuery
  -> Memory Fabric

LearningCandidate
  -> EvolutionReview
  -> promoted MemoryRecord if approved
```

### 新增内部适配对象

| 对象 | 责任 | 边界 |
| --- | --- | --- |
| `PersonaSourceAdapter` | 将 `agency-agents` 上游资产转换为 `PersonaPack` | 不直接参与运行时调度 |
| `EmployeePackCompiler` | 将多个 `PersonaPack` 编译为单席位 `VirtualEmployee` 与 `EmployeePack` | 不改变部门外部接口 |
| `OpenClawWorkspaceCompiler` | 将 `EmployeePack` 编译为 `OpenClawWorkspaceBundle` | 不替代部门、席位和公司语义 |
| `OpenClawProvisioningService` | 生成 `OpenClawAgentBinding`、workspace、agentDir、channel account 配置 | 不定义公司级 workflow |
| `OpenClawGatewayAdapter` | 调用 OpenClaw 原生 agent runtime、skills、tools、sessions | 不替代 WorkTicket / TaskGraph / RunTrace |
| `OpenClawSessionBinding` | 将 `ConversationThread` / channel session 绑定到 OpenClaw sessionKey | 不改变表面级 thread 语义 |
| `LangGraphRuntimeAdapter` | 将 `WorkflowRecipe`、`TaskGraph` 编译到 `LangGraph` | 只负责 company workflow orchestration |
| `FeishuMentionDispatch` | 将 Feishu 私聊、单提及、多提及映射到目标 agent 集合 | 不直接生成 agent 回复 |
| `VisibleRoomOrchestrator` | 管理 visible-room fan-out、公开轮次发言与 transcript 镜像 | 不允许隐藏 agent 私聊作为默认路径 |
| `Mem0Bridge` | 作为可选整合边界统一 `remember / recall / search` 与 metadata 映射 | 不定义 promotion / approval 规则，也不是 V1 默认必选依赖 |
| `CheckpointStore` | 持久化 `TaskGraph snapshot + memory refs + verdict` | 不替代 recall/search |
| `MemoryGovernanceService` | 管理 promotion、approval、supersede、rollback | 不依赖单一公开库语义 |
| `GoalLineageService` | 维护目标血缘链与引用完整性 | 不直接决定流程路线 |
| `BudgetPolicyService` | 管理预算阈值、告警、硬停和 override | 不取代工具级预算保护 |
| `TriggerScheduler` | 管理 heartbeat 与 event trigger 调度 | 不绕过 Executive Office |
| `WorkTicketService` | 统一工单、线程、运行和交付状态 | 不取代 TaskGraph 的执行语义 |

### 组合席位约束

- V1 默认支持 `composite employee pack`。
- 单席位组合不能改变该部门的外部接口，只能改变该席位内部使用的 `PersonaPack`。
- V2 如果拆分成多员工部门，必须保持 `DepartmentSeatMap` 与 `WorkflowRecipe` 外部兼容。

## 6. Memory Fabric 与 Tool 治理

完整设计定义在 [memory-fabric-design.md](/Users/weisen/Documents/small-project/multi-agent-company/docs/memory-fabric-design.md)。本节只保留主方案需要直接依赖的摘要、接口边界和默认策略。

### Memory Fabric 总图

```text
Human CEO Layer
  -> company_shared strategic memory

Executive Office Layer
  -> memory routing / distillation / promotion / approval

Virtual Department Layer
  -> department_shared namespaces

Orchestration Layer
  -> session recall / handoff persist / checkpoint / rollback

Memory Fabric
  -> run memory
  -> agent_private memory
  -> department_shared memory
  -> company_shared memory
  -> evidence + checkpoint + indexing

Governance & Observability Layer
  -> mutation audit / approval log / promotion review / replay
```

### Scope x Kind 双维模型

| scope | working | episodic | semantic | procedural | evidence |
| --- | --- | --- | --- | --- | --- |
| `run` | 当前任务上下文、scratchpad | 当前 run 的阶段事件 | 本轮临时检索摘要 | 当前 recipe 的执行步骤 | 当前 run 的测试与观察 |
| `agent_private` | 当前席位个人上下文 | 个人执行历史、失败经验 | 个人检索偏好、主题索引 | 个人 heuristics、工具偏好 | 个人审阅记录 |
| `department_shared` | 部门当前工作面板 | 部门复盘、handoff 历史 | 部门知识库、术语、FAQ | SOP、checklist、handoff 模板 | 部门级质量案例 |
| `company_shared` | 当前公司级重点事项 | 月度 checkpoint、战略事件 | 产品事实、客户画像、政策知识 | 跨部门 recipe、policy、playbook | board-style evidence package |

### 默认规则

- `run` 作用域服务当前 session 和当前 `TaskGraph`，生命周期最短。
- `agent_private` 允许自动写入，但必须带版本、置信度和 retention。
- `department_shared` 是正式 namespace，即使 V1 每部门只有一个席位也必须存在。
- `company_shared` 由 Executive Office 管理，高影响项默认需要 CEO 或等价审批。
- recall 默认按 `scope_filter + tags + project + stage + receiver` 组合查询，不能直接全库裸搜。
- `heartbeat summary` 默认进入 `episodic`，而不是直接写 company-level procedural memory。
- 审计日志与长期记忆严格区分：
  审计用于追踪动作；
  长期 memory 用于后续 recall。

### Memory lifecycle

```text
capture
  -> summarize
  -> classify(scope + kind)
  -> route
  -> approve if needed
  -> persist
  -> index
  -> recall / rollback when needed
```

### Distillation 与 self-improving 默认机制

- 长上下文、长 traces、长对话不直接写入长期记忆，先进入 `memory distillation`。
- `LearningCandidate` 是 agent 从一次 run 中提炼出的“可复用经验”，不是自动生效的制度变更。
- 三级进化固定为：
  `L1 private auto-learning`
  `L2 department promotion`
  `L3 company promotion`
- 默认审批链固定为：
  `agent_private` 自动写入；
  `department_shared` 由部门席位或 `Chief of Staff` 审批；
  `company_shared` 由 `Chief of Staff` 审批，高影响项再交 CEO。

### 推荐 V1 存储映射

| memory type | 推荐实现 |
| --- | --- |
| `working / run` | Redis 或等价缓存 |
| `episodic / checkpoint / metadata` | Postgres |
| `semantic retrieval` | Vector DB |
| `procedural` | versioned registry 或 Git-backed 文档资产 |
| `evidence` | object storage + metadata index |

### Tool 治理默认值

- `Executive Office` 默认拥有读、写、规划、汇总类工具，不默认拥有高风险执行工具。
- `Engineering Lead` 可使用代码、文件、测试、构建类工具，但高风险写操作仍需策略层约束。
- `Quality Lead` 默认拥有读取、验证、测试、证据采集工具，不默认拥有产品写入权限。
- `Trust & Compliance Lead` 在高风险 run 中拥有审批前置校验权限。
- Distribution Layer 的导出动作不混入普通 workflow tool set。
- 预算治理与工具治理同时存在：
  `tool_budget` 约束单次执行，
  `BudgetPolicy` 约束公司、部门、席位与任务层面的累计成本。

## 7. 安全与可观测性

### 安全默认值

- 所有最终放行结论都必须附带 `EvidenceArtifact`。
- 高风险 run 默认需要 `executive approval`，并留下审批理由。
- `Trust / Security / Legal` 是正式部门，不是附录注释；只是默认按需激活。
- `Agentic Identity & Trust Architect` 与 `Identity Graph Operator` 继续作为 roadmap 中的 specialized governance 来源。

### 可观测性默认值

- 每个 `TaskGraph` 节点必须记录：
  所属部门
  所属席位
  recipe
  证据数量
  重试次数
  当前 verdict
- `RunTrace` 必须能回答：
  为什么激活了这个部门；
  为什么某个席位被允许直达执行；
  为什么进入 retry 或 rollback；
  为什么 CEO 最终批准或驳回。
- V1 还需额外回答：
  这个 run 属于哪个 `WorkTicket`；
  它追溯到哪个 `GoalLineage`；
  是否由 `manual / event / scheduled_heartbeat` 触发。

### 关键指标

- 经营层：
  目标完成率、CEO 介入率、部门激活频次、月度 checkpoint 完成率。
- 交付层：
  交付成功率、平均耗时、重试率、rollback 率、GO / NO-GO 比例。
- 质量层：
  evidence pass rate、quality reject rate、post-launch issue rate。

## 8. 阶段路线图

### Phase 0：文档与命名升级

- 将主叙事升级为 `one-person-company`。
- 新增组织模型附录。
- 固定 12 部门、席位、cadence 和 CEO 路由规则。
- 明确 `OpenClaw = agent plane`、`当前项目 = company control plane`。

### Phase 1：Executive Office 与核心部门落地

- 落地 `Chief of Staff` 路由模型。
- 激活 always-on 部门：
  Executive Office、Product、Research & Intelligence、Project Management、Design & UX、Engineering、Quality。
- 固定 `CEO Strategy Loop` 与 `Product Build Loop`。
- 完成 `OpenClaw native agent provisioning` 与 `EmployeePack -> OpenClawWorkspaceBundle` 编译路径。

### Phase 2：Memory Fabric、质量与 checkpoint 稳定化

- 增加独立 `Memory Fabric` 文档与正式接口。
- 固化 `run / agent_private / department_shared / company_shared` 四层作用域。
- 把 `LearningCandidate`、`EvolutionReview`、`memory-aware checkpoint` 接入默认流程。
- 固化 `Quality Lead` 的双模式。
- 把 `EvidenceArtifact`、`Checkpoint`、`rollback` 与 `executive approval` 接入默认流程。
- 明确 CEO 直达部门后的同步回写。

### Phase 3：on-demand 部门扩展

- 按场景启用 `Growth & Marketing`、`Customer Success & Support`。
- 正式使用 `Launch / Growth Loop`。
- 将反馈回流到 Product 与 Executive Office。
- 完成 Feishu `visible-room fan-out`、单提及 / 多提及、可见 agent-to-agent exchange。

### Phase 4：situational 部门与高阶治理

- 逐步接入 `Sales & Partnerships`、`Business Operations`、`Trust / Security / Legal`。
- 完善 `Distribution Layer` 与 `composite employee pack` 的自动编译能力。
- 评估 Specialized Governance 的实现路线。
- 预留 `company template / org template / employee pack bundle` 与 `portfolio / multi-company isolation` 的长期路线。

### 与公开库绑定的版本路线

| 版本 | 默认主栈 | 目标 | 公开库边界 |
| --- | --- | --- | --- |
| `V1` | `OpenClaw + LangGraph + agency-agents + current Memory Fabric + Feishu visible orchestration` | 跑通 `Product Build Loop` 与 `Discovery / Synthesis Loop`，并用 Feishu 满足 CEO 可见沟通目标 | `OpenClaw` 承接 agent plane，`LangGraph` 承接 company workflow，`agency-agents` 提供 seat pack 来源，Feishu 走 visible-room fan-out |
| `V1.5` | `OpenClaw + LangGraph + agency-agents + current Memory Fabric + Feishu visible orchestration` | 把 `Launch / Growth Loop` 纳入正式承接范围，补强 Feishu room policy 与 transcript 观察能力 | 仍不引入第二沟通平台 |
| `V2` | `OpenClaw + LangGraph + agency-agents + current Memory Fabric + Slack` | 扩展 on-demand 部门、开放 `L2 department promotion`、引入 Slack 作为第二沟通平台 | `Slack` 复用同一 company plane 契约，Feishu 保留为 V1 主表面 |
| `V3` | 主栈保持不变，评估替代路线 | 评估更强 DevUI / workforce / 产品壳层 | `Microsoft Agent Framework`、`CAMEL`、`full-stack-ai-agent-template` 只进入 future path |

## 9. 风险与决策记录

### 已做默认决策

- `one-person-company` 是产品与组织叙事，`multi-agent-company` 是底层引擎名。
- 公司原型固定为 `AI 产品工作室`。
- 默认操作模式固定为 `CEO + Chief of Staff` 混合。
- V1 每部门一席位，但允许 `composite employee pack`。
- 12 个部门全部进入文档主干，但只按激活策略参与运行。
- Quality 在 V1 采用“单席位、双模式”。

### 主要风险

- 如果只换名字、不改 operating model，文档会继续停留在系统视角而不是 CEO 视角。
- 如果 `Chief of Staff` 不是默认入口，CEO 与部门的直接沟通会导致记忆与任务图断裂。
- 如果“每部门一个员工”被误解成“一角色一 persona”，V1 会很快卡死在角色能力不足上。
- 如果把所有部门都设成 always-on，系统会在 V1 过度复杂化。
- 如果不保留 `multi-agent-company` 作为底层引擎名，产品叙事和技术架构会再次混层。
- 如果没有正式的 `department_shared` namespace，V2 从单席位扩展到多席位时会被迫重构 memory 模型。
- 如果让 agent 自动写入公司级 procedural memory，自我进化会退化成不可控的制度漂移。
- 如果没有 `GoalLineage`，正式任务会退化成孤立执行，无法形成真正的 company control plane。
- 如果没有 `BudgetPolicy`，V1 很难形成公司级成本治理闭环。
- 如果没有 `TriggerPolicy`，recurring work 只能靠 CEO 手动推进，无法形成稳定经营节奏。
- 如果没有 `WorkTicket`，thread、run、artifact 和决策会继续散落在不同对象上。

### 延后决策

- 是否在实现层立即引入真正的 `CompanyProfile` 配置文件。
- 是否把 `Research & Intelligence` 拆成单独 division 还是继续复用 Product 角色资产。
- `CompanyTemplate` 何时进入正式产品化路线。
- `Portfolio / Multi-Company Isolation` 何时从长期方向进入实现优先级。
- `Sales & Partnerships`、`Business Operations`、`Trust / Security / Legal` 在第一轮实现中是文档存在还是运行时可选。
- V2 何时把 `Quality Lead` 从单席位拆成双员工结构。
