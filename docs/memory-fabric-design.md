# One-Person Company Memory Fabric 设计文档

本文是 `one-person-company` memory 子系统的 source of truth。目标不是补充“agent 有记忆”这一个点，而是定义一套可接入 CEO、Executive Office、Departments、TaskGraph、Quality Gate 和自我进化机制的正式 `Memory Fabric`。

## 1. 设计目标

- 让每个虚拟员工拥有自己的私有记忆，同时保留部门共享记忆和公司共享记忆。
- 让 `memory` 成为正式系统层，而不是 prompt 里的临时技巧。
- 让 handoff、checkpoint、rollback、quality、self-improving 都建立在统一的 memory 模型上。
- 保持平台中立设计，同时给出 V1 推荐的存储实现映射。
- 确保 V1 单席位部门与 V2 多席位部门之间的 memory 结构兼容。

## 2. 设计原则

- `scope` 和 `kind` 分开建模，避免把“谁拥有记忆”和“记忆是什么类型”混在一起。
- 长期 memory 只能来自蒸馏后的内容，不能直接把所有对话和 trace 原样塞进去。
- 自我进化是受控学习，不是 agent 自主修改公司制度。
- 所有共享 memory 都必须有显式命名空间、可见性规则和 promotion 审批链。
- recall 默认最小可见，不做“所有人默认能看全部”的设计。

## 3. Memory Fabric 在整体架构中的位置

```text
Human CEO Layer
  -> company_shared strategic memory

Executive Office Layer
  -> memory routing / approval / distillation / promotion

Virtual Department Layer
  -> department_shared namespaces

Orchestration Layer
  -> run lifecycle hooks
  -> task start recall
  -> handoff persist
  -> verdict checkpoint
  -> rollback

Memory Fabric
  -> run
  -> agent_private
  -> department_shared
  -> company_shared
  -> index / evidence / checkpoint

Governance & Observability Layer
  -> audit every mutation and approval
```

## 4. 双维模型

### 4.1 Scope

| scope | 说明 | 典型 owner |
| --- | --- | --- |
| `run` | 当前一次 session / run 的临时上下文 | `run_id` |
| `agent_private` | 单个虚拟员工的私有记忆 | `employee_id` |
| `department_shared` | 部门级共享记忆空间 | `department_name` |
| `company_shared` | 整个公司的共享长期记忆 | `company_id` |

### 4.2 Kind

| kind | 说明 | 典型内容 |
| --- | --- | --- |
| `working` | 短期上下文 | 当前任务状态、阶段摘要、临时决策 |
| `episodic` | 事件与经验 | 历史 run、失败经验、复盘记录 |
| `semantic` | 可检索知识 | 产品事实、术语、客户画像、FAQ |
| `procedural` | 可执行规则 | SOP、checklist、policy、playbook |
| `evidence` | 证据与 verdict | 截图、测试结果、spec quote、审批材料 |

### 4.3 Scope x Kind 矩阵

| scope | working | episodic | semantic | procedural | evidence |
| --- | --- | --- | --- | --- | --- |
| `run` | 当前任务 scratchpad | 本轮关键事件 | 本轮临时综合摘要 | 当前 recipe 的阶段步骤 | 当前测试与验证结果 |
| `agent_private` | 当前席位偏好上下文 | 个人任务历史、失败回避经验 | 个人检索关键词、主题索引 | 工具偏好、个人 heuristics | 个人审阅记录 |
| `department_shared` | 部门当前任务板摘要 | 部门复盘与 handoff 历史 | 部门知识库、术语、常见问题 | SOP、handoff 模板、评审清单 | 部门级质量案例 |
| `company_shared` | 当前公司级重点事项 | 战略事件、月度 checkpoint | 产品事实、客户定义、公司术语 | 跨部门 recipe、policy、战略 playbook | board-style evidence package |

## 5. 关键对象

### `MemoryRecord`

核心字段：

- `scope`
- `scope_id`
- `owner_id`
- `kind`
- `visibility`
- `content`
- `confidence`
- `promotion_state`
- `version`
- `checkpoint_ref`
- `artifact_refs`
- `retention`
- `source_trace`

### `MemoryNamespace`

核心字段：

- `namespace_id`
- `scope`
- `owner`
- `read_policy`
- `write_policy`
- `promotion_policy`

### `RecallQuery`

核心字段：

- `scope_filter`
- `kind_filter`
- `tags`
- `project`
- `department`
- `receiver`
- `time_window`
- `min_confidence`

### `LearningCandidate`

核心字段：

- `source_run`
- `agent_id`
- `candidate_type`
- `proposed_scope`
- `evidence_refs`
- `confidence`
- `expected_reuse`

### `EvolutionReview`

核心字段：

- `candidate_id`
- `reviewer`
- `decision`
- `reason`
- `target_scope`
- `version_action`

### `Checkpoint`

扩展字段：

- `memory_snapshot_refs`
- `promotion_state_refs`
- `rollback_scope`

## 6. 命名空间与可见性

### 6.1 默认可见性

- agent 默认可读：
  自己的 `agent_private`
  自己所属部门的 `department_shared`
  被授权的 `company_shared`
- agent 默认不可读：
  其他部门的 `department_shared`
  其他席位的 `agent_private`
  未授权的敏感 `company_shared`

### 6.2 跨部门 recall

跨部门 recall 不是禁止，而是受控：

- 必须带 `scope_filter`
- 必须带 tags
- 必须带 `project / stage / receiver` 中的至少一个
- 必须满足策略层 read policy

### 6.3 典型命名空间

```text
run:retroboard:run-2026-03-13-01
employee:engineering-lead
department:engineering
company:default
```

## 7. 生命周期

### 7.1 写入流水线

```text
capture
  -> summarize
  -> classify(scope + kind)
  -> route namespace
  -> approve if needed
  -> persist
  -> index
```

### 7.2 读取流水线

```text
build RecallQuery
  -> policy check
  -> retrieve by scope + tags + semantic match
  -> rerank
  -> inject into task context
```

### 7.3 按交互模式的默认写入策略

| interaction mode | 默认 memory 写入 | 默认 TaskGraph | 默认 checkpoint |
| --- | --- | --- | --- |
| `idea_capture` | `CEO intent memory` + 必要 `company_shared semantic/episodic` | 默认不建 | 默认无 |
| `quick_consult` | `run + agent_private + optional department_shared summary` | 默认不建完整图 | 默认无 |
| `department_task` | `department_shared` + 必要 `company_shared summary` | 最小 `TaskGraph` 或单节点任务卡 | 轻量 |
| `formal_project` | 正式回写 `run / agent_private / department_shared / company_shared` | 完整 `TaskGraph` | 正式 |
| `review_decision` | `DecisionRecord` + `board-style evidence package` + 必要 `company_shared` | 读取既有图或挂靠既有图 | 必要时新建 |
| `override_recovery` | supersede refs + rollback refs + 新方向摘要 | 更新或恢复既有图 | 强制 |
| `escalation` | 风险摘要、冲突点、建议动作 | 可挂靠现有图，也可独立升级单 | 视处理结果而定 |

补充规则：

- `scheduled_heartbeat` 默认先写：
  `heartbeat summary -> episodic`
  再由 Executive Office 判断是否需要提升为正式任务或共享知识。
- `event_based` 触发默认优先写：
  `run summary + related WorkTicket refs`
  避免直接把原始事件流写成长期事实。

### 7.4 轻量流程的 memory 原则

- 轻量流程不是“无状态聊天”，必须留下最小可追踪记录。
- `idea_capture` 重点写 `CEO intent memory`，不是直接生成完整项目记忆。
- `quick_consult` 重点写可复用摘要，避免把完整对话原样沉淀成长期 memory。
- `department_task` 默认只写相关部门需要的共享摘要，不自动污染公司级 procedural memory。
- 所有轻量流程都必须具备 `sync-back` 能力，避免 Executive Office 与部门上下文断裂。
- `WorkTicket` 与 `ConversationThread` 共享引用但不共享语义：
  `ConversationThread` 负责会话上下文，
  `WorkTicket` 负责正式工作项的持续跟踪，
  memory 写入时默认同时挂接两类 ref。

### 7.5 回滚流水线

```text
NO-GO / failure
  -> locate latest valid Checkpoint
  -> restore task graph state
  -> restore memory snapshot refs
  -> mark superseded writes
  -> resume from rollback_scope
```

## 8. Distillation

### 8.1 为什么需要 distillation

- 长时间运行会产生大量噪声。
- 原始 conversation 和 tool traces 可审计，但不适合直接变成长期记忆。
- 不蒸馏就会导致 recall 污染和 procedural drift。

### 8.2 默认策略

- 长对话先摘要成阶段结论。
- 重复执行先合并成“稳定模式”再写入 semantic / procedural。
- 原始 evidence 保留原件，但 recall 默认返回摘要和索引，不直接返回全部原始材料。

### 8.3 产物去向

| 蒸馏结果 | 默认落点 |
| --- | --- |
| 阶段结论摘要 | `episodic` |
| 稳定事实 | `semantic` |
| 可复用步骤 | `procedural` |
| 审批与验证材料 | `evidence` |

## 9. 自我进化

### 9.1 三级进化模型

| 级别 | 范围 | 示例 | 默认权限 |
| --- | --- | --- | --- |
| `L1 private auto-learning` | `agent_private` | 个人 heuristics、检索词、工具偏好 | 自动 |
| `L2 department promotion` | `department_shared` | checklist、handoff 模板、部门 FAQ | 审批 |
| `L3 company promotion` | `company_shared` | policy、跨部门 recipe、战略 playbook | 严格审批 |

### 9.2 默认边界

- agent 可以自动学习，但不能自动成为制度制定者。
- agent 可以生成 `LearningCandidate`，不能绕过审批直接写公司级 procedural memory。
- procedural memory 的升级必须版本化、可 supersede、可 rollback。

### 9.3 Promotion 流程

```text
run outcome
  -> self review
  -> LearningCandidate
  -> evaluator / reviewer
  -> approve or reject
  -> write promoted MemoryRecord
  -> monitor reuse outcome
```

## 10. 与现有层级的融合方式

### 10.1 Human CEO Layer

- 读写 `company_shared` 的战略、目标、季度重点、月度 checkpoint。
- 不直接操作底层 memory 存储，而通过 Executive Office 发起写入和审批。

### 10.2 Executive Office Layer

- 是 memory 的默认路由与 promotion 中枢。
- 负责：
  recall 前置
  handoff 回写
  distillation
  company-level promotion
  checkpoint 审核

### 10.3 Virtual Department Layer

- 每个部门拥有固定 `department_shared namespace`。
- 部门席位默认能写自己的 `agent_private`，并对本部门共享记忆发起 promotion。

### 10.4 Orchestration Layer

以下节点必须接入 memory hook：

- session start
- task start
- task completion
- handoff
- quality verdict
- rollback
- monthly checkpoint

### 10.5 Governance & Observability Layer

- 记录每次 memory mutation
- 记录每次 approval / reject
- 记录每次 promotion / rollback
- 记录 supersede 和版本切换
- 审计日志默认保留完整动作轨迹，但不自动等同为长期 memory。
- 长期 memory 必须经过 distillation、分类和路由后再落库。

## 11. 推荐 V1 存储映射

| 子能力 | 推荐实现 | 原因 |
| --- | --- | --- |
| `working / run` | Redis 或等价缓存 | 快速读写、带 TTL |
| `episodic / checkpoint / metadata` | Postgres | 结构化、可审计、适合查询 |
| `semantic retrieval` | Vector DB | 语义检索和标签过滤 |
| `procedural` | versioned registry 或 Git-backed 资产 | 版本清晰、可 review、可 rollback |
| `evidence` | object storage + metadata index | 原件保存与元数据检索分离 |

## 12. 与 `mem0` 的整合边界

官方仓库 [mem0](https://github.com/mem0ai/mem0) 在当前方案中被定义为一个**可选整合边界**，而不是 V1 默认必选依赖。它可以在后续作为 `episodic / semantic recall` 的增强路径接入，但它不是当前方案的完整 `Memory Fabric` source of truth。

### 12.1 `mem0` 承担的范围

- `episodic` 的长期经验检索。
- `semantic` 的长期知识 recall。
- `agent_private / department_shared / company_shared` 三类长期命名空间的 metadata 过滤与 recall 辅助。
- `remember / search` 的统一入口之一，通过 `Mem0Bridge` 暴露给当前方案。

### 12.2 不交给 `mem0` 的范围

- `working` 运行态上下文。
- `procedural` 的版本管理、review、supersede 与 rollback。
- `evidence` 原件与 verdict 存储。
- `checkpoint` 的 source of truth。
- `promotion`、`approval`、`governance` 的规则定义。

### 12.3 V1 可选落点

| memory kind | V1 默认承载 |
| --- | --- |
| `working` | 不进入长期检索层，继续留在运行态上下文或缓存 |
| `episodic` | 先由当前 `Memory Fabric` / tool bridge 提供 recall；如后续需要，再由 `Mem0Bridge` 接入 `mem0` 做增强 |
| `semantic` | 先由当前 `Memory Fabric` / tool bridge 提供 recall；如后续需要，再由 `Mem0Bridge` 接入 `mem0` 做增强 |
| `procedural` | 继续走 versioned registry |
| `evidence` | 继续走 object storage + metadata index |

### 12.4 内部适配对象

| 对象 | 责任 | 边界 |
| --- | --- | --- |
| `Mem0Bridge` | 作为可选适配层统一 `remember / recall / search`，并将 `scope / kind / tags / project / stage / receiver` 写入 metadata | 不定义审批和 promotion，也不是 V1 默认必选依赖 |
| `CheckpointStore` | 保存 `TaskGraph snapshot + memory refs + quality verdict + approval state` | 不承担 recall/search |
| `MemoryGovernanceService` | 管理 `promotion`、`approval`、`supersede`、`rollback` | 不把治理规则交给 `mem0` |

## 13. OpenClaw session memory vs company memory fabric

### 13.1 两层记忆不是一回事

`OpenClaw` 原生会维护自己的 session/context，用于：

- 当前 agent 的对话上下文
- 当前 session 的 tool usage 历史
- channel / session routing state
- agent 自己在一次运行中的短期工作记忆

但这些能力不等于当前项目的 `Memory Fabric`。当前项目的长期真相源仍然固定为：

- `agent_private`
- `department_shared`
- `company_shared`
- `Checkpoint + memory refs`
- `Evidence + approval / supersede / rollback`

### 13.2 正式边界

| 层 | 承载内容 | 是否 source of truth |
| --- | --- | --- |
| `OpenClaw session/context` | agent 的短期对话与运行态上下文 | 否 |
| 当前项目 `Memory Fabric` | 长期记忆、治理、promotion、rollback、checkpoint refs | 是 |

固定结论：

- OpenClaw session/context 不替代 `agent_private / department_shared / company_shared`。
- 当前 Memory Fabric 仍是长期治理真相源。
- OpenClaw 访问 memory 应通过工具桥，而不是把完整公司记忆直接硬拼进 prompt。

### 13.3 工具桥方式

为避免 prompt 内嵌和 session 漂移，当前方案建议把长期记忆通过工具桥暴露给 OpenClaw agent，例如：

- `opc_memory_recall`
- `opc_memory_write_candidate`
- `opc_checkpoint_lookup`
- `opc_work_ticket_get`

这样：

- OpenClaw 保持原生 tools/skills/session 模式；
- 当前项目继续保留 Memory Governance、approval、promotion、supersede 的控制权；
- 所有高影响 memory mutation 仍可回写到 `RunTrace / Checkpoint / Audit`。

## 14. 与 `agency-agents` 的关系

- `agency-agents` 的 `remember / recall / rollback / search` 提供的是使用模式，不是内建 memory engine。
- 当前项目应把这些模式编译进 `employee pack` 的 prompt 指令，但真正的 memory 能力由 `Memory Fabric` 提供。
- 这意味着：
  上游 prompt 可以指导 agent 什么时候 recall 和记忆；
  但 scope、namespace、approval、promotion、versioning 由当前架构统一定义。

## 15. 默认失败模式与防护

| 风险 | 默认防护 |
| --- | --- |
| recall 污染 | 强制 `scope_filter + tags + project/stage/receiver` |
| 共享记忆漂移 | promotion 审批 + versioning |
| procedural 污染 | 只能通过 review 提升 |
| 跨部门越权读取 | namespace policy + audit |
| 长期记忆膨胀 | distillation + archive + supersede |
| rollback 不完整 | memory-aware checkpoint |

## 16. 验收场景

- `Agent private recall`：
  Engineering Lead 能在新 session 中读回自己的调试经验，但看不到其他席位私有记忆。
- `Department shared reuse`：
  Design Lead 把 checklist 提升到 `department_shared` 后，同部门后续任务能自动检索到。
- `Company strategic memory`：
  CEO 更新战略后，Product、Research、Executive Office 能读到同一份目标描述。
- `Handoff continuity`：
  Product -> PM -> Design -> Engineering 的链路无需人工反复粘贴上下文。
- `Quality rollback`：
  Quality 给出 NO-GO 后，系统能恢复到最近一个包含任务状态和 memory snapshot 的 checkpoint。
- `Promotion guardrail`：
  agent 能自动写私有记忆，但不能静默写部门或公司共享记忆。
- `Stale memory control`：
  被 supersede 的 procedural memory 不再参与默认 recall，但仍可审计与回滚。
- `OpenClaw memory boundary`：
  agent 能在 session 中使用 OpenClaw 原生上下文，但正式长期记忆仍要通过当前项目 Memory Fabric 的工具桥与治理链落库。
- `Cross-department access policy`：
  Growth 默认不能检索 Trust / Security / Legal 的敏感记忆。
- `Self-evolution safety`：
  连续成功不会自动改写公司级 policy，只会生成待审批的 `LearningCandidate`。
