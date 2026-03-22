# OpenClaw Native Agent Plane 定位文档

本文定义 `OpenClaw` 在 `one-person-company / multi-agent-company` 中的正式定位。它不是当前项目的“模型配置插件”，而是单个 agent 的原生能力层。

## 1. 结论

- `OpenClaw = agent plane`
- 当前项目 = `company control plane / governance / Memory Fabric / visible communication orchestration`
- `LangGraph` = `company workflow orchestration`
- `agency-agents` = `persona / workflow asset source`

固定边界：

- `OpenClaw` 承接单 agent runtime、skills、tools、sessions、sandbox、provider/model routing。
- 当前项目继续承接：
  `VirtualDepartment`
  `VirtualEmployee`
  `WorkTicket`
  `TaskGraph`
  `RunTrace`
  `Checkpoint`
  `Memory Fabric`
  `Approval`
  `Feishu / Slack visible communication orchestration`

## 2. 为什么不是“只读模型配置”

当前方案不再把 OpenClaw 仅仅视为：

- 一个 OpenAI-compatible provider gateway
- 一个 prompt 模板容器
- 一个用于加载 `identity / soul` 的配置层

正式目标是：

- 每个 `VirtualEmployee` 都映射到一个真实 `OpenClaw agentId`
- 每个 agent 都有独立 workspace、agentDir、sessions、tool/sandbox policy
- 每个 agent 的人格、身份、工具、heartbeat、channel account 都通过 OpenClaw 原生 bootstrap 文件承接
- 当前正式 provision 范围只包含 core-7
- Dashboard 是项目侧 source of truth，Control UI 是同步后的观察面

## 3. Agent Plane / Company Plane 分工

| 层 | 责任 |
| --- | --- |
| `OpenClaw Agent Plane` | 单 agent 的原生执行、会话、技能、工具、sandbox |
| `Company Control Plane` | CEO 路由、部门激活、工单、任务图、治理、记忆、审批 |
| `Visible Communication Orchestration` | Feishu / Slack 的 mention dispatch、room policy、可见 transcript |

固定规则：

- 当前项目不再把“直接调模型”当成长期 agent runtime。
- Dashboard / Feishu / Slack 的消息都应通过 `OpenClawGatewayAdapter` 触发真实 agent 执行。
- 当前项目仍保留外层 `ConversationThread / WorkTicket / RunTrace`，不让 channel 语义直接等于 OpenClaw session。

## 4. OpenClaw 原生能力面

当前方案默认吸收的 OpenClaw 原生能力包括：

- agent workspace bootstrap
- native sessions
- native tools / skills
- sandbox policy
- provider/model routing
- channel-compatible runtime
- workspace-local native skills

V1 不要求一次性开放 OpenClaw 全部生态插件，但文档层必须默认：

- 新增能力优先放进 OpenClaw 原生 agent plane
- 而不是继续堆叠到当前项目自定义对话层

## 5. `OpenClawWorkspaceBundle`

每个核心席位都应从 `EmployeePack` 编译出一个 `OpenClawWorkspaceBundle`，最小内容固定为：

- `AGENTS.md`
- `SOUL.md`
- `IDENTITY.md`
- `BOOTSTRAP.md`
- `SKILLS.md`
- `TOOLS.md`
- `USER.md`
- `HEARTBEAT.md`

映射链固定为：

```text
agency-agents
  -> PersonaPack
  -> EmployeePack
  -> OpenClawWorkspaceBundle
  -> OpenClaw native agent
```

## 6. 与 Memory Fabric 的边界

- `OpenClaw session/context`
  只负责 agent 的短期会话与运行态上下文。
- 当前 `Memory Fabric`
  负责长期公司记忆、promotion、approval、rollback、checkpoint refs。

默认做法：

- OpenClaw 通过工具桥访问 memory
- 不把完整公司记忆硬拼进 prompt
- 不让 OpenClaw session 直接替代 `agent_private / department_shared / company_shared`

## 7. Native Skill Registry 与项目 Skill Catalog

- `OpenClaw bundled/native skill registry`
  负责 runtime 可发现、可执行的原生 skills。
- `项目 skill catalog`
  负责 GitHub 来源、license、install/verify metadata 与岗位级 skill pack。
- `workspace-local native skill export`
  是当前项目把 skill catalog 物化到 OpenClaw agent workspace 的正式运行时落地点。

固定规则：

- 每个 skill 都应以 workspace-local native skill folder 形式进入 agent workspace
- `SKILLS.md` 负责说明和对齐，不替代 OpenClaw 原生 skill 发现
- native skill 的 source / install / discovery / invocation / result 必须全量验证

## 8. 与 Feishu / Slack 的关系

- `Feishu V1`
  继续由当前项目承接 visible-room fan-out、mention dispatch 与 transcript mirror。
- `Slack V2`
  作为更简单稳定的企业协作通道进入第二阶段。
- OpenClaw 原生 channel 能力可复用，但不能直接替代当前项目对“CEO 可见 agent-to-agent”的治理约束。

## 9. 正式对象

本轮文档升级后，以下对象成为正式概念：

- `OpenClawAgentBinding`
- `OpenClawWorkspaceBundle`
- `OpenClawGatewayAdapter`
- `OpenClawProvisioningService`
- `OpenClawSessionBinding`
- `OpenClawNativeSkillExporter`
- `OpenClawNativeSkillVerifier`

这些对象都只服务于 `agent plane`，不替代：

- `Chief of Staff`
- `VirtualDepartment`
- `WorkTicket`
- `TaskGraph`
- `Memory Fabric`

## 10. V1.5 / V1.8 / V2 路线

### V1.5

- OpenClaw 作为正式 `agent plane`
- Feishu 作为主沟通表面
- 当前项目负责 visible-room fan-out
- OpenClaw runtime 只 provision core-7
- `AGENTS.md / SKILLS.md` 已纳入 bootstrap files
- per-agent native skills 成为正式运行时能力

### V1.8

- 保持 OpenClaw agent plane 不变
- 在其上增加 `Pulse / Trigger Engine` 与 `Relationship Graph`
- 增加 `Skill Creator + Eval Loop`，但必须经过 approval / eval
- 增加 `CEO Visible Event Stream`，不引入 `Company Plaza`

### V2

- 保持 OpenClaw agent plane 不变
- 新增 Slack 作为第二沟通平台
- 复用同一套 `ConversationThread / WorkTicket / RunTrace / Memory Fabric`
