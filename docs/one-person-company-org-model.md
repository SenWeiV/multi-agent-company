# One-Person Company 组织模型附录

本文专门定义 `one-person-company` 的组织图、席位、激活策略和经营 cadence。目标不是把系统写成抽象的多 agent 网络，而是让用户真的像一家 `AI 产品工作室` 的 CEO 一样操作这套系统。

## 1. 基本 operating model

### 角色关系

- `CEO`：
  负责人类目标、方向取舍、优先级和最终拍板。
- `Chief of Staff`：
  默认运营中枢，负责 intake、归一化、路由、同步、节奏和 executive summary。
- `Virtual Departments`：
  公司的正式部门边界，每个部门在 V1 只有一个虚拟员工席位。
- `Virtual Employees`：
  每个部门的唯一席位，既是组织入口，也是上游 PersonaPack 的承载体。

### 三种 CEO 交互方式

| 模式 | 说明 | 默认行为 |
| --- | --- | --- |
| `strategy` | CEO 提方向、问题、优先级 | 先到 `Chief of Staff` |
| `direct` | CEO 直接找某个部门 | 部门执行后必须回写 Executive Office |
| `override` | CEO 强制改变当前方向或节奏 | 立即生成 checkpoint 并更新 TaskGraph |

### 默认原则

- `Chief of Staff` 永远在线。
- 部门是正式边界，不能把所有事情都写成某个超级 agent。
- 每部门一个席位只是一人公司的组织策略，不是实现层的能力限制。

### CEO 日常交互方式

在真实公司里，CEO 不会每次都启动完整项目链。因此当前组织模型正式支持两类交互：

- `正式项目流程`：
  适用于多部门交付、明确产物、需要质量门和 checkpoint。
- `轻量局部流程`：
  适用于想法记录、快速咨询、单部门小任务、review、改向和升级处理。

默认交互模式固定为：

| mode | 默认参与范围 | 说明 |
| --- | --- | --- |
| `idea_capture` | `CEO + Chief of Staff` | 先记住，不急着拉起部门 |
| `quick_consult` | `CEO + 1 个部门` | 快速获得意见或建议 |
| `department_task` | `CEO + 1 个部门` | 给单部门一个小而明确的任务 |
| `formal_project` | `Chief of Staff + 核心部门链` | 正式项目流 |
| `review_decision` | `CEO + Chief of Staff + optional Quality/Product/Trust` | 基于已有证据做复核和拍板 |
| `override_recovery` | `CEO + Chief of Staff + 相关部门` | 停掉、改向、冻结、回滚 |
| `escalation` | `Chief of Staff + 相关部门 + optional CEO` | 处理冲突和高风险问题 |

## 2. V1 组织图

```text
CEO
  |
  +-- Executive Office
  |     `-- Chief of Staff
  |
  +-- Product
  |     `-- Product Lead
  +-- Research & Intelligence
  |     `-- Research Lead
  +-- Project Management
  |     `-- Delivery Lead
  +-- Design & UX
  |     `-- Design Lead
  +-- Engineering
  |     `-- Engineering Lead
  +-- Quality
  |     `-- Quality Lead
  +-- Growth & Marketing
  |     `-- Growth Lead
  +-- Sales & Partnerships
  |     `-- Partnerships Lead
  +-- Customer Success & Support
  |     `-- Customer Success Lead
  +-- Business Operations
  |     `-- Operations Lead
  `-- Trust / Security / Legal
        `-- Trust & Compliance Lead
```

## 3. 部门席位清单

| 部门 | Charter | V1 席位 | 上游 PersonaPack 来源 | 激活级别 | 默认参与流程 |
| --- | --- | --- | --- | --- | --- |
| Executive Office | 公司 intake、路由、综合、节奏管理 | `Chief of Staff` | `Studio Producer + Senior Project Manager + Agents Orchestrator` | always-on | 全部流程 |
| Product | 产品方向、优先级、版本取舍 | `Product Lead` | `Sprint Prioritizer` | always-on | Strategy、Build、Launch |
| Research & Intelligence | 趋势、竞品、市场、用户信号 | `Research Lead` | `Trend Researcher` | always-on | Strategy、Discovery、Build |
| Project Management | 任务图、依赖、范围、推进 | `Delivery Lead` | `Senior Project Manager + Project Shepherd` | always-on | Build、Launch |
| Design & UX | 用户研究、信息结构、体验方案 | `Design Lead` | `UX Researcher + UX Architect` | always-on | Discovery、Build |
| Engineering | 技术架构、实现、原型 | `Engineering Lead` | `Backend Architect + Frontend Developer + Rapid Prototyper` | always-on | Build |
| Quality | 证据采集、验收、放行 | `Quality Lead` | `Evidence Collector + Reality Checker` | always-on | Build、Launch |
| Growth & Marketing | 增长、品牌、分发、上线传播 | `Growth Lead` | `Growth Hacker + Brand Guardian` | on-demand | Launch、Discovery |
| Sales & Partnerships | 合作、外联、线索、商业机会 | `Partnerships Lead` | `Outbound Strategist + Account Strategist` | situational / expansion | Launch、Expansion |
| Customer Success & Support | 用户支持、反馈、留存、FAQ | `Customer Success Lead` | `Support Responder` | on-demand | Launch、Post-launch |
| Business Operations | 运营流程、预算、财务健康 | `Operations Lead` | `Studio Operations + Finance Tracker` | situational / expansion | Monthly review、Expansion |
| Trust / Security / Legal | 合规、身份、审计、风险控制 | `Trust & Compliance Lead` | `Legal Compliance Checker + Agentic Identity & Trust Architect + Identity Graph Operator` | situational / expansion | High-risk review、Launch |

### 预算责任与 heartbeat 分工

| 部门 | 预算责任 | 默认 heartbeat | 典型 recurring work |
| --- | --- | --- | --- |
| Executive Office | 监控公司级预算阈值、汇总跨部门成本与 override 请求 | 有 | daily sync、weekly review、exception routing |
| Product | 控制产品探索与需求变更带来的任务膨胀 | 按需 | roadmap review、priority refresh |
| Research & Intelligence | 控制调研任务投入与外部信息采样频率 | 有 | trend scan、competitor watch、signal digest |
| Project Management | 控制任务拆解粒度与交付节奏成本 | 有 | dependency check、delivery follow-up |
| Design & UX | 控制设计探索和验证成本 | 按需 | design review、artifact cleanup |
| Engineering | 控制实现与重试成本、工具调用强度 | 按需 | build check、integration follow-up |
| Quality | 控制测试、验证和复核成本 | 按需 | evidence refresh、release gate review |
| Growth & Marketing | 控制推广活动与内容分发预算 | 按需 | launch prep、content cadence |
| Sales & Partnerships | 控制外联、合作与线索处理成本 | 按需 | partner follow-up |
| Customer Success & Support | 控制支持工单与反馈处理投入 | 按需 | support digest、feedback routing |
| Business Operations | 维护预算口径、经营指标与成本健康 | 有 | budget review、ops reconciliation |
| Trust / Security / Legal | 维护高风险动作的合规成本与审计要求 | 按需 | policy check、risk review |

### V1 席位的技术承载方式

当前组织文档只保留核心 7 个默认激活部门的技术承载摘要，避免把组织附录扩写成完整底层实现文档。当前正式定位已经升级为：

- 每个核心席位不再只是“席位 + persona”；
- 而是“席位 + `OpenClaw agent` + workspace bundle + channel accounts + tool/sandbox profile”。

| 部门 | V1 席位 | `openclaw_agent_id` | 上游 persona 组合 | workspace bundle | channel accounts | tool / sandbox profile | 默认 workflow 承载 | 默认 memory scope |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Executive Office | `Chief of Staff` | `chief-of-staff` | `Studio Producer + Senior Project Manager + Agents Orchestrator` | `chief-of-staff/AGENTS.md + SOUL.md + IDENTITY.md + TOOLS.md + USER.md + HEARTBEAT.md` | `dashboard + feishu:chief-of-staff + slack(v2)` | `coordination-heavy / messaging / safe tools / sandbox-first` | `CEO Strategy Loop`、`Product Build Loop`、`Discovery / Synthesis Loop` | `agent_private + department_shared + company_shared` |
| Product | `Product Lead` | `product-lead` | `Sprint Prioritizer` | `product-lead/AGENTS.md + SOUL.md + IDENTITY.md + TOOLS.md + USER.md + HEARTBEAT.md` | `dashboard + feishu:product-lead + slack(v2)` | `product-analysis / docs / messaging / sandbox-first` | `CEO Strategy Loop`、`Product Build Loop` | `agent_private + department_shared + company_shared(authorized)` |
| Research & Intelligence | `Research Lead` | `research-lead` | `Trend Researcher` | `research-lead/AGENTS.md + SOUL.md + IDENTITY.md + TOOLS.md + USER.md + HEARTBEAT.md` | `dashboard + feishu:research-lead + slack(v2)` | `research / browser / retrieval / sandbox-first` | `CEO Strategy Loop`、`Discovery / Synthesis Loop` | `agent_private + department_shared + company_shared(authorized)` |
| Project Management | `Delivery Lead` | `delivery-lead` | `Senior Project Manager + Project Shepherd` | `delivery-lead/AGENTS.md + SOUL.md + IDENTITY.md + TOOLS.md + USER.md + HEARTBEAT.md` | `dashboard + feishu:delivery-lead + slack(v2)` | `planning / scheduling / trace / sandbox-first` | `Product Build Loop` | `agent_private + department_shared + company_shared(authorized)` |
| Design & UX | `Design Lead` | `design-lead` | `UX Researcher + UX Architect` | `design-lead/AGENTS.md + SOUL.md + IDENTITY.md + TOOLS.md + USER.md + HEARTBEAT.md` | `dashboard + feishu:design-lead + slack(v2)` | `design / research / artifact-safe / sandbox-first` | `Product Build Loop`、`Discovery / Synthesis Loop` | `agent_private + department_shared + company_shared(authorized)` |
| Engineering | `Engineering Lead` | `engineering-lead` | `Backend Architect + Frontend Developer + Rapid Prototyper` | `engineering-lead/AGENTS.md + SOUL.md + IDENTITY.md + TOOLS.md + USER.md + HEARTBEAT.md` | `dashboard + feishu:engineering-lead + slack(v2)` | `coding/full / review / sandbox or host-by-policy` | `Product Build Loop` | `agent_private + department_shared + company_shared(authorized)` |
| Quality | `Quality Lead` | `quality-lead` | `Evidence Collector + Reality Checker` | `quality-lead/AGENTS.md + SOUL.md + IDENTITY.md + TOOLS.md + USER.md + HEARTBEAT.md` | `dashboard + feishu:quality-lead + slack(v2)` | `evidence / review / approval-aware / sandbox-first` | `Product Build Loop`，V1 内部保持 `evidence -> verdict` 双模式 | `agent_private + department_shared + company_shared(quality-authorized)` |

说明：

- `Research & Intelligence`、`Project Management`、`Business Operations` 是 V1 默认最适合绑定 heartbeat 的部门，因为它们更偏周期性检查、扫描和整理。
- `Engineering`、`Design & UX`、`Quality` 默认以 `event trigger + manual trigger` 为主，不用常驻 heartbeat 驱动。
- `Business Operations` 虽然不是 V1 常驻执行部门，但在预算治理上是正式责任部门，应在文档中被保留为未来默认 owner。
- `Chief of Staff`、`Product Lead` 等核心席位在 V1 的正式技术落点是：
  `EmployeePack -> OpenClawWorkspaceBundle -> OpenClaw native agent -> dashboard / feishu channel accounts`。

## 4. 部门 Memory 权限与命名空间

完整 memory 设计定义在 [memory-fabric-design.md](/Users/weisen/Documents/small-project/multi-agent-company/docs/memory-fabric-design.md)。这里仅说明组织层视角下每个部门拥有哪些 namespace、默认写权限和 promotion 审批关系。

### 通用规则

- 每个席位默认都有一个 `agent_private` namespace。
- 每个部门默认都有一个 `department_shared` namespace，即使 V1 只有一个席位也不省略。
- 每个席位默认可读：
  自己的 `agent_private`
  所属部门的 `department_shared`
  被授权的 `company_shared`
- `agent_private` 允许自动写入。
- `department_shared` 的 promotion 默认需要部门席位确认；高影响项可升级给 `Chief of Staff`。
- `company_shared` 的写入和 promotion 默认由 `Chief of Staff` 管理；高影响项再交 CEO。

### 默认 memory profile

| 部门 | 私有 namespace | 部门共享 namespace | 公司共享访问 | 自动写入 | 共享升级审批 |
| --- | --- | --- | --- | --- | --- |
| Executive Office | `employee:chief-of-staff` | `department:executive-office` | full strategic access | `agent_private` | `Chief of Staff` / CEO |
| Product | `employee:product-lead` | `department:product` | 产品、战略、公司事实 | `agent_private` | `Product Lead` / `Chief of Staff` |
| Research & Intelligence | `employee:research-lead` | `department:research-intelligence` | 市场、产品、战略事实 | `agent_private` | `Research Lead` / `Chief of Staff` |
| Project Management | `employee:delivery-lead` | `department:project-management` | 任务图、checkpoint、公司计划 | `agent_private` | `Delivery Lead` / `Chief of Staff` |
| Design & UX | `employee:design-lead` | `department:design-ux` | 产品事实、设计约束、授权研究结论 | `agent_private` | `Design Lead` / `Chief of Staff` |
| Engineering | `employee:engineering-lead` | `department:engineering` | 产品、架构、授权质量结论 | `agent_private` | `Engineering Lead` / `Chief of Staff` |
| Quality | `employee:quality-lead` | `department:quality` | 全局 evidence、checkpoint、相关 policy | `agent_private` | `Quality Lead` / `Chief of Staff` |
| Growth & Marketing | `employee:growth-lead` | `department:growth-marketing` | 授权产品、品牌、上线材料 | `agent_private` | `Growth Lead` / `Chief of Staff` |
| Sales & Partnerships | `employee:partnerships-lead` | `department:sales-partnerships` | 授权 GTM、产品摘要、合作材料 | `agent_private` | `Partnerships Lead` / `Chief of Staff` |
| Customer Success & Support | `employee:customer-success-lead` | `department:customer-success-support` | 授权产品、FAQ、问题处理历史 | `agent_private` | `Customer Success Lead` / `Chief of Staff` |
| Business Operations | `employee:operations-lead` | `department:business-operations` | 授权经营指标、财务摘要、流程 policy | `agent_private` | `Operations Lead` / `Chief of Staff` |
| Trust / Security / Legal | `employee:trust-compliance-lead` | `department:trust-security-legal` | 受控高敏 company memory | `agent_private` | `Chief of Staff` / CEO |

### 组织层的 promotion 边界

- 部门席位可以自动沉淀 `L1 private auto-learning`。
- 部门席位可以发起 `L2 department promotion`，但不允许静默完成。
- 任何进入 `company_shared` 的 procedural memory、policy、战略事实，都视为公司制度层内容，必须由 `Chief of Staff` 管理。

## 5. 激活策略

### Always-on

- Executive Office
- Product
- Research & Intelligence
- Project Management
- Design & UX
- Engineering
- Quality

### On-demand

- Growth & Marketing
- Customer Success & Support

### Situational / Expansion

- Sales & Partnerships
- Business Operations
- Trust / Security / Legal

### 激活规则

- 任何新任务默认先进入 Executive Office。
- `idea_capture` 默认不激活业务部门，除非 Chief of Staff 判断需要验证。
- `quick_consult` 与 `department_task` 默认只激活一个业务部门。
- 只要任务涉及产品判断，就激活 Product。
- 只要任务涉及事实不确定性或外部信号，就优先考虑激活 Research & Intelligence。
- 只要任务涉及交付，就必须进入 Project Management、Engineering、Quality。
- 只有在上线、推广、反馈、经营、合规等场景，才激活后四类扩展部门。

### flow-to-department 激活规则

| flow | 默认激活 |
| --- | --- |
| `idea_capture` | `Executive Office` |
| `quick_consult` | `Executive Office + 1 target department` |
| `department_task` | `Executive Office + 1 target department` |
| `formal_project` | `Executive Office + Product + PM + Design + Engineering + Quality`，按需要再加其他部门 |
| `review_decision` | `Executive Office + optional Product / Quality / Trust` |
| `override_recovery` | `Executive Office + related departments` |
| `escalation` | `Executive Office + related departments + optional CEO` |

## 6. 经营 cadence

| 节奏 | 负责人 | 默认输出 |
| --- | --- | --- |
| `daily sync` | Chief of Staff | 当日重点、阻塞、部门激活状态 |
| `weekly review` | CEO + Chief of Staff + Product Lead | 本周进展、优先级调整、下周焦点 |
| `monthly checkpoint` | CEO + Executive Office | 公司阶段总结、指标、风险、rollback 点 |
| `strategy refresh` | CEO + Product + Research | 方向更新、机会窗口、资源再分配 |

### cadence 设计原则

- `daily sync` 服务执行，不做长篇战略讨论。
- `weekly review` 是 CEO 做小范围方向修正的主入口。
- `monthly checkpoint` 是最重要的 `company checkpoint`，默认保留为可 rollback 的里程碑。
- `strategy refresh` 不是每次都开，只有当外部环境、产品假设或资源条件变化明显时才触发。

## 7. Quality 部门的 V1 特殊处理

`Quality` 是 V1 唯一明确采用“单席位、双逻辑”的部门。

- `Evidence mode`：
  负责测试、观察、截图、spec quote、问题清单。
- `Verdict mode`：
  负责 GO / NO-GO、上线建议、回退建议。

这样设计的原因是：

- 保留 `Evidence Collector + Reality Checker` 的双层质量逻辑。
- 不破坏“每部门一个虚拟员工席位”的组织约束。
- 为 V2 拆分成双员工结构预留兼容路径。

## 8. 默认路由与升级规则

### 默认路由

```text
CEO -> Chief of Staff -> relevant departments -> synthesis -> CEO
```

### 直达部门

```text
CEO -> department -> Chief of Staff sync-back -> TaskGraph update
```

### 升级触发

- 同一任务超过 3 次 retry。
- `Quality Lead` 给出 NO-GO。
- 多个部门给出冲突结论。
- 涉及财务、法律、数据或高风险外部动作。

以上任一条件触发时，必须升级回 `Chief of Staff`，必要时再升级到 CEO。

## 9. 典型场景

### 场景 0：先记一个想法

```text
CEO
  -> Chief of Staff
  -> IdeaBrief
  -> CEO intent memory
```

### 场景 0.5：直接问某个部门

```text
CEO
  -> department
  -> ConsultNote / TaskResult
  -> Chief of Staff sync-back
```

### 场景 A：做一个 AI 产品 MVP

```text
CEO
  -> Chief of Staff
  -> Product Lead
  -> Research Lead
  -> Delivery Lead
  -> Design Lead
  -> Engineering Lead
  -> Quality Lead
  -> CEO review
```

### 场景 B：准备上线和推广

```text
CEO
  -> Chief of Staff
  -> Product Lead
  -> Growth Lead
  -> Customer Success Lead
  -> optional Partnerships Lead
  -> Quality Lead
  -> CEO approval
```

### 场景 C：处理高风险发布

```text
CEO
  -> Chief of Staff
  -> Engineering Lead
  -> Quality Lead
  -> Trust & Compliance Lead
  -> CEO final decision
```

## 10. V2 扩展方向

- `Quality Lead` 拆成 `Evidence Lead + Release Authority`
- `Engineering Lead` 拆成 `Architecture + Implementation + Platform`
- `Growth Lead` 拆成 `Growth + Brand + Content`
- `Business Operations` 从流程/财务进一步拆成 `Operations + Finance`

V2 的原则不是增加更多部门，而是在保留部门边界的前提下，把高负载席位拆成更细粒度的虚拟员工。
