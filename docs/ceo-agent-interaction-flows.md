# CEO 与虚拟员工交互流程

本文定义 `one-person-company` 中 CEO 与虚拟员工的正式交互模型。目标不是替代主方案里的组织图、recipe 和 memory 设计，而是补齐“正式项目流程”之外的轻量局部流程，让系统更接近真实公司里的日常协作方式。

## 1. 设计原则

- “默认正式项目流”只是默认路径，不是所有 CEO 交互的唯一入口。
- 轻量流程不是绕过治理，而是降低参与范围和流程负担，同时保留 `sync-back`、最小 memory 回写和可升级能力。
- `Chief of Staff` 仍是默认中枢，但不是每次都要拉起完整部门链。
- 所有交互都必须最终落回：
  `Executive Office`
  `MemoryRecord`
  `RunTrace`
  在需要时再落回 `TaskGraph` 和 `Checkpoint`。

## 2. Interaction Mode

| mode | 中文含义 | 默认参与范围 | 默认目标 |
| --- | --- | --- | --- |
| `idea_capture` | 想法记录 | `executive_only` | 先记住，不急着执行 |
| `quick_consult` | 快速咨询 | `single_department` | 得到意见、判断或建议 |
| `department_task` | 单部门任务 | `single_department` | 完成一个小而明确的动作 |
| `formal_project` | 正式项目流 | `full_project_chain` | 完成交付物和质量门闭环 |
| `review_decision` | 审核与决策 | `multi_department` | 对已有产物做复核和拍板 |
| `override_recovery` | 改向与恢复 | `multi_department` | 停止、改向、回滚、冻结 |
| `escalation` | 升级处理 | `multi_department` | 处理冲突、风险、连续失败 |

## 3. 七类交互流程

### 3.1 Idea Capture Loop

```text
CEO
  -> Chief of Staff
  -> IdeaBrief
  -> CEO intent memory
```

- 适用于：
  想法、灵感、方向、疑问、未来候选项目。
- 默认输出：
  `IdeaBrief`
- 默认行为：
  不建完整 `TaskGraph`
  不激活完整部门链
  只写 `CEO intent memory` 和必要的 `company_shared semantic/episodic`
- 升级条件：
  CEO 明确要求推进；
  Chief of Staff 判断需要部门验证；
  该想法进入周期性评审或版本规划。

### 3.2 Quick Consult Loop

```text
CEO
  -> one department
  -> ConsultNote
  -> Chief of Staff sync-back
```

- 适用于：
  “你怎么看”“帮我分析下”“给我几个建议”。
- 默认输出：
  `ConsultNote`
- 默认行为：
  不走完整项目链
  不强制 Quality
  不建完整 checkpoint
  但必须回写 Executive Office 和记最小 `MemoryRecord`

### 3.3 Department Task Loop

```text
CEO
  -> one department
  -> TaskResult
  -> sync-back
  -> optional lightweight checkpoint
```

- 适用于：
  CEO 给单部门一个边界清晰的小任务。
- 默认输出：
  `TaskResult`
- 默认行为：
  使用最小 `TaskGraph` 或单节点任务卡
  只激活一个部门
  只在关键节点建轻量 checkpoint
- 升级条件：
  出现跨部门依赖；
  对外交付；
  风险升高；
  需要 Quality 或 Trust 介入。

### 3.4 Formal Project Flow

```text
CEO
  -> Chief of Staff
  -> Product / PM / Design / Engineering / Quality
  -> synthesis
  -> CEO review
```

- 适用于：
  明确 deliverable、跨部门交付、需要质量门和 checkpoint 的正式项目。
- 默认输出：
  项目级 deliverable、`EvidenceArtifact`、`Checkpoint`、`RunTrace`
- 默认行为：
  使用完整 `TaskGraph + Checkpoint + Quality Gate + Executive synthesis`

### 3.5 Review & Decision Loop

```text
CEO
  -> Chief of Staff
  -> optional Product / Quality / Trust
  -> DecisionRecord
```

- 适用于：
  CEO reviewing 已有方案、结果、证据、是否继续推进。
- 默认输出：
  `DecisionRecord`
- 默认行为：
  强制读取相关 `artifacts / evidence / checkpoint refs`
  写入 `board-style evidence package`
  必要时写 `company_shared` 和新的 `Checkpoint`

### 3.6 Override & Recovery Loop

```text
CEO
  -> Chief of Staff
  -> related departments
  -> OverrideDecision
  -> checkpoint / rollback / supersede
```

- 适用于：
  “停掉”“改方向”“不要这条了”“回到上一个版本”。
- 默认输出：
  `OverrideDecision`
- 默认行为：
  必须生成或恢复 checkpoint
  更新 `TaskGraph status`
  标记 superseded memory / artifacts

### 3.7 Escalation Loop

```text
Chief of Staff
  -> related departments
  -> EscalationSummary
  -> optional CEO decision
```

- 适用于：
  冲突、高风险、连续失败、权限越界、结论不一致。
- 默认输出：
  `EscalationSummary`
- 默认行为：
  先汇总冲突点、风险、备选动作；
  默认不直接推进执行；
  再决定回到哪一种主流程。

## 4. 默认识别规则

| CEO 表达信号 | 默认 mode |
| --- | --- |
| “我有个想法 / 先记一下 / 以后再说” | `idea_capture` |
| “你怎么看 / 帮我分析 / 给点建议” | `quick_consult` |
| “让工程/设计/产品帮我做这个小任务” | `department_task` |
| “做一个 MVP / 启动这个项目 / 出完整方案” | `formal_project` |
| “这个能不能上线 / 你给我过一下 / 帮我拍板前复核” | `review_decision` |
| “停掉 / 改方向 / 回滚 / 不按原计划做” | `override_recovery` |
| “这有风险 / 有冲突 / 搞不定 / 需要升级处理” | `escalation` |

## 5. 与 TaskGraph / Memory / Checkpoint 的关系

| mode | TaskGraph | memory 写入 | checkpoint |
| --- | --- | --- | --- |
| `idea_capture` | 默认不建 | `CEO intent memory` + 必要 `company_shared` | 默认无 |
| `quick_consult` | 默认不建完整图 | `run + agent_private + optional department_shared summary` | 默认无 |
| `department_task` | 最小 `TaskGraph` | `department_shared` + 必要 `company_shared summary` | 轻量 |
| `formal_project` | 完整 `TaskGraph` | 全量正式回写 | 正式 |
| `review_decision` | 读取现有图和证据 | `DecisionRecord` + `company_shared` | 必要时新建 |
| `override_recovery` | 更新或恢复图 | supersede + rollback refs | 强制 |
| `escalation` | 可挂靠现有图，也可独立升级单 | 风险摘要、冲突结论、建议动作 | 视结果而定 |

## 6. 默认升级原则

- 轻量流程一旦出现跨部门依赖，默认升级至少为 `multi_department`。
- 一旦出现外部发布、高风险动作或合规问题，默认升级到 `review_decision` 或 `escalation`。
- 一旦需要正式交付、明确交付物和质量门，默认升级为 `formal_project`。

## 7. System-Initiated Operational Flows

CEO 交互流并不是系统的唯一触发源。为了让公司进入更接近真实运营的状态，V1 还保留三类系统触发式流程，但它们都必须回到 `Executive Office` 统一调度。

| trigger type | 中文含义 | 默认 owner | 进入方式 |
| --- | --- | --- | --- |
| `manual` | CEO 或 operator 手动触发 | `Chief of Staff` | 直接进入现有 7 类交互流之一 |
| `event_based` | 来自任务状态、消息、审批、失败等事件的触发 | `Chief of Staff` | 先形成 `WorkTicket` 更新，再决定是否升级 |
| `scheduled_heartbeat` | 周期性唤醒 | `Chief of Staff` 或部门 owner | 先生成 heartbeat summary，再决定是否派生任务 |

默认规则：

- `event_based` 和 `scheduled_heartbeat` 不是新的 CEO 交互 mode，而是进入现有流程的触发源。
- heartbeat 只能触发预定义 recurring work，如：
  `trend scan`
  `delivery follow-up`
  `budget review`
  `monthly checkpoint prep`
- 所有系统触发都必须生成最小 `RunTrace`，并回写到：
  `Chief of Staff`
  `WorkTicket`
  必要时的 `TaskGraph`
- 系统触发不能绕过 `ApprovalGate`、`Memory Fabric` 或部门激活策略。

## 8. Visible Agent-to-Agent Communication

### 8.1 正式约束

当前方案允许 agent-to-agent 沟通，但它不是“隐藏的 agent 社会”，而是必须满足 CEO 可见与可审计的协作。

固定规则：

- agent-to-agent 只能在 CEO 所在的可见 room 中发生；
- 或者必须被完整镜像到 Dashboard / `RunTrace`；
- 不允许默认创建 CEO 不可见的 agent 私有 DM 作为主协作路径。

### 8.2 CEO-visible room constraint

对 `Feishu`、后续 `Slack` 和 Dashboard 来说，默认 room policy 固定为：

- `require_ceo_present = false`
- `mirror_to_dashboard = true`
- `mirror_to_visible_room = true`
- `allow_private_agent_dm = false`

这意味着：

- CEO 私聊某个 agent 时，只是 `CEO -> 单 agent`；
- CEO 可以不在 room 中，但 transcript 必须实时镜像到 Dashboard 和一个 CEO 可见的房间；
- 群聊中如果某个 agent 需要另一个 agent 继续补充，后续交流必须继续出现在同一可见群里；
- 如果系统内部为了执行效率需要短暂的 inter-agent coordination，也必须把关键 transcript、决策理由和结果镜像回 `ConversationThread / RunTrace`。

### 8.3 与现有 7 类交互模式的关系

| 场景 | 是否允许 agent-to-agent | 可见性要求 |
| --- | --- | --- |
| `idea_capture` | 默认不需要 | 不创建额外 agent 对话 |
| `quick_consult` | 条件允许 | 必须对 CEO 可见或镜像回 trace |
| `department_task` | 条件允许 | 出现跨部门协作时升级并保持可见 |
| `formal_project` | 允许 | 通过项目 room 或 Dashboard trace 暴露 |
| `review_decision` | 允许 | 证据与结论必须可见 |
| `override_recovery` | 允许 | 恢复和 supersede 必须可审计 |
| `escalation` | 允许 | 冲突与风险必须对 CEO 可见 |
