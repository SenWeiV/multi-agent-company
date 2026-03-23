# Feishu Group Interruption Implementation Breakdown

本文是 [Feishu Group Interruption And Run Supersede Plan](./feishu-group-interruption-run-supersede-plan.md) 的实施拆解稿。目标是把“群聊中用户中途插话 -> 新 run 接管 -> 旧 run 晚到结果不再发送 -> 调度器重排需要回复的 bot”这套语义，进一步拆成可执行的模块改造清单、字段变更表、事件目录和分阶段落地顺序。

本文仍然只定义开发方案，不直接修改任何代码。

## 1. 范围冻结

本实施稿固定采用以下前提：

- `20` 轮预算按 `run` 级计算。
- 群聊中用户每发一条新消息，都会生成一个新的 `Run`。
- V1 不要求真正取消正在进行的模型推理。
- V1 只要求：
  新 run 接管后，旧 run 被标记为 `superseded`，其晚到结果不得继续发送到 Feishu。
- 调度器需要结合新用户插话、当前 thread transcript、`pending_handoff`、`last_committed_state` 一次性选出需要回复的 bot。
- 本次不新增独立的 `group session` 业务对象。

## 2. 涉及模块

### 2.1 P0 必改模块

| 模块 | 现职责 | 本次改动 | 优先级 |
| --- | --- | --- | --- |
| `app/feishu/services.py` `FeishuSurfaceAdapterService` | 群聊 inbound 处理、dispatch、visible handoff、outbound 发送 | 新增 group thread 复用、旧 run supersede、delivery guard、用户插话后 dispatch 重算入口 | P0 |
| `app/conversation/models.py` `ConversationThread` | 表面线程模型 | 增加 thread 级 active run 与接棒状态字段 | P0 |
| `app/conversation/services.py` `ConversationService` | thread 查找、更新、session attach、visibility merge | 新增 active run 切换、thread state 更新方法 | P0 |
| `app/control_plane/models.py` `RunTrace` | 运行追踪模型 | 增加 supersede 与 interruption 相关字段 | P0 |
| `app/control_plane/services.py` `RunTraceService` | runtrace 创建与事件追加 | 新增 `mark_superseded`、可见 turn 计数与 interruption 状态更新 | P0 |
| `app/feishu/models.py` `FeishuOutboundMessageRecord` | outbound 审计记录 | 增加 stale drop / delivery guard 字段 | P0 |

### 2.2 P1 建议改模块

| 模块 | 现职责 | 本次改动 | 优先级 |
| --- | --- | --- | --- |
| `app/feishu/models.py` `FeishuInboundEventRecord` / `FeishuGroupDebugEventRecord` | inbound 审计与 group debug | 增加 supersede / interruption dispatch 观测字段 | P1 |
| `app/openclaw/models.py` `OpenClawCollaborationContext` / `OpenClawHandoffContext` | 传给模型的协作上下文 | 增加 `last_committed_state` / `pending_handoff` 摘要字段 | P1 |
| `app/openclaw/services.py` | 语义推断与回复生成 | 让 interruption run 的 source / handoff target 都看到新的状态锚点 | P1 |
| `app/api/routes/control_plane.py` | RunTrace / WorkTicket 查询接口 | 暴露新字段，支持 Dashboard 查看 supersede 与 stale drop | P1 |
| `app/api/routes/feishu.py` | inbound/outbound 调试接口 | 暴露新的 stale outbound 和 interruption debug 记录 | P1 |

### 2.3 本次不改模块

| 模块 | 原因 |
| --- | --- |
| `app/memory/*` | 这次优先解决的是 `working / run` 状态，不是长期 memory 问题 |
| `LangGraph` 相关模块 | 本问题发生在 Feishu visible orchestration，不需要先动 company workflow graph |
| `checkpoint` 模块 | supersede 只影响 thread/run/outbound，可先不纳入 checkpoint 语义 |

## 3. 模块级改造点

### 3.1 `app/feishu/services.py`

建议拆成五个子改动：

1. `group thread reuse`
- 当前群聊不会复用已有 thread。
- 本次需要让 `surface == FEISHU_GROUP` 时也能查到最近活跃 thread。
- `new_only / new_with_message` 仍保留显式开新会话能力。

2. `run supersede`
- 新用户插话到来时，若 thread 上已有 `active_runtrace_ref`，则创建新 run 后回写：
  - thread.active_runtrace_ref
  - 旧 runtrace.status = `superseded`
  - 旧 runtrace.superseded_by_runtrace_ref = 新 run

3. `interruption-aware dispatch`
- 在现有：
  - 显式 mention
  - 文本别名
  - semantic dispatch
  之外，再引入：
  - `pending_handoff.source_agent`
  - `pending_handoff.target_agent`
  - `last_committed_state`
  作为 dispatch 重算输入。

4. `delivery guard`
- 所有自动回复和 handoff 回复在实际发送前都必须检查：
  - `request.runtrace_ref == thread.active_runtrace_ref`
  - `request.delivery_guard_epoch == thread.delivery_guard_epoch`
- 任一不匹配，则直接落 outbound record 为 stale dropped，不调用 Feishu 发送。

5. `thread state update`
- source bot 生成回复后，需要更新：
  - `last_committed_state`
  - `pending_handoff`
- handoff target 回复后，也需要继续更新这两个状态。

### 3.2 `app/conversation/services.py`

建议新增以下方法：

- `find_active_thread_by_surface_channel(surface, channel_id) -> ConversationThread | None`
  用于群聊复用 thread
- `set_active_runtrace(thread_id, runtrace_id, delivery_guard_epoch) -> ConversationThread`
- `set_last_committed_state(thread_id, state: dict[str, Any]) -> ConversationThread`
- `set_pending_handoff(thread_id, pending_handoff: PendingHandoffState | None) -> ConversationThread`
- `clear_pending_handoff(thread_id) -> ConversationThread`
- `mark_thread_interrupted(thread_id, superseded_runtrace_ref, successor_runtrace_ref) -> ConversationThread`

注意：

- 现有 `find_thread_by_surface_channel(...)` 可以复用，但需要明确“群聊是否允许复用”的策略入口。
- `ConversationThread.runtrace_ref` 可继续保留为“最近一次 run”，但新增 `active_runtrace_ref` 用于发送闸门，避免语义混淆。

### 3.3 `app/control_plane/services.py`

建议在 `RunTraceService` 增加：

- `mark_superseded(runtrace_id, successor_runtrace_id, reason) -> RunTrace`
- `set_visible_turn_count(runtrace_id, visible_turn_count) -> RunTrace`
- `set_delivery_guard_epoch(runtrace_id, epoch) -> RunTrace`
- `set_interruption_reason(runtrace_id, reason) -> RunTrace`

建议在 `WorkTicketService` 层只复用已有能力：

- 继续使用现有 `set_supersede_refs(...)`
- 不新增独立 supersede service

### 3.4 `app/openclaw/services.py`

无需重写语义推断框架，但需要补强 prompt 输入。

建议 source / handoff target 两种模式都看到：

- `last_committed_state_summary`
- `pending_handoff_summary`
- `interruption_reason`
- `dispatch_reason`

这样模型才能在用户插话后做出：

- “这轮先该 quality-lead 解释”
- “然后 chief-of-staff 继续报 8”

而不是只盯着原始 user message 和最近几条 transcript。

## 4. 字段设计

### 4.1 `ConversationThread`

文件：
`app/conversation/models.py`

建议新增字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `active_runtrace_ref` | `str | None` | 当前 thread 正在生效的 run |
| `delivery_guard_epoch` | `int` | 每次 active run 切换后递增，用于丢弃旧结果 |
| `last_committed_state` | `dict[str, Any]` | thread 级状态锚点 |
| `pending_handoff` | `PendingHandoffState | None` | 尚未兑现的接棒 |
| `superseded_runtrace_refs` | `list[str]` | 已被当前 thread 替换掉的历史 run |

建议新增辅助模型：

```python
class PendingHandoffState(BaseModel):
    source_agent_id: str
    target_agent_id: str
    instruction: str | None = None
    reason: str | None = None
    source_runtrace_ref: str | None = None
    status: str = "active"
```

字段策略：

- `runtrace_ref`
  继续表示“最近一次 run”
- `active_runtrace_ref`
  表示“当前仍允许发送消息的 run”

### 4.2 `RunTrace`

文件：
`app/control_plane/models.py`

建议新增字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `supersedes_runtrace_ref` | `str | None` | 当前 run 接管了谁 |
| `superseded_by_runtrace_ref` | `str | None` | 当前 run 被谁接管 |
| `visible_turn_count` | `int` | 当前 run 已消耗的 bot turn 数 |
| `delivery_guard_epoch` | `int` | 当前 run 对应的发送 epoch |
| `interruption_reason` | `str | None` | 例如 `user_interruption` |
| `interruption_dispatch_targets` | `list[str]` | 中断后重算出的目标 bot |

建议扩展枚举：

- `RunTraceStatus.SUPERSEDED = "superseded"`

保留现有字段：

- `remaining_turn_budget`
- `dispatch_targets`
- `spoken_bot_ids`
- `stop_reason`

其中：

- `dispatch_targets`
  保留为当前 run 的总目标集合
- `interruption_dispatch_targets`
  专门记录“用户插话后重新算出的那一轮 bot 集合”

### 4.3 `WorkTicket`

文件：
`app/company/models.py`

本次建议：

- 不新增字段
- 复用现有：
  - `thread_ref`
  - `runtrace_ref`
  - `supersede_refs`

使用规则：

- 每条新的用户插话仍生成新的 `WorkTicket`
- 新 ticket 通过 `supersede_refs` 指向被它接管的旧 ticket 或旧 run 关联 ticket

### 4.4 `FeishuInboundEventRecord`

文件：
`app/feishu/models.py`

建议新增字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `supersedes_runtrace_ref` | `str | None` | 本次 inbound 是否接管旧 run |
| `active_thread_runtrace_ref` | `str | None` | 处理完成后 thread 的 active run |
| `interruption_dispatch_targets` | `list[str]` | 中断后重排目标 |
| `delivery_guard_epoch` | `int | None` | 当前 inbound 绑定的发送 epoch |

### 4.5 `FeishuOutboundMessageRecord`

文件：
`app/feishu/models.py`

建议新增字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `delivery_guard_epoch` | `int | None` | 发送前校验使用的 epoch |
| `delivery_guard_checked_at` | `datetime | None` | 发送闸门检查时间 |
| `stale_drop_reason` | `str | None` | 例如 `superseded_run` |
| `dropped_as_stale` | `bool` | 是否被 stale guard 拦截 |

状态建议增加约定值：

- `status = "dropped_stale"`

### 4.6 `OpenClawCollaborationContext`

文件：
`app/openclaw/models.py`

建议新增字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `dispatch_reason` | `str | None` | 说明这轮为什么选中这些 bot |
| `last_committed_state_summary` | `str | None` | 当前 thread 的状态摘要 |
| `pending_handoff_summary` | `str | None` | 当前待执行接棒摘要 |
| `interruption_mode` | `str | None` | 例如 `user_supersede` |

### 4.7 `OpenClawHandoffContext`

文件：
`app/openclaw/models.py`

建议新增字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `last_committed_state_summary` | `str | None` | handoff target 看到的状态锚点 |
| `pending_handoff_summary` | `str | None` | handoff target 看到的旧接棒摘要 |
| `dispatch_reason` | `str | None` | 当前 target 被选中的原因 |
| `interruption_reason` | `str | None` | 为什么进入本轮接棒 |

## 5. 事件目录

### 5.1 P0 事件

| event_type | 发出模块 | 触发条件 | 必带 metadata |
| --- | --- | --- | --- |
| `run_supersede_requested` | `FeishuSurfaceAdapterService` | 新群聊 inbound 命中已有 active run | `thread_id`, `prior_runtrace_id`, `new_runtrace_id`, `message_id` |
| `run_superseded` | `RunTraceService` | 旧 run 被正式置为 `superseded` | `runtrace_id`, `superseded_by_runtrace_id`, `reason` |
| `thread_active_run_switched` | `ConversationService` 或 Feishu service | thread.active_runtrace_ref 切换 | `thread_id`, `prior_runtrace_id`, `new_runtrace_id`, `delivery_guard_epoch` |
| `interruption_dispatch_resolved` | `FeishuSurfaceAdapterService` | 用户插话后重算出 bot 集合 | `thread_id`, `runtrace_id`, `targets`, `resolution_basis` |
| `stale_reply_dropped` | `FeishuSurfaceAdapterService` | 旧 run 晚到结果被发送闸门拦截 | `thread_id`, `runtrace_id`, `active_runtrace_id`, `outbound_source_kind`, `reason` |

### 5.2 P1 事件

| event_type | 发出模块 | 触发条件 | 必带 metadata |
| --- | --- | --- | --- |
| `pending_handoff_captured` | `FeishuSurfaceAdapterService` | source bot 生成了新的可兑现 handoff | `thread_id`, `runtrace_id`, `source_agent`, `target_agent`, `instruction` |
| `pending_handoff_invalidated` | `FeishuSurfaceAdapterService` | 用户插话后旧 handoff 被判失效 | `thread_id`, `runtrace_id`, `source_agent`, `target_agent` |
| `pending_handoff_corrected` | `FeishuSurfaceAdapterService` | 新 run 对旧 handoff 做了更正 | `thread_id`, `runtrace_id`, `source_agent`, `target_agent`, `corrected_instruction` |
| `last_committed_state_updated` | `FeishuSurfaceAdapterService` | 线程状态锚点被更新 | `thread_id`, `runtrace_id`, `state_summary` |
| `delivery_guard_passed` | `FeishuSurfaceAdapterService` | outbound 在发出前通过 guard | `thread_id`, `runtrace_id`, `delivery_guard_epoch`, `source_kind` |

## 6. 处理时序

### 6.1 用户插话进入系统

1. Feishu callback 到达 `FeishuSurfaceAdapterService`
2. 若是群聊，优先查找当前 channel 对应的活动 thread
3. 若 thread 存在 `active_runtrace_ref`
   - 记录 `run_supersede_requested`
4. 继续创建新 `ConversationIntakeResult`
5. 新 runtrace 创建完成后：
   - thread.active_runtrace_ref 切到新 run
   - thread.delivery_guard_epoch 自增
   - 旧 runtrace 标记 `superseded`
   - 旧 ticket / 新 ticket 建 supersede refs

### 6.2 重算回复 bot

调度器输入：

- 最新用户插话
- thread transcript
- 显式 mention
- 文本命名
- `pending_handoff.source_agent`
- `pending_handoff.target_agent`
- `last_committed_state`
- LLM semantic dispatch

调度器输出：

- `dispatch_targets`
- `interruption_dispatch_targets`
- 排序后的 bot turn order

### 6.3 回复生成与发送

1. source bot 生成回复
2. 更新 `last_committed_state` / `pending_handoff`
3. 准备 outbound request
4. 发送前执行 delivery guard
5. 通过则发送
6. 不通过则写 `stale_reply_dropped`，不调用 Feishu 发送
7. 后续 handoff target 重复同样流程

## 7. 分阶段实施

### 7.1 Phase P0

目标：

- 先让系统具备“新 run 接管旧 run，旧回复不再发送”的最低可用能力

任务：

- 群聊 thread 复用
- `ConversationThread.active_runtrace_ref`
- `RunTraceStatus.SUPERSEDED`
- `RunTrace.superseded_by_runtrace_ref`
- `delivery_guard_epoch`
- outbound stale drop
- P0 事件打点

验收：

- 用户在 bot 接棒过程中插话，旧 run 晚到回复不会继续发到群里

### 7.2 Phase P1

目标：

- 让 interruption run 的 bot 选择和回复内容更稳定

任务：

- `last_committed_state`
- `pending_handoff`
- interruption-aware dispatch target resolution
- OpenClaw 上下文增强
- P1 事件打点

验收：

- “数7”场景下，用户追问 `quality-lead` 后，新的 run 能选出 `quality-lead + chief-of-staff`，并先纠错再继续报数

### 7.3 Phase P2

目标：

- 补齐观测和可回放能力

任务：

- Dashboard / API 展示 superseded run 与 stale outbound
- 更细的排序策略
- `memory distillation` 已从本方案解耦，后续归入 `Memory Fabric` 专项

## 8. 风险与约束

### 8.1 结构性风险

- 当前 `ConversationThread` 只保留一个 `runtrace_ref`，如果不加 `active_runtrace_ref`，很容易把“最新 run”和“允许发送的 run”混成一个字段。
- 当前 outbound 发送逻辑默认“生成即发送”，如果不加 delivery guard，superseded run 的旧结果仍会漏出。

### 8.2 范围约束

- 本次不做真正的 runtime cancel token。
- 本次不引入新的长期 memory 写入路径。
- 本次不接入 `memory distillation`，避免与 `Memory Fabric` 专项职责重叠。
- 本次不把 `20` 轮预算提升到 thread 级。

## 9. 建议的最小开发顺序

1. 先改 `ConversationThread` 与 `RunTrace` 模型字段。
2. 再改 `ConversationService` 和 `RunTraceService` 的状态更新方法。
3. 然后改 `FeishuSurfaceAdapterService` 的 inbound 入口与 outbound guard。
4. 最后补 `OpenClaw` 上下文字段和 API 可观测面。

## 10. 与现有文档的关系

- 行为与产品语义以 [Feishu Group Interruption And Run Supersede Plan](./feishu-group-interruption-run-supersede-plan.md) 为准。
- 长期记忆蒸馏、promotion 与 recall 边界以 [Memory Fabric 设计](../memory-fabric-design.md) 为准。
- 本文负责把该方案翻译成开发者可以直接执行的实施拆解。
