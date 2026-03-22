# 系统架构与模块拆解

本文把现有设计方案转换为实现模块视角，重点说明 V1 中哪些对象是概念接口，哪些对象是内部实现模块，模块之间的依赖关系是什么，以及 memory 与 checkpoint 的实现边界如何落地。

## 1. 三层视角

### 产品概念层

- `CEO`
- `Chief of Staff`
- `VirtualDepartment`
- `VirtualEmployee`
- `WorkflowRecipe`
- `Memory Fabric`

这一层回答“系统是什么”。

### 实现模块层

- `ExecutiveOfficeCore`
- `InteractionRouter`
- `DepartmentRuntime`
- `OpenClawProvisioningService`
- `OpenClawGatewayAdapter`
- `OpenClawWorkspaceCompiler`
- `SkillCatalogService`
- `OpenClawNativeSkillExporter`
- `OpenClawNativeSkillVerifier`
- `OpenClawSessionBinding`
- `LangGraphRuntimeAdapter`
- `FeishuMentionDispatch`
- `VisibleRoomOrchestrator`
- `RepeatRecallResolver`
- `CheckpointStore`
- `MemoryGovernanceService`
- `QualityService`
- `AgentDetailAggregator`
- `AgentConfigSyncService`

这一层回答“谁来实现”。

### 开发执行层

- 项目结构
- 模块依赖
- 数据流
- 迭代顺序
- 验收场景

这一层回答“先做什么、后做什么”。

## 2. V1 系统形态

### 2.1 运行形态

- `Python` 单体后端
- 简单 `Operator Console`
- 本机 `Docker` 开发栈
- 单数据库主系统
- 单默认公司实例

### 2.2 本机 Docker 开发基线

V1 的开发环境固定为：
`Host + Docker + 主开发容器 + 依赖服务容器`

推荐的开发拓扑：

```text
Host machine
  -> IDE / terminal
  -> Docker Engine / Docker Desktop

Docker network
  -> app-dev container
  -> postgres
  -> redis
  -> vector-db
  -> object-store
```

固定规则：

- 代码仓库挂载到主开发容器中进行开发。
- 所有依赖安装、命令执行、测试和调试都在主开发容器内完成。
- 所有 V1 基础设施优先以 sidecar 容器提供，不依赖 Host 已安装服务。
- Host 不作为 Python、Node、数据库、缓存或对象存储的运行环境。

### 2.3 公开库位置

| 层 | 绑定 | 说明 |
| --- | --- | --- |
| 资产层 | `agency-agents` | 只提供 persona/workflow 上游资产 |
| agent plane | `OpenClaw` | 只提供单 agent runtime、skills、tools、sessions、sandbox |
| company workflow 层 | `LangGraph` | 只提供 company workflow graph/subgraph 执行能力 |
| 长期记忆治理层 | 当前 `Memory Fabric` | 提供长期记忆、checkpoint、approval、promotion 与 evidence |

固定边界：

- `agency-agents` 不定义部门边界，不做 scheduler。
- `OpenClaw` 不定义 `Chief of Staff`，不定义公司组织模型。
- `LangGraph` 不定义单 agent 会话语义。
- 当前 `Memory Fabric` 不下沉为 agent session store。

### 2.4 Interaction Surfaces

V1 的交互表面固定为两种：

| 表面 | 定位 | 默认职责 |
| --- | --- | --- |
| `Web Dashboard` | 主控制面 | 全量沟通、状态观察、agent 管理、memory、checkpoint、审批 |
| `Feishu` | 协作与会话表面 | 部门私聊、项目群聊、轻量通知和会议式互动 |

两种表面都挂到同一套底层系统：

```text
Conversation Surface
  -> ExecutiveOfficeCore
  -> FeishuMentionDispatch / VisibleRoomOrchestrator
  -> OpenClawGatewayAdapter
  -> DepartmentRuntime
  -> WorkflowRecipe
  -> TaskGraph
  -> Memory Fabric
  -> RunTrace
```

固定边界：

- `Web Dashboard` 不是第二套 runtime。
- `Feishu` 不是配置或 memory 的 source of truth。
- `Feishu` 在 V1 走 `visible-room fan-out`，不直接等于 OpenClaw shared groups。
- 两种表面共享长期 memory，但不共享短期 thread 上下文。
- 两种表面的本地开发、联调和测试都必须在 Docker 容器环境中完成。

## 3. 关键概念接口

### 3.1 输入与路由

| 对象 | 作用 | V1 负责模块 |
| --- | --- | --- |
| `CEOCommand` | CEO 的原始指令 | `ceo_command_service` |
| `GoalRequest` | 标准化目标对象 | `executive_routing_service` |
| `GoalLineage` | 目标血缘链 | `goal_lineage_service` |
| `TriggerPolicy` | 手动、事件、heartbeat 统一触发策略 | `executive_routing_service` + `trigger_scheduler` |
| `InteractionMode` | 交互类型 | `interaction_mode_classifier` |
| `ParticipationScope` | 参与范围 | `executive_routing_service` |
| `SyncBackPolicy` | 回写策略 | `executive_routing_service` |

### 3.2 组织与席位

| 对象 | 作用 | V1 负责模块 |
| --- | --- | --- |
| `VirtualDepartment` | 部门边界 | `department_runtime_service` |
| `VirtualEmployee` | 部门席位 | `employee_pack_compiler` |
| `DepartmentSeatMap` | 部门到席位映射 | `persona_source_adapter_agency_agents` + `employee_pack_compiler` |
| `AgentProfile` | 运行时席位配置 | `employee_pack_compiler` |
| `OpenClawAgentBinding` | `employee_id -> openclaw_agent_id -> workspace/channel accounts` | `openclaw_provisioning_service` |
| `OpenClawWorkspaceBundle` | OpenClaw 原生 bootstrap 文件集合 | `openclaw_workspace_compiler` |

### 3.3 执行与追踪

| 对象 | 作用 | V1 负责模块 |
| --- | --- | --- |
| `WorkflowRecipe` | 流程模板 | `workflow_recipe_registry` |
| `WorkTicket` | 正式工作项 | `work_ticket_service` |
| `TaskGraph` | 执行任务图 | `taskgraph_service` |
| `ExecutionTask` | runtime 执行单元 | `langgraph_runtime_adapter` |
| `RunTrace` | 端到端追踪 | `runtrace_service` |

### 3.4 表面与通道

| 对象 | 作用 | V1 负责模块 |
| --- | --- | --- |
| `ConversationSurface` | 交互表面枚举 | `conversation_thread_service` |
| `ConversationThread` | 具体会话线程 | `conversation_thread_service` |
| `ChannelBinding` | 表面与默认路由绑定 | `channel_binding_service` |
| `RoomPolicy` | 群聊主持与发言策略 | `channel_binding_service` |
| `OpenClawSessionBinding` | 表面线程与 OpenClaw sessionKey 的绑定 | `openclaw_session_binding` |
| `VisibleRoomPolicy` | Feishu / Slack 的可见协作约束 | `visible_room_orchestrator` |

### 3.5 Memory 与治理

| 对象 | 作用 | V1 负责模块 |
| --- | --- | --- |
| `MemoryRecord` | 记忆实体 | `memory_namespace_service` |
| `MemoryNamespace` | 记忆命名空间 | `memory_namespace_service` |
| `RecallQuery` | recall 查询对象 | `memory_bridge_service` |
| `BudgetPolicy` | 预算阈值与 override 规则 | `budget_policy_service` |
| `Checkpoint` | 可恢复节点 | `checkpoint_store` |
| `EvidenceArtifact` | 证据对象 | `artifact_store` |
| `ApprovalGate` | 高风险审批控制点 | `approval_service` |

## 4. 内部实现模块

### 4.1 ExecutiveOfficeCore

职责：

- `CEOCommand` 接收
- `GoalRequest` 归一化
- `InteractionMode` 推断
- 流程入口统一
- `sync-back`
- executive synthesis

依赖：

- `interaction_mode_classifier`
- `department_activation_service`
- `workflow_recipe_registry`
- `runtrace_service`

### 4.2 InteractionRouter

职责：

- 识别：
  `idea_capture`
  `quick_consult`
  `department_task`
  `formal_project`
  `review_decision`
  `override_recovery`
  `escalation`
- 绑定默认 `ParticipationScope`
- 绑定默认升级目标
- 识别 `manual / event_based / scheduled_heartbeat` 三类触发源

依赖：

- `executive_routing_service`
- `workflow_recipe_registry`
- `goal_lineage_service`

### 4.3 DepartmentRuntime

职责：

- 加载 `VirtualDepartment`
- 加载 `VirtualEmployee`
- 绑定 `DepartmentSeatMap`
- 为席位注入 tool/memory profile

依赖：

- `persona_source_adapter_agency_agents`
- `employee_pack_compiler`
- `memory_namespace_service`

### 4.4 PersonaSourceAdapter

职责：

- 从 `agency-agents` 提取上游资产
- 生成 `PersonaPack`
- 生成 `DepartmentSeatMap` 的原始输入

边界：

- 不直接执行
- 不直接路由
- 不直接决定 runtime graph

### 4.5 EmployeePackCompiler

职责：

- 把一个或多个 `PersonaPack` 组合成 `VirtualEmployee`
- 生成 seat-level rules、workflow hints、memory profile、tool/sandbox hints
- 生成 seat-level role contract 与 `EmployeeSkillPack`

输出：

- `VirtualEmployee`
- `AgentProfile`
- seat-level `Employee Pack`
- `EmployeeSkillPack`
- `SkillManifest[]`

### 4.6 OpenClawWorkspaceCompiler

职责：

- 将 `Employee Pack` 编译成 `OpenClawWorkspaceBundle`
- 生成：
  `AGENTS.md`
  `SOUL.md`
  `IDENTITY.md`
  `BOOTSTRAP.md`
  `SKILLS.md`
  `TOOLS.md`
  `USER.md`
  `HEARTBEAT.md`

### 4.6A SkillCatalogService

职责：

- 管理 skill catalog、`SkillSourceRef`、`SkillManifest`
- 为每个席位生成 `30` 专业 + `10` 通用 skills 的正式集合
- 管理 GitHub source / license / install / verify metadata

### 4.6B OpenClawNativeSkillExporter

职责：

- 将 `SkillManifest` 物化为 workspace-local native skill folders
- 为每个 agent 生成 `skills/<skill-slug>/SKILL.md`
- 保证 OpenClaw Skills 页可发现 per-agent native skills

### 4.6C OpenClawNativeSkillVerifier

职责：

- 校验 native skill 的 source / install / discovery / invocation / result
- 标记 invalid skills
- 为 Dashboard `Agents` 模块提供 validation 状态

### 4.7 OpenClawProvisioningService

职责：

- 生成 `OpenClawAgentBinding`
- 生成 workspace、agentDir、channel account 与 tool/sandbox policy
- 为每个核心席位提供正式 `openclaw_agent_id`

### 4.8 OpenClawGatewayAdapter

职责：

- 从 Dashboard / Feishu / workflow 节点调用真实 OpenClaw agent
- 维护单 agent 执行与外层 `ConversationThread / WorkTicket / RunTrace` 的映射
- 作为未来替代当前过渡性 `OpenClawDialogueService` 的正式实现路径

### 4.9 LangGraphRuntimeAdapter

职责：

- 将 `WorkflowRecipe` 编译为 graph/subgraph
- 将 `TaskGraph` 与 runtime state 绑定
- 提供 task start、handoff、quality、checkpoint hook
- 将 `GoalLineage`、`WorkTicket`、`trigger_type` 注入 runtime state

V1 承接图：

- `Idea Capture Graph`
- `Quick Consult Graph`
- `Department Task Graph`
- `Product Build Graph`
- `Discovery / Synthesis Graph`

### 4.10 GoalLineageService

职责：

- 维护：
  `company_goal -> initiative -> project -> task -> execution`
- 为 `GoalRequest / TaskGraph / ExecutionTask / RunTrace` 提供稳定引用
- 保证正式任务都能回溯到上层公司目标

### 4.11 WorkTicketService

职责：

- 统一管理轻量任务、正式项目、review、escalation 的工作项外壳
- 将 `ConversationThread`、`TaskGraph`、`RunTrace`、`artifacts` 绑定到同一 ticket
- 为 Dashboard 提供面向 operator 的工作项视图

### 4.12 MemoryBridgeService

职责：

- 构建 `RecallQuery`
- 处理长期 memory recall 与 metadata 对齐
- 为 OpenClaw 提供 memory tool bridge，而不是直接把长期记忆写进 prompt

边界：

- 不管理 `working memory`
- 不管理 `procedural registry`
- 不管理 `checkpoint / approval / promotion`

### 4.13 BudgetPolicyService

职责：

- 管理 `company / department / employee / task` 四层预算
- 提供 `soft alert / hard stop / override` 规则
- 为高影响预算越界动作提供审批挂点

### 4.14 TriggerScheduler

职责：

- 管理 `scheduled_heartbeat`
- 接收 `event_based` 触发并转交 `ExecutiveOfficeCore`
- 限制系统触发只能命中预定义 recurring work

当前定位：

- `V1.5` 只保留接口与模型前置，不宣称完整上线
- `V1.8` 才进入正式 `Pulse / Trigger Engine`

### 4.15 CheckpointStore

职责：

- 保存 `Checkpoint`
- 记录 `TaskGraph snapshot`
- 记录 `memory_snapshot_refs`
- 记录 `artifact_refs`
- 执行 rollback 恢复

### 4.16 MemoryGovernanceService

职责：

- 管理 `promotion`
- 管理 `supersede`
- 管理 `rollback` 后的记忆状态
- 管理共享 memory 的审批边界

### 4.14 QualityService

职责：

- 以一个 `Quality Lead` 席位承载两种模式：
  `evidence`
  `verdict`
- 为正式项目和高风险任务产出：
  `EvidenceArtifact`
  `DecisionRecord`

### 4.15 OperatorConsoleBackend

职责：

- 提供 CEO / operator 所需数据接口
- 展示当前 run、交互模式、部门激活、TaskGraph、artifact、checkpoint
- 展示 `GoalLineage`、预算状态、`WorkTicket`
- 执行 approve、retry、override、rollback

### 4.16 ConversationThreadService

职责：

- 统一管理 `dashboard / feishu_dm / feishu_group` 的线程模型
- 将表面级 thread 绑定到 `RunTrace`、`TaskGraph` 和 memory 过滤条件
- 保证不同表面共享长期 memory，但短期上下文隔离

### 4.17 OpenClawSessionBinding

职责：

- 将 `ConversationThread / surface / channel` 绑定到 `OpenClaw sessionKey`

### 4.17A AgentDetailAggregator

职责：

- 聚合单个 agent 的 workspace files、native skills、memory、recent runs / sessions、bindings / hooks
- 为 Dashboard `Agents` 页面提供统一 detail view

### 4.17B AgentConfigSyncService

职责：

- 承接 workspace files、hook overrides、binding overrides 的保存与同步
- 触发 provision sync 与 native skill re-check
- 固定：
  `agent:<agentId>:feishu:dm:<senderId>`
  `agent:<agentId>:feishu:group:<chatId>`
- 保证 session 不替代外层 `ConversationThread`

### 4.18 ChannelBindingService

职责：

- 管理 `BotSeatBinding`
- 管理 `ChannelBinding`
- 管理 `RoomPolicy`
- 为 Feishu 私聊、群聊和 Dashboard 入口提供默认路由策略

### 4.19 FeishuMentionDispatch

职责：

- 将 Feishu `私聊 / 单提及 / 多提及` 映射到目标 agent 集合
- 保持去重维度为 `app_id + message_id`
- 保证未被 @ 的 bot 不参与回复

### 4.20 VisibleRoomOrchestrator

职责：

- 管理 visible-room fan-out
- 管理可见的 agent-to-agent 轮次发言
- 管理 transcript mirror 到 Dashboard / RunTrace

### 4.20A RepeatRecallResolver

职责：

- 识别用户显式召回与 LLM 语义召回
- 识别 peer 在可见正文中对 bot 的再次点名
- 约束同一 bot 默认只主动发言一次，但允许被明确召回后返场

### 4.21 FeishuSurfaceAdapter

职责：

- 承接 Feishu 私聊和群聊事件
- 将外部会话映射为系统内部 `ConversationThread`
- 调用 `FeishuMentionDispatch` 与 `VisibleRoomOrchestrator`
- 将目标 agent 请求转交 `OpenClawGatewayAdapter`

边界：

- 不实现底层组织模型
- 不绕过 `ExecutiveOfficeCore`
- 不作为配置或 memory 的 source of truth
- 不直接替代 OpenClaw agent runtime

### 4.22 ApprovalService

职责：

- 承接 `ApprovalGate`
- 管理 review、approval、rollback、promotion、budget override 的最小治理流
- 为 Dashboard 和高风险流程提供统一审批入口

## 5. 模块依赖关系

### 5.1 高层依赖图

```text
ceo_command_service
  -> ExecutiveOfficeCore
  -> InteractionRouter
  -> GoalLineageService
  -> WorkTicketService
  -> DepartmentRuntime
  -> OpenClawProvisioningService
  -> OpenClawGatewayAdapter
  -> WorkflowRecipeRegistry
  -> LangGraphRuntimeAdapter
  -> QualityService
  -> ConversationThreadService
  -> ApprovalService
  -> RunTraceService

DepartmentRuntime
  -> PersonaSourceAdapter
  -> EmployeePackCompiler
  -> OpenClawWorkspaceCompiler
  -> MemoryNamespaceService

ConversationThreadService
  -> ChannelBindingService
  -> OpenClawSessionBinding
  -> FeishuMentionDispatch
  -> VisibleRoomOrchestrator
  -> FeishuSurfaceAdapter
  -> RunTraceService

MemoryNamespaceService
  -> MemoryBridgeService
  -> CheckpointStore
  -> MemoryGovernanceService
  -> ArtifactStore

TriggerScheduler
  -> ExecutiveOfficeCore
  -> WorkTicketService
  -> BudgetPolicyService
```

### 5.2 关键前置依赖

- `ExecutiveOfficeCore` 是所有流程的共同前置。
- `GoalLineageService` 是正式任务进入 control-plane 语义的必要前置。
- `DepartmentRuntime` 是任何部门激活和席位运行的前置。
- `OpenClawProvisioningService` 与 `OpenClawGatewayAdapter` 是 agent plane 成立的前置。
- `LangGraphRuntimeAdapter` 是正式 company workflow 和可追踪执行的前置。
- `WorkTicketService` 是统一串联 thread、run、artifact 和任务状态的必要前置。
- `CheckpointStore` 是 `override_recovery` 的必要前置。
- `ConversationThreadService` 是 Web / Feishu 两种表面进入同一系统状态的必要前置。
- `FeishuMentionDispatch` 与 `VisibleRoomOrchestrator` 是 V1 Feishu 可见协作语义的必要前置。
- `ApprovalService` 是 review、rollback 和高风险动作闭环的必要前置。
- `QualityService` 是 `formal_project` 产出正式 verdict 的必要前置。
- `BudgetPolicyService` 是当前预算治理闭环的必要前置。
- `TriggerScheduler` 是 `V1.8` Pulse / Trigger Engine 的前置，不应在 `V1.5` 被误写成已完整上线。

## 6. 典型数据流

### 6.1 轻量流程数据流

```text
CEOCommand
  -> ExecutiveOfficeCore
  -> InteractionRouter
  -> GoalLineageService
  -> WorkTicket create/update
  -> target department
  -> minimal result
  -> RunTrace
  -> sync-back
  -> targeted memory write
```

适用：

- `idea_capture`
- `quick_consult`
- `department_task`

### 6.2 正式项目数据流

```text
CEOCommand
  -> GoalRequest
  -> GoalLineage
  -> WorkTicket
  -> Department activation
  -> WorkflowRecipe
  -> TaskGraph
  -> LangGraph execution
  -> EvidenceArtifact
  -> Quality verdict
  -> Executive synthesis
  -> Checkpoint
  -> RunTrace
```

适用：

- `formal_project`
- `review_decision`
- `override_recovery`
- `escalation`

## 7. Memory 与 checkpoint 的实现边界

### 7.1 MemoryScope

- `run`
- `agent_private`
- `department_shared`
- `company_shared`

### 7.2 MemoryKind

- `working`
- `episodic`
- `semantic`
- `procedural`
- `evidence`

### 7.3 V1 实现边界

| 能力 | V1 承接方式 | 说明 |
| --- | --- | --- |
| `goal lineage` | `GoalLineageService` | 正式任务必须可回溯到公司目标 |
| `work ticket` | `WorkTicketService` | 统一工单、线程、运行与交付状态 |
| `budget policy` | `BudgetPolicyService` | 支持四层预算与 override |
| `trigger model` | `TriggerScheduler` + `ExecutiveOfficeCore` | `V1.5` 只保留模型前置，`V1.8` 正式支持 manual / event / heartbeat |
| `openclaw workspace` | `OpenClawWorkspaceCompiler` | 为核心席位生成原生 workspace bundle |
| `skill catalog` | `SkillCatalogService` | 管理岗位级 skill pack 与 source metadata |
| `native skill export` | `OpenClawNativeSkillExporter` | 将 skill catalog 物化成 workspace-local native skills |
| `native skill verify` | `OpenClawNativeSkillVerifier` | 校验 source / install / discovery / invocation / result |
| `openclaw agent runtime` | `OpenClawGatewayAdapter` | 承接单 agent 原生执行 |
| `feishu visible orchestration` | `FeishuMentionDispatch` + `VisibleRoomOrchestrator` | 承接单提及 / 多提及 / visible agent-to-agent |
| `repeat recall` | `RepeatRecallResolver` | 允许用户或 peer 明确召回 bot 再次回复 |
| `working` | runtime state / cache | 不进入长期治理记忆 |
| `episodic` | `MemoryBridgeService` | 长期经验 recall |
| `semantic` | `MemoryBridgeService` | 事实与知识 recall |
| `procedural` | versioned registry | 不交给 agent session |
| `evidence` | `ArtifactStore` + metadata | 原件与索引分离 |
| `checkpoint` | `CheckpointStore` | source of truth |
| `promotion / approval` | `MemoryGovernanceService` | 本项目自定义 |

### 7.4 默认写入边界

- `agent_private`：
  允许自动写入
- `department_shared`：
  需要部门席位确认或 `Chief of Staff` 审批
- `company_shared`：
  需要 `Chief of Staff` 管理，高影响项再交 CEO
- 预算和 trigger 的审计轨迹：
  默认进入 `RunTrace` 与审批记录，不直接写成长期 memory

## 8. 目录与代码组织建议

V1 推荐的服务划分：

```text
app/
  company/
  executive_office/
  departments/
  workflows/
  runtime/
  memory/
  quality/
  artifacts/
  checkpoints/
  runtrace/
  console/
```

说明：

- 这是建议的开发骨架，不是这一步要创建的代码结构。
- 代码实现时仍应优先服务于当前文档定义的模块边界，而不是照抄目录名。
