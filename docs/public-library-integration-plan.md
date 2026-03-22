# 公开库整合方案总入口

本文是当前“公开库如何接入 `one-person-company / multi-agent-company` 文档体系”的 source of truth。范围只包括文档设计，不包括任何代码实现、依赖接入、PoC 或运行时开发。

## 1. 整合目标

- 在不改变现有方案版本和概念接口的前提下，为当前主方案补一层“公开库绑定关系”说明。
- 固定当前默认主栈：
  [OpenClaw](https://docs.openclaw.ai/) 负责 `agent plane`，
  [LangGraph](https://github.com/langchain-ai/langgraph) 负责 `company workflow orchestration`，
  [agency-agents](https://github.com/msitarzewski/agency-agents) 负责 persona/division/workflow 资产源，
  当前项目自定义 `Memory Fabric` 负责长期记忆治理。
- 明确哪些能力由公开库承担，哪些能力仍由本项目定义：
  产品语义层不外包；
  运行时能力层可复用；
  治理、审批、promotion、checkpoint 仍归当前方案。

## 2. 选型结论

### 当前主栈

- 主 `agent plane`：
  [OpenClaw](https://docs.openclaw.ai/)
- 主 `company workflow plane`：
  [LangGraph](https://github.com/langchain-ai/langgraph)
- 主 persona 资产源：
  [agency-agents](https://github.com/msitarzewski/agency-agents)
- 主长期记忆治理层：
  当前项目自定义 `Memory Fabric`

### 选择原因

- `OpenClaw` 最适合承接单 agent runtime、skills、tools、sessions、sandbox 与 provider/model routing。
- `LangGraph` 最适合承接当前文档里的 `TaskGraph`、checkpoint、长流程状态、human-in-the-loop 和 graph/subgraph 编排需求。
- `agency-agents` 已经按 division/role/workflow 组织好上游资产，最适合映射为 `VirtualDepartment -> VirtualEmployee -> Employee Pack`。
- 当前项目的 `Memory Fabric` 已经承接长期记忆、checkpoint refs、approval、promotion 与 supersede 语义，因此不再把完整长期治理层外包给公开库。
- [`paperclipai/paperclip`](https://github.com/paperclipai/paperclip/blob/master/README.md) 只作为外部 benchmark 与能力参考源：
  它验证了“公司级 control plane”叙事，但不是当前主栈依赖，也不替代 `human CEO` 主模型。

## 3. 分层绑定关系

| 当前方案层 | 默认绑定 | 说明 |
| --- | --- | --- |
| `Human CEO Layer` | 当前项目自定义 | 不外包给公开库 |
| `Executive Office Layer` | 当前项目自定义 | `Chief of Staff` 仍是公司层概念，不是第三方 scheduler |
| `Virtual Department Layer` | 当前项目自定义 | 部门、席位、激活策略由当前文档定义 |
| `OpenClaw Agent Plane` | `OpenClawProvisioningService -> OpenClawGatewayAdapter -> OpenClaw native agents` | 单 agent runtime、skills、tools、sessions、sandbox |
| `Orchestration Layer` | `LangGraphRuntimeAdapter -> LangGraph` | 公司级主图、子图、状态、checkpoint |
| `Workflow Recipe Layer` | `LangGraphRuntimeAdapter + 当前项目 recipe 定义` | recipe 语义仍由当前方案定义 |
| `Persona Asset Layer` | `PersonaSourceAdapter -> agency-agents` | 上游 Markdown 先编译成 `PersonaPack` |
| `Employee Pack Layer` | `EmployeePackCompiler -> OpenClawWorkspaceCompiler` | 将多个 `PersonaPack` 组合成席位，再编译成 `OpenClawWorkspaceBundle` |
| `Memory Fabric` | 当前项目治理层 + memory/tool bridge | 长期记忆、checkpoint、approval、promotion 仍由当前项目定义 |
| `Visible Communication Orchestration` | `FeishuMentionDispatch + VisibleRoomOrchestrator` | V1 Feishu 不直接依赖 OpenClaw shared groups |
| `Checkpoint / Approval / Promotion` | 当前项目自定义 | 不交给 `mem0` 或 `LangGraph` 的默认模型替代 |
| `Distribution Layer` | 当前项目定义，参考 `agency-agents` | 参考上游分发模式，不直接复用为运行时 |

## 4. V1 文档落地方案

- 只把两条 recipe 明确绑定到公开库主栈：
  `Product Build Loop`
  `Discovery / Synthesis Loop`
- `CEO Strategy Loop` 在 V1 继续保留为轻量控制面流程，重点写清 route、checkpoint 和 strategic memory，而不是增加新的运行时复杂度。
- `Launch / Growth Loop` 延后到 `V1.5`，先保留组织与流程定义，不做当前主栈的第一批承接对象。
- V1 只激活核心 7 个部门：
  `Executive Office`
  `Product`
  `Research & Intelligence`
  `Project Management`
  `Design & UX`
  `Engineering`
  `Quality`
- V1 的正式落点固定为：
  `OpenClaw` 负责 agent 执行；
  `LangGraph` 负责公司 workflow；
  `Feishu` 由当前项目做 visible-room fan-out；
  `Memory Fabric` 继续承接长期治理与 evidence；
  `Slack` 延后到 `V2`

## 5. V2/V3 演进路径

### V2

- 保持 `OpenClaw + LangGraph + agency-agents + current Memory Fabric` 主栈不变。
- 扩展 `Launch / Growth Loop`，把 `Growth & Marketing`、`Customer Success & Support` 纳入正式可激活范围。
- 开放 `L2 department promotion`，让 `department_shared procedural memory` 进入正式审批流。
- 把 `Quality Lead` 从“单席位、双模式”升级为“同部门双员工”，但保持部门接口不变。
- 引入 `company template / org template / employee pack bundle` 作为模板化资产能力。
- 引入 `Slack` 作为第二沟通平台。

### V3

- 继续保持现有公共接口稳定，只在实现层考虑替代路径。
- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) 仅作为更强 DevUI / time-travel / observability 的候选替代 runtime。
- [CAMEL](https://github.com/camel-ai/camel) 仅作为 workforce / society / large-scale seat simulation 的研究型扩展。
- [full-stack-ai-agent-template](https://github.com/vstorm-co/full-stack-ai-agent-template) 仅作为未来 Web UI、auth、streaming、admin 壳层的候选，不进入核心引擎定义。
- 预留 `portfolio / multi-company isolation` 路线，但不进入当前 V1 主线。

## 6. 替代路线与不选原因

### [CrewAI](https://github.com/crewAIInc/crewAI)

- 保留为原型/对照路线。
- 不进入当前主栈的原因：
  角色协作心智很强，但当前方案更需要稳定的图式状态、checkpoint 和 memory-aware orchestration 作为核心骨架。

### [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)

- 保留为未来企业级替代路线。
- 不进入当前 V1 主线的原因：
  对当前文档阶段来说太重，且会过早把方案绑定到另一套更具体的生态与实现假设。

### [CAMEL](https://github.com/camel-ai/camel)

- 保留为研究和 workforce/society 方向参考。
- 不进入当前 V1 主线的原因：
  概念很接近，但当前方案更需要产品化控制面和稳定的组织化运行骨架，而不是先进入大规模 society 试验。

## 7. 风险与边界

- 不能把 `agency-agents` 误写成 scheduler 或 runtime。
- 不能把 `OpenClaw` 误写成公司组织模型、治理层或长期 memory 真相源。
- 不能把 `LangGraph` 误写成单 agent runtime 或公司组织模型本身。
- 不能把 `Feishu` 误写成 OpenClaw shared groups 的直接等价物。
- 不能把 `Paperclip` 误写成当前项目的依赖或隐式替代方案。
- 公开库只承担实现层能力，不替代：
  `Chief of Staff`
  `VirtualDepartment`
  `VirtualEmployee`
  `Memory Fabric`
  `ApprovalGate`
- 当前文档更新的目标是“明确可复用能力边界”，不是“开始实现公开库接入工程”。
