# V1 具体实现开发方案

本文是当前开发方案的 kickoff 主文档，负责回答 V1 做什么、先做什么、哪些不做、各模块按什么顺序交付，以及如何判断 V1 已经达到可交付状态。

## 1. V1 目标

### 1.1 业务目标

- 让用户以 `CEO` 身份与一组部门化虚拟员工稳定交互。
- 跑通“想法记录、快速咨询、单部门任务、正式项目”四类核心流程。
- 让每次交互都能留下最小可追踪的 `RunTrace`、memory 写入和必要 artifact。
- 在不引入完整产品壳的前提下，先做一个内部可操作的虚拟公司控制面。

### 1.2 技术目标

- 固定开发环境为本机 Docker 容器栈，避免 Host 环境漂移影响实现和调试。
- 用 `OpenClaw` 承接单 agent 的原生 runtime、skills、tools、sessions、sandbox 与 provider/model routing。
- 用 `LangGraph` 承接 company workflow orchestration，而不是直接承担单 agent 对话执行。
- 用 `agency-agents` 作为上游 `PersonaPack` 资产来源，并编译成 `OpenClawWorkspaceBundle`。
- 用单体后端把 `Executive Office`、部门席位、memory、checkpoint、quality 和 visible communication orchestration 串起来。
- 把 V1 收敛为最小可用 `company control plane`，正式引入：
  `Goal Lineage`
  `Budget Governance`
  `Trigger Model`
  `WorkTicket`
- 同时把 `OpenClaw native agent provisioning`
  `Feishu mention dispatch`
  `visible-room fan-out`
  `OpenClaw session binding`
  纳入 V1 主线。

### 1.3 成功标准

- CEO 能发出一条自然语言指令，系统能识别 `InteractionMode` 并进入正确流程。
- 轻量流程不拉全员，但都能 `sync-back` 到 `Chief of Staff`。
- 正式项目能走完：
  `Product -> Project Management -> Design -> Engineering -> Quality`
- 至少 7 个核心部门的席位模型和 memory scope 都能稳定工作。
- 所有正式结论都能找到对应的 trace、artifact 和 checkpoint 引用。
- 所有正式任务都能显示 `GoalLineage`
- 至少具备最小可用的预算阈值、heartbeat / event trigger、`WorkTicket` 视图

## 2. V1 范围

### 2.1 默认主栈

- `OpenClaw`：
  承接单 agent runtime、skills、tools、sessions、sandbox 与 provider/model routing。
- `LangGraph`：
  承接 `TaskGraph`、graph/subgraph、状态流转与 company workflow orchestration。
- `agency-agents`：
  承接 division、role、workflow、quality gate pattern 的上游角色资产。
- 当前 `Memory Fabric`：
  承接长期公司记忆、checkpoint refs、approval、promotion、supersede 与 evidence 治理。

### 2.2 核心 7 部门

| 部门 | V1 席位 | 核心作用 |
| --- | --- | --- |
| Executive Office | `Chief of Staff` | intake、路由、同步、综合 |
| Product | `Product Lead` | 产品方向、优先级、取舍 |
| Research & Intelligence | `Research Lead` | 外部信号、事实收集、趋势分析 |
| Project Management | `Delivery Lead` | 任务图、依赖、推进 |
| Design & UX | `Design Lead` | 结构、体验、信息设计 |
| Engineering | `Engineering Lead` | 架构、实现、技术交付 |
| Quality | `Quality Lead` | 证据与 verdict |

### 2.3 V1 重点交互模式

| mode | V1 状态 | 说明 |
| --- | --- | --- |
| `idea_capture` | 必做 | 轻量记录和后续升级入口 |
| `quick_consult` | 必做 | CEO 与单部门快速咨询 |
| `department_task` | 必做 | 单部门小任务 |
| `formal_project` | 必做 | 默认正式项目流 |
| `review_decision` | 最小支持 | 允许 CEO 基于现有证据拍板 |
| `override_recovery` | 最小支持 | 支持停掉、改向、回滚 |
| `escalation` | 最小支持 | 处理冲突和高风险情况 |

### 2.4 V1 必做流程

- `Idea Capture Loop`
- `Quick Consult Loop`
- `Department Task Loop`
- `Product Build Loop`
- `Discovery / Synthesis Loop`
- `scheduled_heartbeat` 与 `event trigger` 的最小可用控制流

### 2.5 V1 不做内容

- 不做正式面向终端用户的前台产品。
- 不做复杂权限系统和多租户。
- 不做全部 12 部门的常驻参与。
- 不做 `Launch / Growth Loop` 的完整实现。
- 不做 `L2/L3` 自我进化的自动化闭环。
- 不做 `Quality` 双席位拆分。
- 不做完整 agent 自治经营。

## 3. 系统形态

### 3.1 部署形态

- 单仓、单体后端。
- 单个内部控制台，服务于 CEO / operator。
- 单公司、单 CEO、单默认工作区。

### 3.2 开发环境约束

- 所有开发活动都在本机 Docker 容器中进行。
- 默认采用：
  `1 个主开发容器 + 若干依赖服务容器`
- 主开发容器负责：
  代码执行
  依赖安装
  测试与调试
  本地运行命令
- 依赖服务容器负责：
  `Postgres`
  `Redis`
  `Vector DB`
  `Object Store`
  以及其他 V1 必需基础设施。
- Host 只承担：
  `Docker Engine / Docker Desktop`
  `IDE / terminal`
  不作为 Python、Node、数据库或缓存的执行环境。

### 3.3 主要入口

- `Web Dashboard`
  作为 V1 的主前端表面，承接 CEO 输入、run 查看、artifact、memory、checkpoint 和管理动作。
- `Feishu`
  作为协作与会话表面，承接部门机器人私聊、项目群聊和轻量通知。
- `Internal API`
  供控制台和未来外部调用方使用。

详细的前端与飞书交互设计见 [frontend-and-feishu-interaction-design.md](/Users/weisen/Documents/small-project/multi-agent-company/docs/development-plan/frontend-and-feishu-interaction-design.md)。V1 固定采用：
`Web 优先`
`Dashboard = 内部控制台`
`Feishu = 按部门独立机器人`
`V1 群聊 = mention-based fan-out + visible-room orchestration`

### 3.4 V1 默认控制面

```text
CEOCommand
  -> Chief of Staff intake
  -> Interaction Router
  -> Department activation
  -> Workflow recipe
  -> TaskGraph / run execution
  -> Quality / synthesis
  -> CEO review
```

## 4. 核心子系统与交付顺序

### 4.1 Executive Office Core

职责：

- `CEOCommand -> GoalRequest` 归一化
- 指令分类和路由
- `InteractionMode` 识别
- `GoalLineage` 绑定
- 部门激活
- `sync-back`
- executive synthesis

优先级：
`P0`

### 4.2 Interaction Router

职责：

- 推断或接收显式 `interaction_mode`
- 映射 `ParticipationScope`
- 为每条指令选择默认流程与升级路径
- 区分 `manual / event_based / scheduled_heartbeat` 三类触发源

优先级：
`P0`

### 4.3 Department Runtime

职责：

- 管理 `VirtualDepartment`
- 管理 `VirtualEmployee`
- 将席位与上游 `PersonaPack` 绑定
- 为每个席位注入默认 memory profile
- 为每个席位生成 `OpenClawAgentBinding`
- 为每个席位绑定 tool / sandbox / channel accounts

优先级：
`P0`

### 4.4 OpenClaw Agent Provisioning

职责：

- 生成 `OpenClawWorkspaceBundle`
- 生成 `openclaw_agent_id`
- 绑定 workspace、agentDir、tool / sandbox profile
- 把 `EmployeePack` 编译成 `OpenClaw` 原生 agent bootstrap

优先级：
`P0`

### 4.5 OpenClaw Gateway Adapter

职责：

- 从 Dashboard / Feishu / workflow 节点调用真实 OpenClaw agent
- 维护 `OpenClawSessionBinding`
- 将单 agent 执行结果回写到 `ConversationThread / WorkTicket / RunTrace`

优先级：
`P0`

### 4.6 LangGraph Runtime Adapter

职责：

- 将 `WorkflowRecipe` 编译成 graph/subgraph
- 将 `TaskGraph` 映射为 runtime state
- 在关键节点挂接 checkpoint、quality 和 synthesis
- 在正式流程中挂接 `GoalLineage`、`WorkTicket` 和 trigger metadata
- 调度哪个席位应该进入 OpenClaw agent execution

优先级：
`P0`

### 4.7 Memory Fabric

职责：

- 管理 `run / agent_private / department_shared / company_shared`
- 管理 `working / episodic / semantic / procedural / evidence`
- 处理 recall、写入、promotion 边界和最小审计
- 处理 `heartbeat summary`、`WorkTicket refs` 与长期记忆的挂接

优先级：
`P0`

### 4.8 Quality Gate

职责：

- 以 `Quality Lead` 单席位形式承载：
  `Evidence mode`
  `Verdict mode`
- 为正式项目和高风险任务产出 `EvidenceArtifact` 与 `DecisionRecord`

优先级：
`P0`

### 4.9 Conversation Surfaces

职责：

- 承接 `Web Dashboard` 与 `Feishu` 两种交互表面
- 管理 `ConversationThread`
- 管理 `ChannelBinding`
- 管理 `RoomPolicy`
- 管理 `FeishuMentionDispatch`
- 管理 `VisibleRoomOrchestrator`
- 保证不同表面的输入都映射到同一套 `Executive Office / TaskGraph / RunTrace`
- 保证 Feishu 群聊满足单提及 / 多提及 / visible agent-to-agent 语义

优先级：
`P1`

### 4.10 Approval & Audit

职责：

- 承接高影响 review / approval / rollback / promotion
- 承接预算 override 与高影响 heartbeat 派生任务
- 让 `DecisionRecord`、高风险动作和质量 verdict 具备可审计轨迹
- 为 Dashboard 提供审批与审计查询能力

优先级：
`P1`

### 4.11 Operator Console

职责：

- CEO 输入
- run 列表
- `WorkTicket` 视图
- 当前交互模式展示
- TaskGraph 状态查看
- artifact、memory 摘要、checkpoint 查看
- review / approve / rollback / override 操作

优先级：
`P1`

## 5. V1 模块交付顺序

### Phase 1：基础骨架

- `Docker` 本地开发基线
- `company_profile_service`
- `ceo_command_service`
- `interaction_mode_classifier`
- `executive_routing_service`
- `department_activation_service`
- `workflow_recipe_registry`
- `goal_lineage_service`
- `work_ticket_service`

交付结果：
先固定 `主开发容器 + 依赖服务容器` 的开发环境，再跑通从 CEO 输入到流程选择的控制面。

### Phase 2：席位与运行时

- `persona_source_adapter_agency_agents`
- `employee_pack_compiler`
- `openclaw_workspace_compiler`
- `openclaw_provisioning_service`
- `openclaw_gateway_adapter`
- `openclaw_session_binding`
- `department_runtime_service`
- `langgraph_runtime_adapter`
- `taskgraph_service`

交付结果：
先让部门和席位被编译成真实 OpenClaw agent，再让公司流程进入 LangGraph 图运行。

### Phase 3：memory 与治理

- `memory_namespace_service`
- `memory_bridge_service`
- `artifact_store`
- `checkpoint_store`
- `memory_governance_service`
- `runtrace_service`
- `approval_service`
- `budget_policy_service`
- `trigger_scheduler`

交付结果：
让每条流程都留下稳定的 memory、trace 和 checkpoint。

### Phase 4：质量、表面与控制台

- `quality_service`
- `conversation_thread_service`
- `channel_binding_service`
- `feishu_mention_dispatch`
- `visible_room_orchestrator`
- `feishu_surface_adapter`
- `operator_console_backend`
- `review_decision`
- `override_recovery`
- `escalation`

交付结果：
补齐 CEO 的控制动作、交互表面和正式验收能力。

## 6. V1 关键流程如何落地

### 6.1 Idea Capture Loop

```text
CEO
  -> Chief of Staff
  -> IdeaBrief
  -> CEO intent memory
```

V1 要求：

- 不建完整 `TaskGraph`
- 生成 `IdeaBrief`
- 写入 `CEO intent memory`
- 建立最小 `WorkTicket`
- 可升级到 `department_task` 或 `formal_project`

### 6.2 Quick Consult Loop

```text
CEO
  -> one department
  -> ConsultNote
  -> Chief of Staff sync-back
```

V1 要求：

- 只激活一个部门
- 不强制 `Quality`
- 必须留下最小 `RunTrace`
- 必须挂接对应 `WorkTicket`
- 必须有 `sync-back`

### 6.3 Department Task Loop

```text
CEO
  -> one department
  -> TaskResult
  -> optional lightweight checkpoint
```

V1 要求：

- 使用最小 `TaskGraph`
- 支持轻量 checkpoint
- 默认只写相关 `department_shared` 和必要 `company_shared summary`
- 必须带 `goal_lineage_ref`
- 出现高风险或跨部门依赖时允许升级

### 6.4 Product Build Loop

```text
Chief of Staff
  -> Product Lead
  -> Delivery Lead
  -> Design Lead
  -> Engineering Lead
  -> Quality Lead
  -> synthesis
```

V1 要求：

- 这是默认正式项目流
- 必须有 artifact、trace、checkpoint
- 必须有 `GoalLineage`、`WorkTicket` 和预算阈值检查
- `Quality Lead` 必须同时支持证据采集和 verdict

### 6.5 Discovery / Synthesis Loop

```text
Chief of Staff
  -> Product Lead + Research Lead + Design Lead
  -> Cross-Agent Synthesis
  -> CEO / Product review
```

V1 要求：

- 允许多部门并行分析
- 必须统一综合，不允许简单拼接回答
- 结论要区分事实、推断、建议和待确认项
- recurring discovery 允许由 `scheduled_heartbeat` 触发，但仍需回到 `Chief of Staff`

### 6.6 Heartbeat / Event Trigger

```text
scheduled_heartbeat / event trigger
  -> Chief of Staff
  -> WorkTicket update or create
  -> optional department activation
  -> summary / follow-up task
```

V1 要求：

- 只支持预定义 recurring work
- 必须留下最小 `RunTrace`
- 必须带 `trigger_type`
- 默认受预算与审批规则约束

## 7. Memory 与 checkpoint 的 V1 落地范围

### 7.1 MemoryScope

- `agent_private`
- `department_shared`
- `company_shared`

### 7.2 MemoryKind

- `working`
- `episodic`
- `semantic`
- `procedural`
- `evidence`

### 7.3 V1 绑定关系

- `working`：
  仅存在于运行态和图 state，不交给 `mem0`
- `episodic / semantic`：
  V1 可由当前 Memory Fabric 或 tool bridge 提供 recall，是否额外接 `mem0` 属于后续优化，不作为本轮 agent plane 真相源
- `procedural`：
  放在 versioned registry
- `evidence`：
  放在 artifact store + metadata index
- `checkpoint`：
  由 `CheckpointStore` 作为 source of truth
- `WorkTicket`：
  作为 `TaskGraph / ConversationThread / RunTrace / artifacts` 的统一外层工作项

### 7.4 预算、触发与 ticket 的最小落地

- `BudgetPolicy`：
  V1 至少支持 `company / department / employee / task` 四层预算语义。
- `TriggerPolicy`：
  V1 至少支持 `manual / event_based / scheduled_heartbeat` 三类触发源。
- `WorkTicket`：
  V1 至少支持：
  `idea_capture`
  `department_task`
  `formal_project`
  `review_decision`
  `escalation`
  这些工作项的统一查询与追踪。

## 8. 依赖与风险

### 8.1 外部依赖

- `Docker`
- `OpenClaw`
- `LangGraph`
- `agency-agents`
- `Paperclip` 不作为依赖，只作为 control-plane benchmark

### 8.2 内部依赖顺序

- 没有 Docker 开发基线，环境一致性和后续迭代节奏都无法稳定。
- 没有 `Executive Office Core`，后续任何流程都无法稳定路由。
- 没有 `Department Runtime`，`WorkflowRecipe` 无法绑定到真实席位。
- 没有 `MemoryNamespace` 和 `CheckpointStore`，轻量流程与正式项目都会失去可追踪性。
- 没有 `OpenClawProvisioningService / OpenClawGatewayAdapter / OpenClawSessionBinding`，当前系统就仍然只是“自管模型调用”。
- 没有 `ConversationThread / ChannelBinding / FeishuSurfaceAdapter / FeishuMentionDispatch / VisibleRoomOrchestrator`，前端与飞书交互无法与主系统状态闭环。
- 没有 `approval_service`，高影响动作会停留在文档层定义，无法形成正式治理闭环。
- 没有 `Quality Gate`，`formal_project` 只能停留在“生成结果”，无法形成可审查交付。
- 没有 `GoalLineageService`，任务将无法回溯到公司目标。
- 没有 `BudgetPolicyService` 和 `TriggerScheduler`，V1 就无法形成最小可用的 control-plane 语义。

### 8.3 主要风险

- Host 与容器环境混用，导致依赖、路径、权限和网络行为不一致。
- 过早扩到全部 12 部门，导致 V1 范围失控。
- 把 Dashboard 和 Feishu 做成两套不同状态源，导致 thread、memory 和审批链断裂。
- 过早把 `review / override / escalation` 做成完整自治工作流，拖慢核心路径。
- 把 OpenClaw 只当模型配置层，而不是正式 agent plane，会让后续能力长期分叉。
- 把 `agency-agents` 角色直接当运行时角色，导致 seat model 失真。
- 把 `Paperclip` 当成现成依赖而不是 benchmark，会破坏当前主栈和概念层边界。

## 9. V1 完成定义

当以下条件全部满足时，V1 视为可冻结：

- 开发命令、依赖安装和测试都能在本机 Docker 容器内完成
- 4 个主交互模式都可跑通
- 核心 7 部门席位都可激活
- `Product Build Loop` 和 `Discovery / Synthesis Loop` 都能稳定执行
- `agent_private / department_shared / company_shared` 三层记忆都已落地
- `Web Dashboard` 与 `Feishu` 两个交互表面都已接到同一套系统状态
- 核心席位都已具备 `OpenClawWorkspaceBundle`、`OpenClawAgentBinding` 与 session binding
- Feishu 已满足私聊、单提及、多提及与 visible agent-to-agent 的 V1 语义
- `GoalLineage`、预算阈值、`scheduled_heartbeat / event trigger` 和 `WorkTicket` 都具备最小可用落点
- 高影响 `approval / rollback / promotion` 已具备最小可用治理路径
- `review_decision / override_recovery / escalation` 具备最小可用能力
- 控制台能够查看 run、artifact、checkpoint，并做基本控制动作
