# 开发路线图与周迭代计划

本文将当前开发方案正式固化为 V1 周迭代节奏，并补充 `V1.5 / V1.8 / V2` 的演进摘要。目标是让团队按周推进时有稳定的里程碑、依赖关系和冻结条件。

## 1. 路线图总览

### V1

目标：

- 跑通核心 7 部门
- 跑通 4 个主交互模式
- 跑通 `Product Build Loop` 与 `Discovery / Synthesis Loop`
- 跑通 `Memory Fabric` 的 V1 可用能力
- 提供最小可用 Operator Console
- 完成 `OpenClaw native agent provisioning`
- 完成 `Feishu visible-room orchestration`

### V1.5

目标：

- Core-7 OpenClaw 对齐
- `AGENTS.md / SKILLS.md` 进入 bootstrap
- per-agent native skills 正式化
- 新增 Dashboard `Agents` 模块
- 完成 repeat recall 语义召回
- 完成 Feishu card approval
- 固化 `Launch / Ops / Support Room`

### V1.8

目标：

- 引入 `Pulse / Trigger Engine`
- 引入 `Relationship Graph`
- 引入 `Skill Creator + Eval Loop`
- 引入 `CEO Visible Event Stream`
- 引入 memory promotion / policy guard / quotas

### V2

目标：

- 开放 `L2 department promotion`
- 加强 `department_shared procedural memory`
- 拆分高负载复合席位，优先拆 `Quality`
- 引入 `company template / org template / employee pack bundle`
- 新增 `Slack` 作为第二沟通平台

## 2. Week 1-8 计划

### Week 1：基础骨架

目标：

- 固定 Docker 本地开发基线
- 固定项目骨架
- 明确核心对象 schema
- 固定公司 profile、部门枚举和 7 个核心席位

重点：

- `主开发容器 + 依赖服务容器`
- `CompanyProfile`
- `VirtualDepartment`
- `VirtualEmployee`
- `DepartmentSeatMap`
- `RoleActivationPolicy`

前置依赖：

- 无

里程碑：

- 能清晰表示当前 V1 组织模型与默认配置
- 开发、调试、测试都可在本机 Docker 容器中执行

### Week 2：Executive Office 与交互模式

目标：

- 建立 CEO 指令入口和路由控制面
- 跑通轻量流程的基础服务逻辑

重点：

- `CEOCommand`
- `GoalRequest`
- `InteractionMode`
- `ParticipationScope`
- `SyncBackPolicy`
- `idea_capture / quick_consult / department_task`

前置依赖：

- Week 1 的基础 schema 和组织模型

里程碑：

- CEO 输入能稳定映射到正确的交互模式

### Week 3：OpenClaw Provisioning 与 Company Runtime

目标：

- 将席位编译成 OpenClaw 原生 agent
- 将正式流程接到 company workflow 运行时
- 建立 `TaskGraph`、`OpenClaw agent` 和 runtime state 的正式绑定

重点：

- `OpenClawWorkspaceCompiler`
- `OpenClawProvisioningService`
- `OpenClawGatewayAdapter`
- `WorkflowRecipeRegistry`
- `LangGraphRuntimeAdapter`
- `TaskGraph`
- `ExecutionTask`
- `Product Build Graph`
- `Discovery / Synthesis Graph`

前置依赖：

- Week 2 的路由与流程选择能力
- 核心席位与 `EmployeePack` 编译路径

里程碑：

- 至少两个正式流程能在 `OpenClaw agent plane + LangGraph company workflow` 下统一承接

### Week 4：Memory Fabric V1

目标：

- 建立三层长期 memory 的可用形态
- 接入 recall 与命名空间治理

重点：

- `MemoryNamespace`
- `MemoryRecord`
- `RecallQuery`
- `Mem0Bridge`
- `MemoryGovernanceService`
- `CheckpointStore` 的基础形态

前置依赖：

- Week 2 的流程入口
- Week 3 的 runtime state

里程碑：

- `agent_private / department_shared / company_shared` 可以被写入和 recall

### Week 5：Quality 与 artifacts

目标：

- 建立正式证据和 verdict 机制
- 让正式项目具备可审查产物
- 为高影响动作建立最小审批与审计能力

重点：

- `EvidenceArtifact`
- `QualityService`
- `DecisionRecord`
- `approval_service`
- `review_decision`
- 最小 `escalation`

前置依赖：

- Week 3 的正式流程图
- Week 4 的 memory 与 checkpoint 基础

里程碑：

- `formal_project` 不再只是流程执行，而是能形成 quality-backed 交付

### Week 6：Operator Console 与 Feishu Visible Orchestration

目标：

- 让 CEO / operator 能直接观察和控制系统
- 把 `Web Dashboard` 与 `Feishu` 接到同一套系统状态上
- 完成 Feishu 单提及 / 多提及 / visible agent-to-agent 的 V1 语义

重点：

- run 列表
- 当前交互模式
- Department activation 展示
- TaskGraph 状态
- artifact / memory summary / checkpoint 展示
- approve / retry / rollback / override 操作
- `conversation_thread_service`
- `channel_binding_service`
- `openclaw_session_binding`
- `feishu_mention_dispatch`
- `visible_room_orchestrator`
- `feishu_surface_adapter`
- `visible-room fan-out` 房间策略

前置依赖：

- Week 3-5 的后端对象和状态接口

里程碑：

- 内部控制台可支持日常测试和验收
- `Web Dashboard` 与 `Feishu` 已共享长期状态并隔离 thread 上下文
- Feishu 已满足私聊、单提及、多提及和 visible agent-to-agent 的正式语义

### Week 7：Override / Recovery / 稳定化

目标：

- 打通停掉、改向、回滚与恢复
- 建立流程升级路径

重点：

- `override_recovery`
- `Checkpoint restore`
- `supersede refs`
- 状态迁移与恢复
- 轻量流程向正式流程的升级

前置依赖：

- Week 4 的 `CheckpointStore`
- Week 5 的 `DecisionRecord`

里程碑：

- CEO 能在不中断整体系统语义的情况下调整方向和恢复状态

### Week 8：集成验收与冻结

目标：

- 跑完核心场景
- 清理超范围内容
- 冻结 V1 范围

重点：

- 核心验收场景
- 公开库边界检查
- memory scope 检查
- V1 backlog 清理

前置依赖：

- Week 1-7 的所有核心模块

里程碑：

- V1 达到可冻结状态，并可输出 `V1.5 / V1.8 / V2` backlog

## 3. 关键依赖链

### 主路径

```text
基础 schema
  -> Executive Office
  -> Department Runtime
  -> WorkflowRecipe
  -> LangGraph runtime
  -> Memory Fabric
  -> Quality
  -> Console
  -> Override / Recovery
  -> Acceptance
```

### 风险最高的依赖项

- Docker 开发基线如果没有先固定，后续所有模块都可能受到环境漂移影响。
- `Executive Office` 和 `InteractionMode` 如果不稳，后续所有流程都会返工。
- `Department Runtime` 如果先做错，`Employee Pack` 和 memory scope 会一起漂移。
- 交互表面如果没有统一到 `ConversationThread` 和 `ChannelBinding`，Web / Feishu 会演变成两套状态机。
- 如果没有先固定 `OpenClawProvisioningService` 和 `OpenClawSessionBinding`，后续 Feishu / Dashboard 只会回退成“自管模型调用”。
- `CheckpointStore` 如果过晚落地，`override_recovery` 会变成补丁式能力。

## 4. V1 冻结条件

只有满足以下条件，V1 才能冻结：

- 本机 Docker 开发栈已经稳定承载开发、运行和测试
- 4 个主交互模式都可跑通
- `review_decision / override_recovery / escalation` 具备最小可用能力
- `Product Build Loop` 和 `Discovery / Synthesis Loop` 都通过验收
- 核心 7 部门都能被正确激活
- `agent_private / department_shared / company_shared` 三层 memory 都完成 V1 落地
- `Web Dashboard` 与 `Feishu` 都接入统一状态模型
- 核心席位都已具备 `OpenClaw agent binding + workspace bundle`
- Feishu 已实现 `visible-room fan-out`
- `ApprovalGate` 已通过最小治理链落地
- `Quality Lead` 的 `evidence -> verdict` 双模式可用
- Operator Console 能查看和控制关键状态

## 5. V1.5 / V1.8 / V2 摘要

### V1.5

- Core-7 OpenClaw 与 Dashboard 完全对齐
- `AGENTS.md / SKILLS.md` 进入 runtime bootstrap
- 每个核心 bot 具备 workspace-local native skills
- Dashboard 新增 `Agents` 模块
- repeat recall 语义召回进入正式能力
- Feishu 消息卡审批闭环
- `Launch / Ops / Support Room` 进入正式模板
- 当前明确排除：
  `Company Plaza`
  `Growth / Support` 独立 bot

### V1.8

- 新增 `Pulse / Trigger Engine`
- 新增 `Relationship Graph`
- 新增 `Skill Creator + Eval Loop`
- 新增 `CEO Visible Event Stream`
- 增强 memory promotion、policy guard、quota 与 trigger 治理
- 保持 `Company Plaza not in scope`

### V2

- 开放 `L2 department promotion`
- 强化 procedural memory
- 把 `Quality Lead` 从单席位双模式拆成双员工
- 新增 `SlackSurfaceAdapter`
- 让 `Slack` 成为第二沟通平台
- 加强公司 cadence：
  `daily sync`
  `weekly review`
  `monthly checkpoint`

## 6. V1.5 / V1.8 开发阶段

### Phase 0：Docs Sync

- 统一 `README`、路线图、封板清单、架构文档、前端方案、验收文档口径
- 补 `V1.8 Enhancement Roadmap`
- 去掉 `Company Plaza` 与 `Growth / Support` 独立 bot 的 V1.5 叙事

### Phase 1：Core-7 OpenClaw 对齐

- OpenClaw provision 全部切到 `core_only=true`
- 清理 5 个非核心历史 agent / workspace
- `AGENTS.md / SKILLS.md` 进入 bootstrap-extra-files

### Phase 2：Native Skills 正式化

- 完成 `skill sync -> native export -> discovery -> verification`
- 每个核心 bot 固定为 `30` 专业 + `10` 通用 native skills
- 全量验证 source / install / discovery / invocation / result

### Phase 3：Dashboard Agents 模块

- 新增 `Agents` 一级页面
- 统一展示 identity、native skills、memory、runtime、config
- Dashboard 成为 agent 文件与配置的项目侧 source of truth

### Phase 4：Feishu V1.5 收口

- 完成 card approval live 闭环
- 完成 repeat recall live 验证
- 完成 `Launch / Ops / Support Room` 模板联调

### Phase 5：V1.8 预埋点

- 只预埋 `Pulse / Trigger Engine`
- 只预埋 `Relationship Graph`
- 只预埋 `Skill Creator + Eval Loop`
- 只预埋 `CEO Visible Event Stream`

## 7. 不应提前进入 V1.5 / V1.8 的事项

- 全量 12 部门日常化参与
- `Company Plaza`
- `Growth / Support` 独立 bot
- 深度自我进化与自动 policy promotion
- 重型多租户
- 复杂外部身份与权限集成
- 产品级前端体验优化
