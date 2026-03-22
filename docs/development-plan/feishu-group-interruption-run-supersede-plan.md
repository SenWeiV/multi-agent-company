# Feishu Group Interruption And Run Supersede Plan

本文定义 Feishu 群聊中“用户中途插话”时的正式处理方案。目标不是引入新的 `group session` 概念，而是在现有 `ConversationThread + Run + VisibleRoomOrchestrator + OpenClaw semantic routing` 之上，补齐可中断的群聊协作语义。

本文范围只包括行为定义、状态模型、调度规则、验收标准和实现边界，不直接修改任何代码。

## 1. 已确认的产品决策

- `20` 轮限制固定为 `run` 级，而不是群聊长期累计预算。
- 群聊中用户每发一条新消息，都会创建一个新的 `Run`。
- 如果旧 `Run` 还在执行，可先不做真正的模型取消；V1 只要求：
  旧 `Run` 被标记为 `superseded`，其晚到结果即使生成成功，也不得再发送到 Feishu。
- 用户中途插话后，调度器必须基于新的用户语义，重新选择需要回复的 bot 集合，而不是机械沿用旧的 pending handoff。
- 如果用户插话点名了某个 bot，或者语义上明确涉及某个 bot 的责任、纠错或继续接棒，该 bot 应被纳入新的调度目标。
- 当前阶段不新增独立的 `group session` 业务对象。

## 2. 问题定义

当前群聊协作更接近“单条 inbound message 触发单条链式执行”。这会导致两个问题：

- 用户在 bot 接棒过程中插话时，系统缺少正式的“旧链路失效、新链路接管”语义。
- 接棒状态主要依赖 transcript 和模型临时理解，缺少显式的 `pending_handoff` 与 `last_committed_state`，因此容易在纠错、继续接棒、重复召回这类场景中漂移。

以“数7”为例：

- `quality-lead` 说了“继续报8”
- 用户中途问“为什么让 chief-of-staff 继续报8？”
- 这时系统不能继续按旧链路机械发送 chief-of-staff 已经算好的回复
- 而应该把这句用户插话纳入同一话题上下文，重新判断：
  - 谁需要先解释
  - 谁需要继续接棒
  - 旧 pending handoff 是否仍然有效

## 3. 目标模型

### 3.1 Thread

`ConversationThread` 表示群聊中同一话题的连续上下文。

在“数7”场景中：

- 用户发“开始玩数7”会创建 `Thread T1`
- bot 接力期间，用户再发“等等，quality lead 刚才为什么让 chief-of-staff 继续报8？”时，仍应复用 `T1`
- 只有用户显式要求新会话，或命中独立的新话题边界时，才新建 thread

### 3.2 Run

`Run` 表示同一 thread 下，由某一条用户输入触发的一次执行切片。

固定规则：

- 同一 thread 内，每条新的用户输入创建一个新的 `Run`
- `Run` 具有独立的 `20` 轮 bot 可见发言预算
- 新 `Run` 可以 `supersede` 旧 `Run`
- 旧 `Run` 被 supersede 后，不再拥有可见发送资格

### 3.3 Working State

本问题首先是 `working / run` 状态问题，而不是长期 memory 不够。

V1 需要补齐的核心状态为：

| 字段 | 作用 |
| --- | --- |
| `thread_id` | 绑定同一群聊话题上下文 |
| `active_run_id` | 当前 thread 正在生效的 run |
| `run.status` | `active / completed / superseded / failed` |
| `run.superseded_by_run_id` | 标记被哪个新 run 接管 |
| `run.turn_budget_limit` | 固定为 `20` |
| `run.visible_turn_count` | 当前 run 已消耗的 bot turn 数 |
| `last_committed_state` | 当前话题的已确认业务状态 |
| `pending_handoff` | 当前待执行但尚未兑现的接棒信息 |
| `dispatch_targets` | 当前 run 一次性选出的需要回复的 bot 集合 |
| `delivery_guard_epoch` | 防止 superseded run 的晚到结果继续发送 |

## 4. 调度器定义

本文中的“调度器”不是一个单独的新服务名，而是现有两层能力的组合：

- `Feishu visible-room orchestration`
  负责 dispatch、handoff、turn order、outbound delivery guard
- `OpenClaw semantic router`
  负责利用大模型推断语义目标和重复召回目标

因此，调度器是“规则路由 + LLM 语义推断 + visible-room 编排”的组合体。

### 4.1 调度器是否使用大模型

使用。

当前目标推断本来就是混合式：

- 显式 @ mention
- 文本中的 bot 名称或别名
- 语义 dispatch
- 语义 repeat recall

其中后两者已经依赖 OpenClaw 的推断能力。V1 新方案不改变这一点，而是把 LLM 推断放入“中断后重排”的正式语义里。

### 4.2 用户插话时的调度规则

当用户在 bot 接棒中途插话时，调度器必须执行以下顺序：

1. 找到当前群聊正在进行中的 thread
2. 判断该 thread 是否存在 `active run`
3. 若存在，则将其标记为 `superseded`
4. 创建新的 `Run`
5. 把新的用户消息加入同一 thread transcript
6. 基于以下输入重算 `dispatch_targets`

重算输入固定为：

- 最新用户插话
- thread 最近可见 transcript
- `pending_handoff`
- `last_committed_state`
- 本轮被明确点名的 bot
- 已知可参与 bot 白名单

### 4.3 目标 bot 选择规则

新的 `dispatch_targets` 按以下优先级选择：

1. 用户显式 @ 的 bot
2. 用户正文中明确点名的 bot
3. `pending_handoff` 中的 source bot
4. `pending_handoff` 中的 target bot
5. 由 LLM 语义推断出来、与本轮插话强相关的 bot

选择后需去重，并生成有序队列。

默认排序建议：

1. 被追问、被纠错、被要求解释的 bot 先说
2. 当前 baton owner 或待接棒 bot 后说
3. 其余语义相关 bot 再说

这样可以保证“先澄清，再恢复任务”。

## 5. Supersede 语义

V1 先不要求真正取消模型推理，只要求严格的发送闸门。

### 5.1 旧 Run 失效

当 `Run R2` supersede `Run R1` 后：

- `R1.status = superseded`
- `R1.superseded_by_run_id = R2`
- `thread.active_run_id = R2`

### 5.2 晚到结果处理

若 `R1` 中某个 bot 的回复在 supersede 之后才生成完成：

- 允许生成完成
- 允许记录到 observability / audit
- 但在实际发消息前，必须执行 delivery guard

delivery guard 规则：

- 若 `run_id != thread.active_run_id`，则该回复视为 stale result
- stale result 不得发送到 Feishu
- 记录 `stale_reply_dropped` 事件到 `RunTrace`

这就是 V1 所需的“暂停旧链路”的最小可用实现。

## 6. 数7场景模拟

### 6.1 原始流程

- 用户：`开始玩数7，从 chief-of-staff 开始`
- 创建 `Thread T1`
- 创建 `Run R1`
- bot 接力：
  - `chief-of-staff` 说 `1`
  - `product-lead` 说 `2`
  - `research-lead` 说 `3`
  - ...
  - `quality-lead` 说：`过。@chief-of-staff 到你了，继续报8`

此时系统中存在：

- `last_committed_state = { game: "count7", last_valid_number: 7, next_expected_number: 8 }`
- `pending_handoff = { from: "quality-lead", to: "chief-of-staff", instruction: "继续报8" }`

### 6.2 用户中途插话

用户发送：

`等等，quality lead 刚才为什么让 chief-of-staff 继续报8？`

系统处理：

1. 仍挂到 `Thread T1`
2. 新建 `Run R2`
3. 将 `R1` 标记为 `superseded`
4. 任何属于 `R1` 的晚到 bot 回复都不得再发出
5. 调度器读取：
   - 最新用户插话
   - `T1` transcript
   - `pending_handoff`
   - `last_committed_state`
6. 调度器选出新的 `dispatch_targets`

本例中推荐的选择结果为：

- `quality-lead`
- `chief-of-staff`

原因：

- `quality-lead` 是被用户追问的 bot，也是当前错误接棒链的 source
- `chief-of-staff` 是当前 baton owner，需要承接更正后的继续报数

### 6.3 新 Run 的理想回复序列

`R2` 内的理想可见回复顺序为：

1. `quality-lead`
   `抱歉，我刚才的接棒判断错了。当前应该由 chief-of-staff 继续报 8。我重新交给 chief-of-staff。`
2. `chief-of-staff`
   `刚才这一步已更正。现在继续报 8。@product-lead 到你了，继续报 9。`

若 `R1` 中 chief-of-staff 的旧结果晚到，例如：

`1。@product-lead 到你了，继续报2。`

则该结果必须被 delivery guard 丢弃，不得发送到群里。

## 7. last_committed_state 与 pending_handoff

### 7.1 last_committed_state

`last_committed_state` 表示当前 thread 中已经确认成立的业务状态。

在“数7”场景中，可最小化为：

```json
{
  "game": "count7",
  "last_valid_number": 7,
  "next_expected_number": 8
}
```

它的作用是：

- 给后续 bot 一个明确的状态锚点
- 避免仅靠 transcript 猜测“当前到底该说到几”
- 在用户插话后，为调度器和目标 bot 提供稳定上下文

### 7.2 pending_handoff

`pending_handoff` 表示一条已声明、但尚未兑现的接棒。

最小字段：

```json
{
  "source_agent": "quality-lead",
  "target_agent": "chief-of-staff",
  "instruction": "继续报8",
  "status": "active"
}
```

当用户插话 supersede 旧 run 时：

- 该 `pending_handoff` 不应直接执行
- 而应转为新 `Run` 的输入之一
- 由新调度器判断它是：
  - `confirmed`
  - `corrected`
  - `invalidated`

## 8. Memory 边界

本方案不把“中途插话纠偏”定义为长期 memory 能力。

固定边界：

- 实时纠偏、继续接棒、抑制旧结果发送：
  属于 `working / run` 和 thread 级状态
- 这次失误是否值得沉淀为经验：
  才属于 `episodic / agent_private / department_shared`

因此 V1 的优先顺序是：

1. 先补强 `thread + run + delivery guard + baton state`
2. 再考虑把失败经验蒸馏进长期 memory

## 9. 变更范围

### 9.1 本次纳入

- 群聊复用已有 thread 的正式语义
- 用户插话创建新 run
- 旧 run `superseded` 标记
- stale outbound drop
- `last_committed_state`
- `pending_handoff`
- 基于最新用户语义的一次性多 bot 重排

### 9.2 本次不纳入

- 真正的模型级取消
- 新建独立 `group session` 业务对象
- 将 `20` 轮预算提升到 thread 级
- 用长期 memory 直接驱动实时接棒

## 10. 建议的数据与事件字段

### 10.1 Thread

- `thread_id`
- `surface`
- `channel_id`
- `active_run_id`
- `last_committed_state`
- `pending_handoff`

### 10.2 Run

- `run_id`
- `thread_id`
- `status`
- `supersedes_run_id`
- `superseded_by_run_id`
- `visible_turn_budget_limit`
- `visible_turn_count`
- `dispatch_targets`

### 10.3 RunTrace events

- `run_superseded`
- `stale_reply_dropped`
- `interruption_dispatch_resolved`
- `pending_handoff_invalidated`
- `pending_handoff_corrected`
- `last_committed_state_updated`

## 11. 验收标准

- 群聊里 bot 接棒过程中，用户插话会创建新的 `Run`，而不是继续沿用旧 run。
- 新 run 复用同一个 thread，而不是切成新的上下文。
- 被 supersede 的旧 run，其晚到回复不会继续发到 Feishu。
- 调度器能基于用户插话、transcript、pending handoff 和当前状态，一次性选出应回复的 bot。
- “数7”场景中，用户追问 `quality-lead` 后，新的 run 能先让 `quality-lead` 纠错，再让 `chief-of-staff` 正确继续报 `8`。
- 每个新 run 的 bot 可见发言上限仍是 `20`。

## 12. 实施顺序建议

### P0

- 群聊 thread 复用
- 新 run supersede 旧 run
- stale outbound drop

### P1

- `pending_handoff`
- `last_committed_state`
- interruption-aware dispatch target resolution

### P2

- 更细的排序策略
- 更丰富的审计与回放视图
- 失败经验蒸馏到长期 memory

## 13. 与现有文档的关系

- Feishu 表面与 visible-room 的总规则，仍以 [Feishu Visible Orchestration Plan](./feishu-visible-orchestration-plan.md) 为准。
- `Web Dashboard + Feishu` 的双表面和会话边界，仍以 [前端 Dashboard 与飞书交互方案](./frontend-and-feishu-interaction-design.md) 为准。
- 实施层的模块、字段、事件与落地顺序，见 [Feishu Group Interruption Implementation Breakdown](./feishu-group-interruption-implementation-breakdown.md)。
- 本文是这两者之下的一个补充专题，专门解决“群聊中断、run supersede、接棒状态连续性”的实现语义。
