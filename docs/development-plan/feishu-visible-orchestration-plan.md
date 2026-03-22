# Feishu Visible Orchestration Plan

本文是 `V1 Feishu` 沟通层的 source of truth。目标不是把 Feishu 当成系统真相源，而是定义如何在 `OpenClaw agent plane + current company control plane` 的组合下，满足 CEO 可见的单 agent、多 agent、agent-to-agent 协作。

## 1. 结论

V1 固定方案为：

- `Feishu = 对外沟通表面`
- `OpenClaw = agent runtime`
- 当前项目 = `mention dispatch + visible-room fan-out + transcript mirror + governance`

这意味着：

- 私聊某个 bot，只该 bot 对应的 agent 回复
- 群里 @ 一个 bot，只该 agent 回复
- 群里 @ 多个 bot，这些 agent 都回复
- agent-to-agent 允许发生，但必须 CEO 可见，或被完整镜像到 Dashboard / `RunTrace`

## 2. 为什么不直接依赖 shared groups

当前 V1 不把 OpenClaw `shared groups` 当成 Feishu 主方案，原因是：

- 你需要的是精确 mention 语义，而不是“群里默认只有一个 agent 接管”
- 你需要的是可见 agent-to-agent 协作，而不是隐藏的 bot 私聊
- 你需要把所有往返都镜像回 `ConversationThread / WorkTicket / RunTrace`

因此 Feishu V1 必须保留项目内 `visible-room fan-out`。

## 3. 核心对象

| 对象 | 作用 |
| --- | --- |
| `FeishuMentionDispatchResult` | 记录一次 message 的目标 agent 集合 |
| `VisibleRoomPolicy` | 约束群聊发言、可见性和 transcript 镜像 |
| `OpenClawSessionBinding` | 将 `agentId + surface + channel` 绑定到 sessionKey |
| `VisibleRoomOrchestrator` | 管理多 agent 回复与可见 agent-to-agent 轮次 |

## 4. mention dispatch 规则

### 4.1 私聊

- 输入：`feishu_dm + app_id + sender`
- 结果：只路由到该 bot 绑定的 `openclaw_agent_id`
- session key：
  `agent:<agentId>:feishu:dm:<senderId>`

### 4.2 群聊 @ 单 bot

- 输入：`feishu_group + mentions = 1`
- 结果：只该 agent 回复
- 其他 bot 不参与

### 4.3 群聊 @ 多 bot

- 输入：`feishu_group + mentions > 1`
- 结果：被 @ 的 agent 并发执行并各自回复
- 去重维度必须是：
  `app_id + message_id`

## 5. Visible Room Policy

默认策略固定为：

- `require_ceo_present = false`
- `mirror_to_dashboard = true`
- `mirror_to_visible_room = true`
- `allow_private_agent_dm = false`

这意味着：

- CEO 可以不在 room 中，但 transcript 必须实时镜像到 Dashboard 与一个 CEO 可见的房间
- agent 之间不能默认开不可见私聊
- 若 `Chief of Staff` 需要另一个 agent 回应，必须继续在同一可见 room 中发言
- 或者把完整 transcript 镜像回 room 与 Dashboard

## 6. OpenClaw Session Binding

### 6.1 DM session

```text
agent:<agentId>:feishu:dm:<senderId>
```

### 6.2 Group session

```text
agent:<agentId>:feishu:group:<chatId>
```

固定规则：

- 每个 agent 在每个 Feishu group 内拥有独立 session
- 每个 DM 也拥有独立 session
- session 不替代外层 `ConversationThread`

## 7. Fan-out 与 transcript mirror

每次 Feishu inbound/outbound 都必须挂接到：

- `ConversationThread`
- `WorkTicket`
- `RunTrace`
- 必要时的 `MemoryRecord`

群内多 agent 协作还必须记录：

- dispatch targets
- visible room id
- outbound turn order
- agent-to-agent exchange refs

## 8. 验收

- 私聊某个 bot，只该 bot 回复
- 群里 @ 一个 bot，只该 bot 回复
- 群里 @ 多个 bot，这些 bot 都回复
- agent-to-agent 沟通始终对 CEO 可见或被镜像
- 所有往返都能回写 `ConversationThread / WorkTicket / RunTrace`

## 9. 与 V2 Slack 的关系

Feishu 是 V1 主沟通平台。V2 新增 Slack 时，复用的不是 Feishu 路由代码本身，而是以下契约：

- `ConversationThread`
- `WorkTicket`
- `RunTrace`
- `VisibleRoomPolicy`
- `OpenClawSessionBinding`

Slack 的目标是降低群协作复杂度，而不是替代 company control plane。
