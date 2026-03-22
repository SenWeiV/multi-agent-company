# 验收标准与测试场景

本文将现有设计方案收敛为 V1 的正式验收标准。它不是测试代码设计文档，而是开发完成后用于判断 V1 是否达标的场景集合。

## 1. 验收原则

- 所有验收都以当前设计文档为准，不新增新的产品级概念。
- 轻量流程也必须留下最小 `RunTrace` 和 `sync-back`。
- 正式流程必须留下 artifact、checkpoint 和 quality verdict。
- 公开库只能承担文档中明确分配给它们的层，不允许出现框架越权。

## 2. 交互模式验收

### 2.1 `idea_capture`

目标：

- CEO 只说一个模糊想法时，系统不拉起完整部门链。

通过条件：

- 生成 `IdeaBrief`
- 写入 `CEO intent memory`
- 默认不创建完整 `TaskGraph`
- 该想法可以被后续升级为 `department_task` 或 `formal_project`

### 2.2 `quick_consult`

目标：

- CEO 直接咨询某一个部门，系统只激活该部门。

通过条件：

- 只激活目标部门
- 生成 `ConsultNote`
- 保留最小 `RunTrace`
- 结果被 `sync-back` 到 `Chief of Staff`

### 2.3 `department_task`

目标：

- CEO 下发一个单部门小任务，系统不误拉多部门协作。

通过条件：

- 使用最小 `TaskGraph`
- 输出 `TaskResult`
- 默认不强制完整 `Quality`
- 在必要时可升级为 `formal_project` 或 `escalation`

### 2.4 `formal_project`

目标：

- CEO 发起正式项目，系统走默认正式项目流。

通过条件：

- 路径包含：
  `Chief of Staff`
  `Product`
  `Project Management`
  `Design`
  `Engineering`
  `Quality`
- 产出 deliverable
- 产出 `EvidenceArtifact`
- 产出 `Checkpoint`
- 能显示对应 `GoalLineage`

### 2.5 `review_decision`

目标：

- CEO 能基于已有产物和证据做复核，而不是重新开项目。

通过条件：

- 读取既有 artifact / evidence / checkpoint
- 生成 `DecisionRecord`
- 决策结果写回 trace 和必要 memory

### 2.6 `override_recovery`

目标：

- CEO 能停止、改向或回滚当前路径。

通过条件：

- 系统能定位 checkpoint
- 恢复 `TaskGraph` 或更新状态
- 标记 superseded memory / artifacts
- 生成 `OverrideDecision`

### 2.7 `escalation`

目标：

- 多部门冲突、高风险或连续失败时，系统能正式升级处理。

通过条件：

- 生成 `EscalationSummary`
- 列出冲突点、风险和建议动作
- 不直接静默推进执行
- 可回到合适主流程继续处理

## 3. Memory Scope 验收

### 3.1 `agent_private`

目标：

- 每个席位能读取并更新自己的私有记忆。

通过条件：

- Engineering Lead 能读回自己的历史经验
- 不能默认读到其他席位的私有记忆

### 3.2 `department_shared`

目标：

- 部门可复用自己的共享知识和 checklist。

通过条件：

- Design Lead 提升的 checklist 能被同部门后续任务 recall
- 默认不能被不相关部门直接读取

### 3.3 `company_shared`

目标：

- 公司级战略和事实能被授权部门一致读取。

通过条件：

- CEO 更新季度战略后，Product、Research、Executive Office 能检索到一致描述
- 高敏内容仍受授权限制

### 3.4 共享升级边界

目标：

- 共享 memory 的 promotion 不应被 agent 静默完成。

通过条件：

- `agent_private` 允许自动写入
- `department_shared` 需要部门或 Executive Office 审批
- `company_shared` 需要 `Chief of Staff` 管理，高影响项再交 CEO

## 4. Quality Gate 验收

### 4.1 单席位双模式

目标：

- `Quality Lead` 保持一个部门席位，但逻辑上仍有 `evidence -> verdict` 两步。

通过条件：

- 正式项目先形成 `EvidenceArtifact`
- 再形成放行或驳回结论
- 外部仍只看到一个 `Quality` 部门席位

### 4.2 GO / NO-GO

目标：

- 放行结论必须基于证据而不是口头完成。

通过条件：

- 每个 `GO / NO-GO` 结论都能找到对应 evidence refs
- `NO-GO` 能触发 checkpoint 或 recovery 路径

## 5. Checkpoint / Rollback 验收

### 5.1 正式 checkpoint

目标：

- 正式项目在关键节点可冻结并恢复。

通过条件：

- checkpoint 至少记录：
  `TaskGraph snapshot`
  `memory refs`
  `artifact refs`
  `approval / verdict state`

### 5.2 轻量 checkpoint

目标：

- `department_task` 在需要时能建立轻量 checkpoint。

通过条件：

- 不强制完整项目级状态
- 仍能支持回退到关键节点

### 5.3 rollback

目标：

- `override_recovery` 与 `Quality NO-GO` 都能使用 checkpoint。

通过条件：

- 能恢复最近有效 checkpoint
- 能标记 superseded 结果
- 恢复后能继续推进而不是重头开始

## 6. Goal Lineage / Budget / Trigger / Ticket 验收

### 6.1 Goal Lineage

目标：

- 正式任务必须可追溯到公司目标，而不是孤立执行。

通过条件：

- `formal_project` 能显示：
  `company_goal -> initiative -> project -> task -> execution`
- `GoalRequest`、`TaskGraph`、`ExecutionTask`、`RunTrace` 之间存在稳定 `goal_lineage_ref`

### 6.2 Budget Governance

目标：

- 系统具备最小可用的公司级成本治理，而不是只有零散的工具预算。

通过条件：

- 支持：
  `company budget`
  `department budget`
  `employee budget`
  `task budget`
- 超过告警阈值时产生提示
- 超过硬阈值时触发停下或审批

### 6.3 Trigger Model

目标：

- 系统不仅支持 CEO 手动发起，还支持最小可用的事件和 heartbeat 触发。

通过条件：

- 存在：
  `manual`
  `event_based`
  `scheduled_heartbeat`
  三类触发源
- heartbeat 只能触发预定义 recurring work
- heartbeat 结果能回写 `RunTrace` 和必要 `WorkTicket`

### 6.4 WorkTicket

目标：

- 正式工作项不再散落在 thread、run、artifact 三个孤立对象里。

通过条件：

- `department_task`
  `formal_project`
  `review_decision`
  `escalation`
  都能挂到统一 `WorkTicket`
- `WorkTicket` 能关联：
  `ConversationThread`
  `TaskGraph`
  `RunTrace`
  `artifacts`

## 7. 表面交互验收

### 7.1 Dashboard surface

目标：

- `Web Dashboard` 能作为主控制面承接核心交互与治理动作。

通过条件：

- 能承接 `idea_capture / quick_consult / department_task / formal_project`
- 能查看 `TaskGraph / RunTrace / EvidenceArtifact / Checkpoint`
- 能执行 review、approval、rollback 等高影响操作

### 7.2 Feishu DM surface

目标：

- CEO 能在 Feishu 私聊某个部门机器人并进入单部门流程。

通过条件：

- 私聊 `Engineering bot` 时，只进入单部门流程
- 私聊 `Chief of Staff bot` 时，只由 `Chief of Staff` 对应 agent 回复
- trace 和必要 memory 能回写到系统主状态
- 不会误拉起完整项目链

### 7.3 Feishu group surface

目标：

- 多部门群聊在 V1 中满足精确 mention 与可见协作，而不是多 bot 无序抢答。

通过条件：

- 群里只 `@` 一个 bot，只该 bot 回复
- 群里同时 `@` 多个 bot，这些 bot 都回复
- 未被 `@` 的 bot 不响应
- `Project Room` 中允许 visible agent-to-agent exchange，但必须对 CEO 可见
- 群聊讨论结果能回写 `RunTrace` 和必要共享 memory

### 7.4 表面级 session / memory 边界

目标：

- 不同表面共享长期 memory，但短期 thread 上下文隔离。

通过条件：

- Dashboard 与 Feishu 共享 `agent_private / department_shared / company_shared`
- 不同 Feishu 私聊用户彼此隔离，不共享 DM session
- Dashboard tab、Feishu 私聊、Feishu 群聊使用不同 thread 上下文

### 7.5 统一线程模型

目标：

- `Web Dashboard` 与 `Feishu` 不是两套独立状态机，而是共享同一套系统线程与路由语义。

通过条件：

- 存在统一的 `ConversationThread` 模型
- Feishu 事件能映射到系统内部线程
- Dashboard 与 Feishu 的 run、trace、checkpoint 可在同一系统语义下关联

### 7.6 OpenClaw native agent plane

目标：

- 核心席位必须拥有正式 `OpenClaw` 原生 agent，而不是只靠项目内直接 provider 调用。

通过条件：

- 每个核心席位都存在：
  `OpenClawAgentBinding`
  `OpenClawWorkspaceBundle`
  `OpenClawSessionBinding`
- OpenClaw Control UI 与 Dashboard 都只显示同样的 7 个核心 agent
- workspace 至少包含：
  `AGENTS.md`
  `SOUL.md`
  `IDENTITY.md`
  `BOOTSTRAP.md`
  `SKILLS.md`
  `TOOLS.md`
  `USER.md`
  `HEARTBEAT.md`

### 7.7 Dashboard `Agents` 模块

目标：

- Dashboard 必须提供单个 agent 的完整管理视图，而不是只停留在简化版席位卡片。

通过条件：

- 存在一级页面 `Agents`
- 能查看：
  `Overview`
  `Identity`
  `Native Skills`
  `Memory`
  `Runtime`
  `Config`
- 能看到 OpenClaw native skill discovery 与 validation 状态

### 7.8 Visible agent-to-agent

目标：

- agent-to-agent 沟通允许发生，但不能对 CEO 不可见。

通过条件：

- agent-to-agent 轮次出现在 CEO 所在 room，或被完整镜像到 Dashboard / `RunTrace`
- 默认不允许隐藏的 private inter-agent DM 作为主协作路径

### 7.9 repeat recall

目标：

- 同一 bot 默认只主动发言一次，但在用户或 peer 明确召回时允许返场。

通过条件：

- `最后还是你来收口一下` 这类表达可被命中
- `repeat_invocation_source` 可区分：
  `user_explicit`
  `user_semantic`
  `peer_visible_name`
- 未被明确召回的 bot 不重复发言

## 8. 开发环境验收

### 8.1 本机 Docker 开发基线

目标：

- 所有开发活动都以本机 Docker 容器为唯一正式开发环境。

通过条件：

- 存在一个主开发容器承载代码执行
- 所有依赖安装、启动命令、测试和调试都在容器中完成
- Host 不要求预装项目运行所需的 Python/Node/数据库环境

### 8.2 依赖服务容器化

目标：

- V1 必需基础设施不依赖 Host 本机服务。

通过条件：

- `Postgres`
- `Redis`
- `Vector DB`
- `Object Store`
  都通过本机 Docker 栈提供
- 本地联调不依赖手动启动 Host 原生服务

### 8.3 容器一致性

目标：

- 开发、调试、测试在同一环境语义下进行。

通过条件：

- 开发文档明确规定容器是唯一正式开发环境
- 不存在“Host 本地可以运行、容器内反而不行”的默认工作流
- 关键命令和依赖路径以容器环境为准

## 9. 治理与审计验收

### 9.1 ApprovalGate

目标：

- 高影响动作不只停留在文档概念层，而是具备最小可用治理链。

通过条件：

- `review_decision`
- `rollback`
- `memory promotion`
  都能挂到统一审批入口
- 审批结果能进入 `RunTrace` 和相关 artifact

### 9.2 审计可追踪性

目标：

- 关键决策、驳回和恢复动作都具备可追溯记录。

通过条件：

- 存在 decision / approval / rollback 的可查询轨迹
- Dashboard 能查看高影响动作的结果与证据引用

### 9.3 Feishu 消息卡审批

目标：

- Feishu 卡审批必须成为可见、可追踪、可核对的正式治理入口。

通过条件：

- `approved / rejected` 卡片点击都能回写正式审批链
- Dashboard、checkpoint、approval gate 状态一致
- 至少存在一次真实 live 点击通过的证据

## 10. 公开库边界验收

### 10.1 `agency-agents`

通过条件：

- 只作为 `PersonaPack` 和上游资产来源出现
- 没有被写成 scheduler 或 runtime

### 10.2 `mem0`

通过条件：

- 即使后续接入，也只承担 `episodic / semantic recall`
- 没有被写成完整 `Memory Fabric`
- 不负责 checkpoint / approval / promotion

### 10.3 `LangGraph`

通过条件：

- 只承担 company workflow runtime/orchestration
- 没有被写成 `Chief of Staff` 或公司组织模型本身

### 10.4 `OpenClaw`

通过条件：

- 只承担 `agent plane`
- 没有被写成 `Chief of Staff`、`VirtualDepartment` 或 `Memory Fabric`
- Dashboard / Feishu 的消息执行默认通过 OpenClaw agent runtime，而不是项目内直接模型调用

### 10.5 `Paperclip`

通过条件：

- 只作为外部 benchmark 或能力参考源出现
- 没有被写成当前主栈依赖
- 没有冲掉：
  `human CEO`
  `Chief of Staff`
  `Web Dashboard + Feishu`
  这些现有主叙事

## 11. 一致性验收

开发方案文档与上游设计文档必须保持一致：

- V1 主栈仍是：
  `OpenClaw + LangGraph + agency-agents + current Memory Fabric`
- V1 系统形态仍是：
  `Python 单体后端 + 简单控制台`
- 开发环境仍固定为：
  `本机 Docker 容器栈`
- V1 仍只激活核心 7 部门
- `formal_project` 仍是默认正式项目流
- 轻量流程仍要求 `sync-back`
- `Web Dashboard` 与 `Feishu` 仍共享一套系统状态，而不是两套独立实现
- `V1.5 = Feishu + OpenClaw + native skills + Dashboard Agents`
- `V1.8 = Pulse / Trigger / Relationship / controlled self-evolution / visible event stream`
- `V2 = Slack`
- `Company Plaza` 不进入当前路线
- `GoalLineage`
  `BudgetPolicy`
  `TriggerPolicy`
  `WorkTicket`
  的文档定义前后一致

## 12. V1 最终通过标准

只有以下条件全部满足，V1 才视为通过：

- 核心验收场景全部通过
- Goal Lineage / Budget / Trigger / Ticket 验收通过
- 开发环境验收通过
- 表面交互验收通过
- 治理与审计验收通过
- 核心 7 部门席位都可激活
- `Product Build Loop` 和 `Discovery / Synthesis Loop` 都通过正式验收
- memory scope、quality gate、checkpoint/rollback 和公开库边界都通过检查
- 文档、实现和控制台体现的是同一套系统语义，没有层级混乱
