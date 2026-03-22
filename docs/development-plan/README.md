# One-Person Company 正式开发方案总览

本目录用于把现有设计文档整理成开发视角的正式实施方案。这里不新增产品概念，不改动现有接口定义，也不进行任何实际开发；目标是让开发者和未来执行 agent 只看本目录，就能明确当前 `V1.5` 要做什么、`V1.8` 预埋什么、按什么顺序做、依赖关系是什么、如何验收。

当前 `Operator Console` 的开发方案定义，已经扩展为 `Web Dashboard + Feishu` 双表面交互设计；Dashboard 仍是主控制面，Feishu 仍是协作与会话表面。当前正式架构已经进一步收敛为：
`OpenClaw native agent plane + LangGraph company workflow orchestration + current Memory Fabric + Feishu visible orchestration`

## 1. 目标

- 将现有 `one-person-company` 设计翻译为一套可执行的开发方案。
- 以 `V1.5` 封板为绝对重点，覆盖后续 `V1.8 / V2` 的演进边界。
- 保持当前主栈与概念层定义不变：
  `one-person-company` 仍是产品概念，
  `multi-agent-company` 仍是底层引擎名。

## 2. V1 交付形态

- 系统形态固定为：
  `Python 单体后端 + 简单 Operator Console`
- 开发环境固定为：
  `本机 Docker 容器栈`
  所有依赖安装、命令执行、服务启动、测试和调试都在容器内完成；
  Host 只承担 `Docker + IDE/CLI`。
- 默认主栈固定为：
  `OpenClaw + LangGraph + agency-agents + current Memory Fabric + Feishu visible orchestration`
- 默认只激活核心 7 部门：
  `Executive Office`
  `Product`
  `Research & Intelligence`
  `Project Management`
  `Design & UX`
  `Engineering`
  `Quality`
- 默认重点实现 4 类主交互：
  `idea_capture`
  `quick_consult`
  `department_task`
  `formal_project`
- 同时补入最小 control-plane 能力：
  `GoalLineage`
  `BudgetPolicy`
  `TriggerPolicy`
  `WorkTicket`
- 同时具备 3 类最小治理能力：
  `review_decision`
  `override_recovery`
  `escalation`

## 3. 与现有设计文档的关系

本目录不是新的产品设计 source of truth，而是开发执行层的整理版。上游设计仍以以下文档为准：

- [主方案设计](../multi-agent-development-plan.md)
- [Memory Fabric 设计](../memory-fabric-design.md)
- [CEO 交互流程设计](../ceo-agent-interaction-flows.md)
- [组织模型附录](../one-person-company-org-model.md)
- [公开库整合方案](../public-library-integration-plan.md)
- [agency-agents 上游接入策略](../agency-agents-integration-strategy.md)
- [OpenClaw Native Agent Plane](../openclaw-native-agent-plane.md)

## 4. 文档导航

### 当前正式路线

- `V1.5`
  只围绕核心 7 个 bot、Feishu、OpenClaw、native skills、Dashboard `Agents` 模块、消息卡审批、`Launch / Ops / Support Room`、repeat recall 封板。
- `V1.8`
  只引入 `Pulse / Trigger Engine`、`Relationship Graph`、`Skill Creator + Eval Loop`、`CEO Visible Event Stream`、memory promotion / policy guard。
- 当前明确排除：
  `Company Plaza`
  `Growth / Support` 独立 bot
  `Slack`
  `L2 department promotion`
  `Quality` 双席位拆分

- [V1 具体实现开发方案](./v1-execution-plan.md)
  V1 的开发主入口。说明目标、范围、优先级、交付顺序、风险与非目标。
- [系统架构与模块拆解](./system-architecture-and-modules.md)
  说明系统模块、内部适配层、关键对象、依赖关系、数据流和实现边界。
- [开发路线图与周迭代计划](./roadmap-and-iteration-plan.md)
  固化 Week 1-8 的开发安排，以及 `V1.5 / V1.8 / V2` 的后续路径。
- [V1.8 Enhancement Roadmap](./v1.8-enhancement-roadmap.md)
  固化去掉 `Company Plaza` 后的 `V1.8` 目标、最小能力、依赖关系与非目标。
- [验收标准与测试场景](./acceptance-and-test-scenarios.md)
  收敛正式验收场景、质量门、memory scope、checkpoint/rollback 和公开库边界检查。
- [前端 Dashboard 与飞书交互方案](./frontend-and-feishu-interaction-design.md)
  定义 `Web Dashboard + Feishu` 的双表面模型、房间策略、会话边界和版本路线。
- [Feishu Visible Orchestration Plan](./feishu-visible-orchestration-plan.md)
  定义 Feishu 的 mention dispatch、visible-room fan-out、session binding 与 transcript mirror。
- [Feishu Group Interruption And Run Supersede Plan](./feishu-group-interruption-run-supersede-plan.md)
  定义群聊中用户中途插话时的 thread 复用、run supersede、stale reply 丢弃与多 bot 重排规则。
- [Feishu Group Interruption Implementation Breakdown](./feishu-group-interruption-implementation-breakdown.md)
  把群聊中断方案继续拆成模块、字段、事件和实施顺序。
- [V1 本机运行与排障手册](./v1-local-ops-runbook.md)
  固化 Dashboard、OpenClaw Gateway、Feishu 长连接的本机启动、验证和排障路径。
- [V1.5 Feishu 全链路联调清单](./v1.5-feishu-live-regression-checklist.md)
  固化真实 Feishu 单聊、群聊、接棒、repeat recall、消息卡审批的 live 回归步骤。
- [V1.5 Release Checklist](./v1.5-release-checklist.md)
  固化 `V1.5` 封板前的正式签收项。
- [V1.5 封板状态报告](./v1.5-freeze-report.md)
  记录当前封板进度、live 证据、自动化结果与剩余风险。

## 4.1 Live Signoff 工具

- `python3 scripts/live_signoff.py`
  运行 `V1.5` 最终 live signoff 自动检查，核对 core-7、native skills、room templates、gateway health 与最近运行证据。
- `python3 scripts/live_signoff.py --json > .runtime/live-signoff-report.json`
  导出结构化 signoff 结果，作为封板归档证据。

## 5. V1 优先级

### P0

- CEO 指令输入与 `InteractionMode` 识别
- `Chief of Staff` 路由与部门激活
- `idea_capture / quick_consult / department_task / formal_project`
- `TaskGraph`、`RunTrace`、最小 `Checkpoint`
- `GoalLineage`、最小预算治理、`scheduled_heartbeat / event trigger`
- `WorkTicket` 作为统一工作项视图
- `agent_private / department_shared / company_shared` 的 V1 可用形态
- `Quality Lead` 的单席位双模式

### P1

- `review_decision`
- `override_recovery`
- `escalation`
- `OpenClaw native agent provisioning`
- `Feishu mention dispatch + visible-room fan-out`
- Operator Console 的 run 列表、任务状态、artifact 和 checkpoint 查看

### 延后

- `Launch / Growth Loop`
- 扩展部门常态化参与
- `L2 department promotion`
- 双员工 `Quality` 部门
- 正式产品前台、完整多租户和复杂身份体系

## 6. 固定边界

- 开发不直接依赖 Host 本机 Python/Node/数据库环境。
- 默认使用一个主开发容器承载代码执行，并通过同一 Docker 栈提供依赖服务容器。
- `agency-agents` 只进入资产层，不承担 scheduler/runtime 角色。
- `OpenClaw` 进入 agent plane，不替代公司组织模型或治理层。
- `LangGraph` 只进入 company workflow orchestration，不替代单 agent runtime。
- 当前 `Memory Fabric` 仍是长期治理真相源。
- `Chief of Staff`、`VirtualDepartment`、`Memory Fabric`、`ApprovalGate` 仍由本项目定义。
- `V1.5 = Feishu + OpenClaw + native skills + Dashboard Agents`
- `V1.8 = trigger / relationship / controlled self-evolution / visible event stream`
- `V2 = Slack`
