# “One-Person Company” 概念升级研究摘要

基于 [ideas.md](/Users/weisen/Documents/small-project/multi-agent-company/ideas.md)、当前文档体系，以及官方仓库 [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) 的 README、examples、specialized、integrations 等一手材料整理。本文将 `one-person-company` 定义为上层产品与组织叙事，将 `multi-agent-company` 保留为底层多智能体 orchestration / runtime 引擎名。

## 结论

### 1. `AI company -> one-person-company` 的概念演进成立

- 原始 [ideas.md](/Users/weisen/Documents/small-project/multi-agent-company/ideas.md) 已多次出现 `AI company`、`CEO Agent`、`team layer`、`OpenClaw 是 runtime 不是 agent OS` 等表述。这说明项目从一开始就不只是“几个 agent 串起来”，而是在寻找“像公司一样运作的 agent operating model”。
- `one-person-company` 不是推翻现有方案，而是把当前系统升级成更符合用户心智的产品概念。用户不是“使用一个多智能体系统的人”，而是“这家虚拟公司的 CEO”。
- 这一升级与 [agency-agents README](https://github.com/msitarzewski/agency-agents/blob/main/README.md) 的 division/role 结构高度兼容。官方仓库已经证明：角色资产可以天然按部门组织，而不是只能按 planner / worker / critic 三段式来写。

### 2. 顶层叙事应该变，但底层引擎不需要推翻

- `multi-agent-company` 继续承担平台中立的 `TaskGraph`、`WorkflowRecipe`、`Runtime Adapter`、`Memory`、`ToolContract`、`RunTrace` 等系统责任。
- 新增的只是三层更靠近用户和组织的概念：
  `Human CEO Layer`
  `Executive Office Layer`
  `Virtual Department Layer`
- 这意味着升级重点是命名、组织图、路由入口、部门席位和经营 cadence，而不是重写 agent 之间的基本逻辑关系。

### 3. 初版应采用“完整公司图谱 + 分层激活”

- 公司原型最适合定义为 `AI 产品工作室`。它比传统大厂架构更轻，也比纯 agency 更适合长期经营一个产品或小型业务。
- 初版组织图应完整，但激活分层：
  `always-on`：Executive Office、Product、Research & Intelligence、Project Management、Design & UX、Engineering、Quality
  `on-demand`：Growth & Marketing、Customer Success & Support
  `situational / expansion`：Sales & Partnerships、Business Operations、Trust / Security / Legal
- “部门齐全”不等于“所有部门常驻执行”。V1 需要的是完整公司语义，而不是完整运营负担。

### 4. “每部门 1 个员工”应解释为“单席位，可组合 PersonaPack”

- V1 组织上每个部门只放一个虚拟员工席位，便于理解、控制成本和保持路由清晰。
- 实现上不应把这个席位限制成单一 persona。一个 `VirtualEmployee` 可以绑定多个上游 `PersonaPack`，形成 `composite employee pack`。
- 这种设计既满足“初版简洁”，又不阻断未来从“单席位”升级到“多员工部门”的能力。

### 5. 质量门和记忆系统要改写成“公司语义”，但逻辑保持不变

- `Evidence Collector + Reality Checker` 的双层质量门仍然是对的，只是要从“reviewer loop”改写成 `Quality` 部门的双 operating mode。
- `remember / recall / rollback / search` 仍然是记忆式 handoff 的核心模式，但要改写为：
  `CEO intent memory`
  `department handoff memory`
  `company checkpoint`
  `board-style evidence package`
- `Chief of Staff` 必须成为默认中枢，否则 CEO 直达各部门会很快退化成散乱会话。

### 6. 需要明确区分“产品叙事”和“真实系统能力”

- “一人公司”是上层产品叙事，不代表系统在 V1 就具备完全自治的长期经营能力。
- 文档中不能把“CEO”“部门”“虚拟员工”写成纯 branding，也不能把它们误写成已经替代调度器、数据库、策略引擎的技术能力。
- 正确边界是：
  `one-person-company` 负责用户心智、组织模型、操作入口。
  `multi-agent-company` 负责执行、治理、记忆、观测与分发。

## 依据

### 来自原始问题空间的信号

- [ideas.md](/Users/weisen/Documents/small-project/multi-agent-company/ideas.md) 已经多次提出 `AI company`、`CEO Agent`、`Research Team / Engineering Team / Marketing Team / Operations Team` 等组织化结构。
- 同一份原稿也多次强调 `OpenClaw 本身只是 agent runtime，不是 agent OS`。这与当前“保留底层引擎、升级上层操作模型”的方向一致。
- 原稿里的核心愿景并不是“再加几个 agent”，而是把 agent 系统组织成真正可经营、可协调、可分工的结构。

### 来自 `agency-agents` 官方仓库的支撑

- [README](https://github.com/msitarzewski/agency-agents/blob/main/README.md) 用 `division -> role` 方式组织上游资产，说明“部门化组织”是成熟的角色编排入口。
- [workflow-startup-mvp.md](https://github.com/msitarzewski/agency-agents/blob/main/examples/workflow-startup-mvp.md) 和 [workflow-with-memory.md](https://github.com/msitarzewski/agency-agents/blob/main/examples/workflow-with-memory.md) 说明：真实工作流天然适合写成“跨角色 handoff”，而不是扁平任务列表。
- [agents-orchestrator.md](https://github.com/msitarzewski/agency-agents/blob/main/specialized/agents-orchestrator.md) 提供了“控制面角色”的模式，这非常适合映射为 `Executive Office` 而不是直接当 scheduler。
- [testing-evidence-collector.md](https://github.com/msitarzewski/agency-agents/blob/main/testing/testing-evidence-collector.md) 与 [testing-reality-checker.md](https://github.com/msitarzewski/agency-agents/blob/main/testing/testing-reality-checker.md) 为 `Quality` 部门提供了天然的双逻辑结构。
- [integrations/mcp-memory/README.md](https://github.com/msitarzewski/agency-agents/blob/main/integrations/mcp-memory/README.md) 里的 `remember / recall / rollback / search` 模式，可以直接吸收到“一人公司”的交接与复盘机制里。

### 对现有方案的直接影响

- 当前 [multi-agent-development-plan.md](/Users/weisen/Documents/small-project/multi-agent-company/docs/multi-agent-development-plan.md) 已有平台中立架构、治理、记忆与 workflow recipe，但主叙事仍偏“多智能体系统”。
- 当前 [agency-agents-integration-strategy.md](/Users/weisen/Documents/small-project/multi-agent-company/docs/agency-agents-integration-strategy.md) 已经把官方仓库定义为上游资产层，但还没有升级为“部门席位映射”。
- 因此本次变化的本质不是新增更多底层机制，而是把现有机制映射到完整的公司 operating model 上。

## 建议

### 公开库选型结论

- 当前最适合作为文档默认主栈的组合是：
  [OpenClaw](https://docs.openclaw.ai/) + [LangGraph](https://github.com/langchain-ai/langgraph) + [agency-agents](https://github.com/msitarzewski/agency-agents) + 当前项目自定义 `Memory Fabric`
- 选择理由：
  `OpenClaw` 最适合承接单 agent runtime、skills、tools、sessions、sandbox 与 provider/model routing；
  `LangGraph` 最适合承接公司级图式编排、长流程状态和 checkpoint；
  `agency-agents` 最适合承接 division、role、workflow 和 quality gate 的上游资产；
  当前项目 `Memory Fabric` 最适合继续承接长期记忆治理与 checkpoint / approval / supersede。
- 不进入当前主栈但保留为 future path 的公开库：
  [CrewAI](https://github.com/crewAIInc/crewAI)
  [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
  [CAMEL](https://github.com/camel-ai/camel)
  [full-stack-ai-agent-template](https://github.com/vstorm-co/full-stack-ai-agent-template)
- 当前默认判断是：
  `CrewAI` 更适合原型/对照，不作为当前第一核心引擎；
  `Microsoft Agent Framework` 更适合作为未来更重的企业级替代路线；
  `CAMEL` 更适合作为 workforce/society 研究方向；
  `full-stack-ai-agent-template` 更适合作为未来产品壳层，而不是公司操作系统内核。

- 将当前文档体系升级为四件套：
  `研究摘要`
  `主方案`
  `上游接入策略`
  `组织模型附录`
- 主方案改名为 `One-Person Company：用户担任 CEO 的虚拟公司操作系统`，但文中保留一节明确说明：`multi-agent-company` 是底层引擎名。
- 在主方案和组织附录中固定 12 个部门、默认席位、激活级别和经营 cadence，避免继续停留在抽象的 “team layer”。
- 在接口层新增 `CompanyProfile`、`CEOCommand`、`VirtualDepartment`、`VirtualEmployee`、`ExecutiveRoutingPolicy`、`CompanyCadence`、`DepartmentSeatMap`。
- 在接入策略文档里，把 `agency-agents` 从“角色来源”进一步写清成“部门席位的上游 PersonaPack 来源”，并给出至少 3 个明确映射示例。
- Quality 保持双逻辑，但在 V1 先采用“单部门、单席位、双模式”的组织写法，避免和“每部门一个员工”冲突。

### Paperclip benchmark

- 截至 **2026-03-13**，[`paperclipai/paperclip`](https://github.com/paperclipai/paperclip/blob/master/README.md) 已经公开验证了“公司级 orchestration / control plane”这条叙事，不再只是概念猜想。
- 当前方案应把它定位为：
  外部 benchmark
  能力参考源
  而不是当前主栈依赖。
- 对现有文档最值得吸收的四类能力是：
  `Goal Lineage`
  `Budget Governance`
  `Heartbeat + Event Trigger`
  `WorkTicket`
- 不建议吸收的部分是：
  `zero-human company` 主叙事、
  对自然对话入口的弱化、
  单 Node 进程和嵌入式 Postgres 这类实现假设。

### OpenClaw native agent plane

- 当前研究结论已经从“OpenClaw 是 runtime 不是 agent OS”进一步收敛到：
  `OpenClaw` 适合作为当前项目的正式 `agent plane`。
- 当前项目不应继续长期维护“自管 prompt + 自管 provider 调用”的 agent 对话层，而应把单 agent 执行、skills、tools、sessions、sandbox 收敛到 OpenClaw 原生能力。
- 与此同时，`Chief of Staff`、`VirtualDepartment`、`WorkTicket`、`Memory Fabric`、`Checkpoint` 仍然属于当前项目的 `company control plane`，不下沉给 OpenClaw。

### Clawith 借鉴取舍

- 可借鉴：
  `persistent identity`
  `Pulse / Trigger`
  `self-evolution eval`
- 不借鉴：
  `Company Plaza`
- 当前项目的改造方向：
  用 `CEO Visible Event Stream` 承接异步状态流，而不是引入 agent 社交广场。

### Feishu V1 / Slack V2 结论

- `Feishu V1` 可行，但前提是：
  当前项目必须实现 `visible-room fan-out`，而不是直接把 OpenClaw shared groups 当成解决方案。
- 原因：
  你要求的单提及、多提及、可见 agent-to-agent、完整 trace mirror，需要项目内的 mention dispatch 和 visible room policy。
- `Slack V2` 是更简单稳定的企业协作通道，原因是：
  OpenClaw 官方对 Slack 的企业协作支持更成熟，后续多 agent channel/thread 协作更容易落地。

## 待确认

- `one-person-company` 是否未来会成为对外产品名，还是先只作为内部方案与文档名使用。
- `Research & Intelligence` 是否在实现层独立成单独部门，还是先在 Product 下以 seat 方式兼任。
- `Quality` 部门何时从单席位、双模式升级为双员工结构。
- `Sales & Partnerships`、`Business Operations`、`Trust / Security / Legal` 在第一轮实现里是只保留文档级席位，还是同时纳入可调用的运行时角色池。
