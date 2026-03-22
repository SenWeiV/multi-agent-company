# 前端 Dashboard 与飞书交互方案

本文定义 `one-person-company` 在开发视角下的前端交互层方案。范围只包括交互设计与开发规划文档，不包括任何前端、飞书、OpenClaw 或后端实现。Feishu 的 V1 细化规则以 [feishu-visible-orchestration-plan.md](/Users/weisen/Documents/small-project/multi-agent-company/docs/development-plan/feishu-visible-orchestration-plan.md) 为 source of truth。

## 1. 设计目标

- 为现有 `Operator Console` 提供正式的前端交互定义，升级为 `Web Dashboard + Feishu` 双表面模型。
- 让 CEO 能通过两种入口与虚拟员工交互：
  `Web Dashboard`
  `Feishu`
- 保持当前系统语义不变：
  `Chief of Staff`
  `VirtualDepartment`
  `TaskGraph`
  `Memory Fabric`
  `Checkpoint`
  `RunTrace`
  仍由当前方案统一定义。
- 让轻量流程和正式项目流都能在前端表面中找到稳定入口。
- 保持 V1 目标克制：
  `Web 优先`
  `Dashboard = 内部控制台`
  `Feishu = 按部门独立机器人`
  `群聊 = mention-based fan-out + visible-room orchestration`

## 2. 双表面模型

### 2.1 定义

- `Web Dashboard`
  是系统的主控制面，负责完整沟通、管理、观察和治理。
- `Feishu`
  是系统的协作与会话表面，负责私聊、群聊、轻量任务推进和会议式互动。

### 2.2 固定分工

| 表面 | 默认职责 | 不承担职责 |
| --- | --- | --- |
| `Web Dashboard` | 全量沟通、任务观察、agent 管理、memory 管理、checkpoint、审批与回滚 | 不作为独立运行时或第二套编排器 |
| `Feishu` | 私聊某个部门、在群里和多个部门沟通、接收提醒和轻量卡片 | 不作为配置、memory、审批的 source of truth |

### 2.3 与当前架构的挂接方式

两种表面共用同一套底层系统：

```text
Conversation Surface
  -> Executive Office
  -> Department activation
  -> WorkflowRecipe
  -> TaskGraph
  -> Memory Fabric
  -> Checkpoint / RunTrace
```

这意味着：

- Dashboard 和 Feishu 不是两套 agent 系统。
- 二者共享长期 memory 和组织模型。
- 二者只是在入口、线程、显示方式和互动节奏上不同。

## 3. Web Dashboard 信息架构

V1 中，现有 `Operator Console` 正式扩展为 `Web Dashboard`。它仍然是内部控制台，而不是完整产品后台。

### 3.1 八个主区

| 主区 | 作用 |
| --- | --- |
| `CEO Inbox` | CEO 的主对话入口，支持所有 `InteractionMode` |
| `Runs / TaskGraph` | 查看当前 run、执行状态、任务图、依赖和升级路径 |
| `Departments` | 查看部门席位、激活状态、上游 persona 绑定与当前负载 |
| `Agents` | 查看单个 agent 的 identity、native skills、memory、runtime、config 与 OpenClaw 对齐状态 |
| `Memory Explorer` | 查看 `agent_private / department_shared / company_shared` 摘要、命名空间与 recall 结果 |
| `Checkpoints & Approvals` | 查看 checkpoint、DecisionRecord、rollback、approval 状态 |
| `Feishu Channels & Bindings` | 管理飞书机器人、群组绑定、默认路由、房间策略 |
| `Audit / Observability` | 查看 RunTrace、事件日志、升级处理、质量证据 |

`Agents` 页面固定分为六个视图：

- `Overview`
- `Identity`
- `Native Skills`
- `Memory`
- `Runtime`
- `Config`

### 3.2 Dashboard 必须覆盖的交互

- `idea_capture`
- `quick_consult`
- `department_task`
- `formal_project`
- `review_decision`
- `override_recovery`
- `escalation`

V1 主打前四类，后三类以最小可用控制面支持。

### 3.3 Dashboard 是唯一高权限入口

V1 中以下动作只允许在 Dashboard 完成：

- 管理部门席位与上游 persona 绑定
- 管理 `MemoryNamespace`
- 管理 checkpoint 与 rollback
- 管理 Feishu channel binding 与 room policy
- 执行高影响 approval / recovery / promotion

## 4. Feishu 机器人与房间模型

### 4.1 部门机器人模型

V1 采用“按部门独立机器人”的外部映射方式。核心 7 部门各有一个飞书机器人：

- `Chief of Staff bot`
- `Product bot`
- `Research bot`
- `PM bot`
- `Design bot`
- `Engineering bot`
- `Quality bot`

这些机器人只是 `VirtualEmployee` 的外部会话表面，不是新的 agent 类型。

### 4.2 房间模型

V1 固定三类 Feishu 会话空间：

| 类型 | 作用 | 默认参与者 |
| --- | --- | --- |
| `部门机器人私聊` | CEO 与单个部门席位单聊 | `CEO + 1 bot` |
| `Executive Room` | CEO 与 `Chief of Staff` 的管理型群聊或协作室 | `CEO + Chief of Staff bot + optional observers` |
| `Project Room / Review Room` | 多部门围绕一个项目或评审进行协作 | `Chief of Staff bot + relevant department bots + CEO(optional)` |

固定补充规则：

- `Project Room / Review Room` 中 CEO 可以不在场；
- 但所有 transcript 必须实时镜像到 Dashboard 与一个 CEO 可见的房间；
- 因此 `CEO optional` 只表示“无需常驻在会话内”，不表示“允许 CEO 不可见”。

### 4.3 私聊策略

- `Chief of Staff bot`：
  默认接收 `idea_capture`、战略输入、总控问题、升级处理入口。
- `部门 bot`：
  默认接收 `quick_consult` 与 `department_task`。
- 高风险、跨部门或正式交付场景：
  应升级到 Dashboard 或由 CoS 接管。

### 4.4 群聊策略

V1 采用 `mention-based fan-out + visible-room orchestration`，而不是所有机器人同时自由发言。

默认规则：

- 群里只 `@` 一个 bot，只该 bot 对应 agent 回复。
- 群里同时 `@` 多个 bot，这些 bot 对应 agent 都回复。
- 未被 `@` 的 bot 不参与。
- `Chief of Staff bot` 仍可主持、汇总、分派和点名，但不再是唯一公开发言入口。
- 群聊中默认不允许无约束的隐藏 bot-to-bot 私聊；agent-to-agent 必须在 CEO 可见 room 中发生，或被完整镜像到 Dashboard / `RunTrace`。

### 4.5 OpenClaw / Feishu 事实边界

截至 2026-03-14，可直接复用的公开能力包括：

- OpenClaw 已支持 `Feishu bot` channel、私聊和群组、channel routing、session isolation。
- OpenClaw 的 `shared groups / broadcast groups` 不能直接覆盖当前项目要求的单提及、多提及、可见 agent-to-agent 全套语义。

因此 V1 的结论固定为：

- 飞书群聊的多 agent 协作必须由当前项目自定义为 `visible-room fan-out`。
- OpenClaw 承接 agent runtime，不直接承接 Feishu 群里的全部多 agent 协作规则。
- 当前项目负责：
  `FeishuMentionDispatch`
  `VisibleRoomPolicy`
  `VisibleRoomOrchestrator`
  `ConversationThread / WorkTicket / RunTrace mirror`

参考资料：

- [OpenClaw Feishu](https://docs.openclaw.ai/channels/feishu)
- [OpenClaw Channel Routing](https://docs.openclaw.ai/channels/channel-routing)
- [OpenClaw Session Management](https://docs.openclaw.ai/concepts/session)
- [OpenClaw Groups](https://docs.openclaw.ai/channels/groups)
- [OpenClaw Broadcast Groups](https://docs.openclaw.ai/channels/broadcast-groups)
- [Feishu IM Create Message](https://open.larkoffice.com/document/server-docs/im-v1/message/create)
- [Feishu Message Cards](https://open.feishu.cn/document/common-capabilities/message-card/getting-started/send-message-cards-with-a-custom-bot)

## 5. 交互模式映射

| InteractionMode | Dashboard | Feishu 私聊 | Feishu 群聊 | 默认说明 |
| --- | --- | --- | --- | --- |
| `idea_capture` | 主入口 | `Chief of Staff bot` 默认支持 | 不推荐 | 先记想法，不拉全员 |
| `quick_consult` | 支持 | 适合 | 支持 | 单部门问答最适合私聊，群里 @ 某 bot 时只由该 bot 回复 |
| `department_task` | 支持 | 适合 | 支持 | 小任务默认单部门处理；群里 @ 多 bot 时可形成可见协作 |
| `formal_project` | 主入口 | 不建议直接发起完整执行 | 可用于项目协作室 | 正式项目仍以 Dashboard 为主，群聊作为 visible room |
| `review_decision` | 主入口 | 可接收结果通知 | 适合 Review Room | 正式拍板回到 Dashboard |
| `override_recovery` | 主入口 | 不建议 | 条件支持 | 高影响动作回到 Dashboard，群聊只用于公开同步 |
| `escalation` | 主入口 | 可触发 | 适合 | 群聊用于冲突显化，处理仍受 visible-room policy 约束 |

固定规则：

- `formal_project` 是 Dashboard 的默认主入口。
- `quick_consult` 和 `department_task` 是 Feishu DM 的默认主入口。
- `review_decision / override_recovery / escalation` 可以在 Feishu 发起，但不应在 Feishu 完成全部治理动作。

## 6. Memory / Session / Thread 边界

### 6.1 核心模型

| 对象 | 作用 |
| --- | --- |
| `ConversationSurface` | `dashboard`、`feishu_dm`、`feishu_group` |
| `ConversationThread` | 某个表面上的具体会话线程 |
| `BotSeatBinding` | 部门席位与飞书机器人的绑定 |
| `ChannelBinding` | 会话表面与默认路由策略 |
| `RoomPolicy` | 群聊发言规则与主持策略 |

### 6.2 长期 memory 共享

两种表面共享同一套长期 memory：

- `agent_private`
- `department_shared`
- `company_shared`

这意味着：

- CEO 在 Dashboard 中形成的公司事实，应可被 Feishu 侧同席位检索。
- Feishu 中沉淀的有效交接与摘要，也必须能回写到 Dashboard 可见的长期 memory。

### 6.3 表面级会话隔离

两种表面不共享短期 thread 上下文。V1 固定为：

- Dashboard 的每个对话 tab 对应一个 `ConversationThread`
- Feishu 私聊按 `agent + sender + chat` 隔离
- Feishu 群聊按 `group chat id` 隔离
- 不允许不同人的 Feishu 私聊共享 DM session

### 6.4 共享与隔离的边界

| 类型 | 共享/隔离 |
| --- | --- |
| 长期 memory | 共享 |
| thread 上下文 | 隔离 |
| RunTrace | 统一系统内共享，可按表面过滤 |
| checkpoint | 统一系统内共享，由 Dashboard 管理 |
| approval / rollback / promotion | 统一系统内共享，但高影响操作默认回到 Dashboard |

## 7. V1 / V1.5 / V1.8 / V2 路线

### V1

- Web 控制台为主表面
- Feishu 核心 7 机器人
- Feishu 采用 `mention-based fan-out + visible-room orchestration`
- Dashboard 承担所有高权限管理动作

### V1.5

- 增加消息卡审批
- 增加更多房间模板：
  `Launch Room`
  `Ops Room`
  `Support Room`
- 新增 `Agents` 一级页面
- 固化 core-7 与 OpenClaw 的单一 agent 视图
- 补强 visible-room transcript、turn-taking、repeat recall 和 bot/channel 管理面

### V1.8

- 引入 `Pulse / Trigger Engine`
- 引入 `Relationship Graph`
- 引入 `Skill Creator + Eval Loop`
- 引入 `CEO Visible Event Stream`
- 不引入 `Company Plaza`

### V2

- 新增 `Slack`
- 复用同一套 `ConversationThread / WorkTicket / RunTrace / Memory`
- 让 Slack 成为更简单稳定的企业协作通道
- Feishu 保留为主办公环境下的沟通入口

## 8. 风险与边界

- 不能把 Dashboard 做成第二套独立 orchestrator。
- 不能把 Feishu 当作配置、memory 或审批的 source of truth。
- 不能把 OpenClaw `shared groups / Broadcast Groups` 误写成 Feishu 已具备的多 agent 群聊能力。
- 不能让群聊中的多个部门 bot 自由循环对话，导致噪音和上下文失控。
- 不能允许 CEO 不可见的 agent-to-agent 私聊成为默认协作路径。
- V1 不追求“所有表面都功能对等”，而是追求“Dashboard 完整、Feishu 好用且边界清楚”。
