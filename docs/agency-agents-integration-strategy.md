# 从 `agency-agents` 到 One-Person Company 的上游接入策略

本文定义官方仓库 [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) 如何作为 `one-person-company` 的上游角色资产层接入。核心原则是：`agency-agents` 提供 division、role、workflow recipe、quality gate pattern 和 distribution 思路；当前项目负责把这些上游资产编译成适合“一人公司”的 `department seat + employee pack`，并进一步编译成 `OpenClaw` 原生 agent workspace。

## 1. 定位

- `agency-agents` 是 `role / persona / workflow asset source`。
- 当前项目的主方案是 `one-person-company` 产品概念 + `multi-agent-company` 底层引擎。
- 两者关系是：
  上游仓库提供角色、部门、示例流程与分发模式；
  当前项目负责组织图、席位模型、路由规则、治理与运行边界。
- 三个不能做的错误映射：
  直接把上游所有角色当成当前系统都要常驻运行的员工；
  直接把 [agents-orchestrator.md](https://github.com/msitarzewski/agency-agents/blob/main/specialized/agents-orchestrator.md) 当成 scheduler；
  直接把 [scripts/convert.sh](https://github.com/msitarzewski/agency-agents/blob/main/scripts/convert.sh) 当成 runtime 编排逻辑。

### 在主栈中的位置

当前默认主栈固定为：
[OpenClaw](https://docs.openclaw.ai/) + [LangGraph](https://github.com/langchain-ai/langgraph) + [agency-agents](https://github.com/msitarzewski/agency-agents) + 当前项目自定义 `Memory Fabric`

在这套主栈里，`agency-agents` 只进入 `PersonaSourceAdapter`、`EmployeePackCompiler` 和 `OpenClawWorkspaceCompiler` 三层：

- `OpenClaw` 负责单 agent runtime、skills、tools、sessions、sandbox 与 provider/model routing。
- `LangGraph` 负责 `WorkflowRecipe`、`TaskGraph`、graph/subgraph 与公司级 checkpoint 语义的实际运行时承载。
- 当前 `Memory Fabric` 负责长期记忆治理、promotion、approval、checkpoint refs 与 evidence。
- `agency-agents` 负责 division、role、workflow、quality gate、memory usage pattern 的上游资产来源。

因此它和另外两个公开库的关系固定为：

```text
agency-agents
  -> PersonaSourceAdapter
  -> PersonaPack
  -> EmployeePackCompiler
  -> VirtualEmployee / Employee Pack
  -> OpenClawWorkspaceCompiler
  -> OpenClawWorkspaceBundle
  -> OpenClaw native agent workspace

Employee Pack
  -> seat-level memory instructions
  -> tool / sandbox policy
  -> channel account binding
  -> OpenClaw bootstrapping files

OpenClaw native agent workspace
  -> AGENTS.md / SOUL.md / IDENTITY.md / BOOTSTRAP.md / SKILLS.md / TOOLS.md / USER.md / HEARTBEAT.md
  -> OpenClaw agent runtime
  -> current project Memory Fabric / WorkTicket / RunTrace via tool bridge
```

### Seat Compiler 输出契约

`EmployeePackCompiler` 的输出不再停留在“运行时 prompt 包”，而是进入两级编译：先形成当前方案可消费的 `Employee Pack`，再形成 `OpenClawWorkspaceBundle`。最小输出契约固定为：

| 输出对象 | 说明 |
| --- | --- |
| `PersonaPack[]` | 从上游角色提炼出的标准化角色资产 |
| `VirtualEmployee` | 当前 V1 单席位员工定义 |
| `DepartmentSeatMap` entry | 部门到席位的正式映射 |
| `Employee Pack` | 当前方案内部消费的组合包，包含 role rules、workflow hints、memory profile、tool/sandbox hints |
| `company_access_profile` | 当前席位可访问的 `company_shared` 范围 |
| `private_namespace / department_namespace` | 与 `Memory Fabric` 对齐的命名空间信息 |
| `OpenClawWorkspaceBundle` | `AGENTS.md / SOUL.md / IDENTITY.md / BOOTSTRAP.md / SKILLS.md / TOOLS.md / USER.md / HEARTBEAT.md` 的编译结果 |
| `OpenClawAgentBinding` | `employee_id -> openclaw_agent_id -> workspace_path -> channel accounts` 的正式绑定 |
| `EmployeeSkillPack` | 每席位的专业 skills、通用 skills 与验证状态 |
| `SkillManifest[]` | 每个 skill 的 source/license/install/verify/native-export 元数据 |

固定边界：

- `agency-agents` 不能跳过 `PersonaPack` 直接定义 `VirtualDepartment`。
- `Employee Pack` 不能直接改写 `WorkflowRecipe` 的部门边界。
- `OpenClawWorkspaceBundle` 不能替代 `VirtualDepartment`、`VirtualEmployee` 或 `Chief of Staff` 的公司语义定义。
- seat pack 里可以包含 memory usage instructions，但不能直接定义 `promotion / approval / rollback` 规则。

## 2. 上游结构如何映射到部门席位

### 映射原则

- 先定义 `VirtualDepartment`，再决定该部门在 V1 放哪个 `VirtualEmployee` 席位。
- 每个席位再绑定一个或多个上游 `PersonaPack`，形成 `employee pack`。
- 单个上游 persona 不足以覆盖部门职责时，使用 `composite employee pack`，但对外仍保持一个席位。
- `DepartmentSeatMap` 是当前项目的中间格式，不直接把上游 Markdown 作为运行时唯一资产模型。
- 每个席位在编译时都要绑定 memory profile：
  `private_namespace`
  `department_namespace`
  `company_access_profile`
- 每个席位在进入运行前都要进一步绑定：
  `openclaw_agent_id`
  `workspace bundle`
  `tool / sandbox profile`
  `channel accounts`

### 12 部门席位映射

| 部门 | V1 席位 | 代表上游来源 | 说明 |
| --- | --- | --- | --- |
| Executive Office | `Chief of Staff` | [Studio Producer](https://github.com/msitarzewski/agency-agents/blob/main/project-management/project-management-studio-producer.md)、[Senior Project Manager](https://github.com/msitarzewski/agency-agents/blob/main/project-management/project-manager-senior.md)、[Agents Orchestrator](https://github.com/msitarzewski/agency-agents/blob/main/specialized/agents-orchestrator.md) | 负责 intake、统筹、状态汇报 |
| Product | `Product Lead` | [Sprint Prioritizer](https://github.com/msitarzewski/agency-agents/blob/main/product/product-sprint-prioritizer.md) | 负责价值判断、优先级和版本目标 |
| Research & Intelligence | `Research Lead` | [Trend Researcher](https://github.com/msitarzewski/agency-agents/blob/main/product/product-trend-researcher.md) | 负责市场、趋势、竞品与用户信号 |
| Project Management | `Delivery Lead` | [Senior Project Manager](https://github.com/msitarzewski/agency-agents/blob/main/project-management/project-manager-senior.md)、[Project Shepherd](https://github.com/msitarzewski/agency-agents/blob/main/project-management/project-management-project-shepherd.md) | 负责任务图、推进、依赖和范围 |
| Design & UX | `Design Lead` | [UX Researcher](https://github.com/msitarzewski/agency-agents/blob/main/design/design-ux-researcher.md)、[UX Architect](https://github.com/msitarzewski/agency-agents/blob/main/design/design-ux-architect.md) | 负责研究、结构、体验基础 |
| Engineering | `Engineering Lead` | [Backend Architect](https://github.com/msitarzewski/agency-agents/blob/main/engineering/engineering-backend-architect.md)、[Frontend Developer](https://github.com/msitarzewski/agency-agents/blob/main/engineering/engineering-frontend-developer.md)、[Rapid Prototyper](https://github.com/msitarzewski/agency-agents/blob/main/engineering/engineering-rapid-prototyper.md) | 负责设计到实现的技术交付 |
| Quality | `Quality Lead` | [Evidence Collector](https://github.com/msitarzewski/agency-agents/blob/main/testing/testing-evidence-collector.md)、[Reality Checker](https://github.com/msitarzewski/agency-agents/blob/main/testing/testing-reality-checker.md) | 单席位双模式 |
| Growth & Marketing | `Growth Lead` | [Growth Hacker](https://github.com/msitarzewski/agency-agents/blob/main/marketing/marketing-growth-hacker.md)、[Brand Guardian](https://github.com/msitarzewski/agency-agents/blob/main/design/design-brand-guardian.md) | 负责增长、品牌与上线传播 |
| Sales & Partnerships | `Partnerships Lead` | [Outbound Strategist](https://github.com/msitarzewski/agency-agents/blob/main/sales/sales-outbound-strategist.md)、[Account Strategist](https://github.com/msitarzewski/agency-agents/blob/main/sales/sales-account-strategist.md) | 负责合作、外联与销售线索 |
| Customer Success & Support | `Customer Success Lead` | [Support Responder](https://github.com/msitarzewski/agency-agents/blob/main/support/support-support-responder.md) | 负责反馈闭环、支持与服务恢复 |
| Business Operations | `Operations Lead` | [Studio Operations](https://github.com/msitarzewski/agency-agents/blob/main/project-management/project-management-studio-operations.md)、[Finance Tracker](https://github.com/msitarzewski/agency-agents/blob/main/support/support-finance-tracker.md) | 负责运营流程与财务健康 |
| Trust / Security / Legal | `Trust & Compliance Lead` | [Legal Compliance Checker](https://github.com/msitarzewski/agency-agents/blob/main/support/support-legal-compliance-checker.md)、[Agentic Identity & Trust Architect](https://github.com/msitarzewski/agency-agents/blob/main/specialized/agentic-identity-trust.md)、[Identity Graph Operator](https://github.com/msitarzewski/agency-agents/blob/main/specialized/identity-graph-operator.md) | 负责合规、身份、审计与共享实体一致性 |

## 3. Workflow Recipe 采用方式

### Executive Office / CEO Strategy

主要来源：
[project-management-studio-producer.md](https://github.com/msitarzewski/agency-agents/blob/main/project-management/project-management-studio-producer.md)
[project-manager-senior.md](https://github.com/msitarzewski/agency-agents/blob/main/project-management/project-manager-senior.md)
[agents-orchestrator.md](https://github.com/msitarzewski/agency-agents/blob/main/specialized/agents-orchestrator.md)

采用要点：

- 把“高层统筹”和“任务级协调”收敛到 `Executive Office`，而不是散落在 Product 或 PM 里。
- `Chief of Staff` 负责 intake、规范化、节奏、总览；不是直接替代调度器。
- `CEO Strategy Loop` 的产出要能进入 `CEO intent memory` 和 `company checkpoint`。

### Product Build

主要来源：
[workflow-startup-mvp.md](https://github.com/msitarzewski/agency-agents/blob/main/examples/workflow-startup-mvp.md)
[product-sprint-prioritizer.md](https://github.com/msitarzewski/agency-agents/blob/main/product/product-sprint-prioritizer.md)
[design-ux-researcher.md](https://github.com/msitarzewski/agency-agents/blob/main/design/design-ux-researcher.md)
[engineering-backend-architect.md](https://github.com/msitarzewski/agency-agents/blob/main/engineering/engineering-backend-architect.md)

采用要点：

- 默认链路固定为：
  `Product -> Project Management -> Design -> Engineering -> Quality`
- 这个链路映射的是公司内部产品研发流程，而不是自由拼装的多 agent 对话。
- `Research & Intelligence` 可在链路前置或并行参与。

### Discovery / Memory Handoff

主要来源：
[workflow-with-memory.md](https://github.com/msitarzewski/agency-agents/blob/main/examples/workflow-with-memory.md)
[integrations/mcp-memory/README.md](https://github.com/msitarzewski/agency-agents/blob/main/integrations/mcp-memory/README.md)
[examples/nexus-spatial-discovery.md](https://github.com/msitarzewski/agency-agents/blob/main/examples/nexus-spatial-discovery.md)

采用要点：

- 将 `remember / recall / rollback / search` 变成一人公司的正式交接机制。
- Discovery 类任务允许 Research、Product、Design、Growth 并行产出，但必须经过 `Cross-Agent Synthesis`。
- 记忆必须附带 `department + stage + receiver` 标签，不能依赖隐式会话上下文。

### Seat Pack Memory Integration

主要来源：
[integrations/mcp-memory/README.md](https://github.com/msitarzewski/agency-agents/blob/main/integrations/mcp-memory/README.md)
[examples/workflow-with-memory.md](https://github.com/msitarzewski/agency-agents/blob/main/examples/workflow-with-memory.md)

采用要点：

- 上游仓库里的 memory integration 说明保留为 `employee pack` 的 prompt 模板来源，而不是当前架构唯一的 memory engine。
- 每个 seat pack 在生成时都应包含三类 memory 提示：
  session start recall
  key decision / deliverable remember
  handoff / rollback 规则
- prompt 层只负责告诉 agent “何时调用 memory”，真正的 scope、namespace、approval、promotion、versioning 由当前项目的 `Memory Fabric` 统一定义。
- 任何 seat pack 的 memory 能力都必须对齐正式命名空间：
  `agent_private`
  `department_shared`
  `company_shared`

## 4. OpenClaw workspace 编译输出

### 4.1 编译路径

当前正式编译链固定为：

```text
agency-agents
  -> PersonaSourceAdapter
  -> PersonaPack
  -> EmployeePackCompiler
  -> Employee Pack
  -> OpenClawWorkspaceCompiler
  -> OpenClawWorkspaceBundle
  -> OpenClaw native agent workspace
```

### 4.2 `OpenClawWorkspaceBundle` 最小内容

| 文件 | 作用 |
| --- | --- |
| `AGENTS.md` | 当前席位在公司中的边界、职责与协作对象 |
| `SOUL.md` | 人格、价值取向、沟通风格与决策语气 |
| `IDENTITY.md` | `VirtualEmployee` 与 `openclaw_agent_id` 的身份映射 |
| `BOOTSTRAP.md` | 当前席位启动时必须优先吸收的规则入口 |
| `SKILLS.md` | 当前席位可用专业 skills、通用 skills 与 skill policy 摘要 |
| `TOOLS.md` | 当前席位可用工具、禁止工具、使用原则 |
| `USER.md` | CEO / operator 关系、可见沟通约束、room policy 入口 |
| `HEARTBEAT.md` | 周期性 recurring work、trigger 与 cadence 说明 |

### 4.3 固定映射关系

- `agency-agents -> PersonaPack`
  只负责角色资产提炼。
- `PersonaPack -> Employee Pack`
  只负责席位级组合、memory/tool/sandbox hints。
- `Employee Pack -> EmployeeSkillPack / SkillManifest`
  负责把岗位能力编译成可验证的 skill catalog。
- `Employee Pack -> OpenClawWorkspaceBundle`
  负责把席位编译成 OpenClaw 原生可引导 workspace。
- `SkillManifest -> workspace-local native skills`
  负责把 skill catalog 物化成 OpenClaw 可发现的原生 skills。
- `OpenClaw native workspace`
  才是单个 agent 真正消费的运行时 bootstrap。

### Quality

主要来源：
[testing-evidence-collector.md](https://github.com/msitarzewski/agency-agents/blob/main/testing/testing-evidence-collector.md)
[testing-reality-checker.md](https://github.com/msitarzewski/agency-agents/blob/main/testing/testing-reality-checker.md)

采用要点：

- 逻辑上保持双层质量门：
  `Evidence`
  `Verdict`
- 组织上在 V1 收敛为 `Quality Lead` 单席位，避免破坏“每部门一个员工”的设定。
- V2 可以把该席位拆成两个独立员工，但不改动 `Quality` 部门接口。

## 4. 显式席位映射示例

### 示例 1：`Engineering Lead`

- 部门：`Engineering`
- 席位：`Engineering Lead`
- 组合来源：
  `Backend Architect + Frontend Developer + Rapid Prototyper`
- 适用场景：
  MVP 实现、跨前后端落地、快速验证、方案到代码交付。

这是第一个标准的 `composite employee pack`：上游角色分别擅长架构、实现与快速产出，但在 V1 的一人公司里，它们对外表现为一个技术负责人席位。

### 示例 2：`Quality Lead`

- 部门：`Quality`
- 席位：`Quality Lead`
- 组合来源：
  `Evidence Collector + Reality Checker`
- operating modes：
  `evidence`
  `verdict`

这是最关键的 V1 组合席位。它既保留双层质量逻辑，又避免在初版组织图里把 Quality 部门拆成多员工。

### 示例 3：`Trust & Compliance Lead`

- 部门：`Trust / Security / Legal`
- 席位：`Trust & Compliance Lead`
- 组合来源：
  `Legal Compliance Checker + Agentic Identity & Trust Architect + Identity Graph Operator`

这个席位默认不常驻运行，但在高风险任务、对外发布、数据敏感场景中按需激活。它体现的是治理能力的上游来源，而不是日常执行员工。

### 示例 4：`Operations Lead`

- 部门：`Business Operations`
- 席位：`Operations Lead`
- 组合来源：
  `Studio Operations + Finance Tracker`

该席位让“一人公司”不仅能交付产品，还能维持内部流程、预算和经营健康。

### 示例 5：`Chief of Staff`

- 部门：`Executive Office`
- 席位：`Chief of Staff`
- 组合来源：
  `Studio Producer + Senior Project Manager + Agents Orchestrator`
- memory profile：
  拥有自己的 `agent_private`；
  维护 `department:executive-office`；
  管理公司级 `company_shared` promotion 与 strategic recall。

这个席位是 memory 路由和 promotion 的默认中枢，因此它的上游 persona 组合不仅决定统筹风格，也决定 seat pack 如何触发 recall、checkpoint 和记忆提升。

## 5. V2 拆分策略

### 何时拆分复合席位

- 某个席位的 operating modes 已经稳定且负载明显分离。
- 某个席位需要同时承担互相制衡的职责，例如 `Quality` 的证据与放行。
- 某个席位的工具权限开始出现明显冲突，例如既要高风险写入又要独立审计。

### 拆分方式

- 保持 `VirtualDepartment` 不变。
- 将原有一个 `VirtualEmployee` 拆成多个同部门席位。
- `DepartmentSeatMap` 从一对一升级为一对多，但 `WorkflowRecipe` 的部门边界不变。
- 原先针对部门的路由仍然有效，只是在部门内部改由更细粒度的员工席位分工。

### 典型拆分案例

- V1：
  `Quality -> Quality Lead(evidence + verdict)`
- V2：
  `Quality -> Evidence Lead + Release Authority`

外部 recipe 仍然只感知 `Quality` 部门，不需要因为部门内部分工变化而重写整个系统。

## 6. Distribution Layer 边界

- 上游仓库中的 [integrations/README.md](https://github.com/msitarzewski/agency-agents/blob/main/integrations/README.md) 与 [scripts/convert.sh](https://github.com/msitarzewski/agency-agents/blob/main/scripts/convert.sh) 仍然只用于参考 `DistributionTarget` 设计。
- 一人公司模式下，分发对象不是“原始 persona 文件”，而是已经过 `DepartmentSeatMap` 编译后的 `employee pack`。
- 同一部门席位可以输出到多个目标：
  `claude-code`
  `openclaw`
  `cursor`
  `opencode`
  `aider`
  `windsurf`
- 分发层只处理产物格式与安装目标，不改写一人公司的部门语义和运行时路由。
- 分发产物应内含与 Memory Fabric 对齐的 seat-level memory instructions，但不直接内嵌具体 MCP server 绑定。

## 7. 维护策略

- 上游仓库变更优先影响 `PersonaPack` 和 `DepartmentSeatMap`，不直接改动主架构接口。
- 新角色进入当前方案前，先判断它属于：
  新部门；
  已有部门的新席位候选；
  现有席位的补充 PersonaPack；
  仅限 roadmap 的 specialized role。
- 文档维护顺序固定为：
  先更新组织附录；
  再更新主方案；
  最后更新接入策略与 seat map。
