import { expect, test } from "@playwright/test"

const collections = {
  tickets: [
    {
      ticket_id: "wt_001",
      title: "Review OpenClaw native runtime rollout",
      status: "in_progress",
      ticket_type: "formal_project",
      channel_ref: "dashboard:ceo",
      thread_ref: "thread_001",
      taskgraph_ref: "tg_001",
      runtrace_ref: "rt_001",
    },
  ],
  threads: [
    {
      thread_id: "thread_001",
      title: "CEO x Chief of Staff",
      surface: "dashboard",
      status: "active",
      channel_id: "dashboard:ceo",
      participant_ids: ["ceo", "chief-of-staff"],
      transcript: [
        { actor: "ceo", text: "Summarize the runtime migration.", created_at: "2026-03-15T10:00:00Z" },
      ],
    },
  ],
  employeePacks: [
    {
      employee_id: "chief-of-staff",
      employee_name: "Chief of Staff",
      department: "Executive Office",
      summary: "Coordinates the visible multi-agent room.",
      source_persona_packs: [{ role_name: "Studio Producer" }],
    },
  ],
  namespaces: [{ namespace_id: "company:default", scope: "company_shared" }],
  feishuBots: [{ app_id: "cli_demo", employee_id: "chief-of-staff", display_name: "OPC - Chief of Staff" }],
  channelBindings: [
    {
      binding_id: "feishu-group-default",
      provider: "feishu",
      surface: "feishu_group",
      default_route: "project-room",
      mention_policy: "mention_fan_out_visible",
      sync_back_policy: "mirror_to_visible_room",
      room_policy_ref: "project-room-policy",
    },
  ],
  botSeatBindings: [{ binding_id: "seat_001", virtual_employee: "chief-of-staff" }],
  roomPolicies: [
    {
      room_policy_id: "project-room-policy",
      room_type: "project_room",
      speaker_mode: "mention_fan_out_visible",
      visible_participants: ["ceo", "chief-of-staff"],
      turn_taking_rule: "visible_round_robin",
      escalation_rule: "chief_of_staff",
    },
    {
      room_policy_id: "room-launch",
      room_type: "Launch Room",
      speaker_mode: "mention_fan_out_visible",
      visible_participants: ["ceo-visible-room", "dashboard-mirror", "chief-of-staff", "product-lead", "delivery-lead"],
      turn_taking_rule: "launch_core_bots_reply_in_visible_room_turns",
      escalation_rule: "launch_scope_or_market_risk_routes_back_to_executive_office",
    },
    {
      room_policy_id: "room-ops",
      room_type: "Ops Room",
      speaker_mode: "mention_fan_out_visible",
      visible_participants: ["ceo-visible-room", "dashboard-mirror", "chief-of-staff", "engineering-lead", "quality-lead"],
      turn_taking_rule: "ops_triage_and_delivery_risk_replies_stay_visible",
      escalation_rule: "production_or_quality_risks_route_to_executive_office",
    },
    {
      room_policy_id: "room-support",
      room_type: "Support Room",
      speaker_mode: "mention_fan_out_visible",
      visible_participants: ["ceo-visible-room", "dashboard-mirror", "chief-of-staff", "product-lead", "quality-lead"],
      turn_taking_rule: "support_triage_and_quality_feedback_transcript_stays_visible",
      escalation_rule: "repeated_customer_issues_route_to_quality_and_executive_office",
    },
  ],
  feishuInbound: [{ app_id: "cli_demo", surface: "feishu_group", chat_id: "oc_room_001", work_ticket_ref: "wt_001" }],
  feishuGroupDebug: [
    {
      debug_event_id: "cli_demo:om_group_debug_001",
      app_id: "cli_demo",
      message_id: "om_group_debug_001",
      chat_id: "oc_room_001",
      surface: "feishu_group",
      text: "@Chief of Staff summarize this thread",
      processed_status: "processed",
      dispatch_mode: "single_agent",
      raw_mentions_summary: ["open_id= | user_id=cli_demo | union_id= | key= | name=OPC - Chief of Staff"],
      target_agent_ids: ["chief-of-staff"],
    },
  ],
  feishuOutbound: [
    {
      outbound_id: "out_001",
      app_id: "cli_demo",
      source_kind: "runtime_reply",
      status: "sent",
      receive_id: "oc_room_001",
      receive_id_type: "chat_id",
      text: "Chief of Staff has responded.",
    },
  ],
  feishuDeadLetters: [
    {
      outbound_id: "dead_001",
      app_id: "cli_demo",
      source_kind: "runtime_reply",
      status: "failed",
      receive_id: "oc_room_001",
      receive_id_type: "chat_id",
      text: "Retry me.",
      attempt_count: 2,
      replay_attempt_count: 0,
      error_detail: "network timeout",
    },
  ],
  feishuReplayAudit: [
    {
      outbound_id: "replay_001",
      app_id: "cli_demo",
      source_kind: "runtime_reply",
      status: "sent",
      receive_id: "oc_room_001",
      receive_id_type: "chat_id",
      text: "Retry success.",
      replay_source_outbound_ref: "dead_001",
      created_at: "2026-03-15T10:10:00Z",
    },
  ],
  openclawGatewayHealth: {
    status: "healthy",
    reachable: true,
    gateway_base_url: "http://openclaw-gateway:18789",
    config_path: "/home/node/.openclaw/config/openclaw.json",
    active_session_refs: 1,
  },
  openclawRuntimeMode: {
    runtime_mode: "gateway",
    gateway_base_url: "http://openclaw-gateway:18789",
    runtime_home: ".runtime/openclaw/home",
    control_ui_url: "http://127.0.0.1:18789/",
  },
  openclawTokenSetup: {
    token_source: "env",
    token_env_key: "OPENCLAW_GATEWAY_TOKEN",
    token_configured: true,
    pairing_ready: true,
    runtime_mode: "gateway",
    launch_url: "/openclaw-control-ui/launch",
    control_ui_url: "http://127.0.0.1:18789/",
    setup_steps: ["Click button", "Control UI opens"],
  },
  openclawSessions: [
    {
      thread_id: "thread_001",
      title: "CEO x Chief of Staff",
      channel_id: "dashboard:ceo",
      surface: "dashboard",
      status: "active",
      work_ticket_ref: "wt_001",
      openclaw_session_refs: { "chief-of-staff": "session_cos_001" },
    },
  ],
  openclawRecentRuns: [
    {
      runtrace_id: "rt_001",
      work_ticket_ref: "wt_001",
      model_ref: "openclaw:opc-chief-of-staff",
      strategy: "openclaw_native_gateway",
      status: "completed",
      surface: "dashboard",
      interaction_mode: "formal_project",
      handoff_count: 1,
      latest_handoff_targets: ["product-lead"],
      latest_handoff_source_agent: "chief-of-staff",
      latest_handoff_reason: "Need product framing",
      last_event_at: "2026-03-15T10:05:00Z",
      session_refs: { "chief-of-staff": "session_cos_001" },
    },
  ],
  openclawHooks: {
    entries: [
      { hook_id: "command-logger", source: "internal", enabled: true, config: {} },
      { hook_id: "bootstrap-extra-files", source: "internal", enabled: true, config: {} },
    ],
  },
  openclawIssues: [
    { issue_id: "issue_001", severity: "warning", summary: "One replay pending review" },
  ],
  openclawBindings: [
    {
      employee_id: "chief-of-staff",
      openclaw_agent_id: "opc-chief-of-staff",
      workspace_home_ref: "/home/node/.openclaw/workspace/chief-of-staff",
      tool_profile: "orchestrator",
      sandbox_profile: "workspace-write",
    },
  ],
  openclawWorkspaceBundles: [
    {
      employee_id: "chief-of-staff",
      bootstrap_entrypoint: "BOOTSTRAP.md",
      workspace_path: "/home/node/.openclaw/workspace/chief-of-staff",
      bootstrap_files: [{ path: "BOOTSTRAP.md" }, { path: "SOUL.md" }],
    },
  ],
  postLaunchSummary: {
    launch_tickets: [
      {
        ticket_id: "wt_launch_001",
        title: "Launch AI MVP to first design partners",
        status: "completed",
        ticket_type: "quick_consult",
        channel_ref: "dashboard:launch-room",
        thread_ref: "thread_launch_001",
        taskgraph_ref: "tg_launch_001",
        runtrace_ref: "rt_launch_001",
      },
      {
        ticket_id: "wt_launch_002",
        title: "Prepare support FAQ expansion for launch week",
        status: "consulting",
        ticket_type: "quick_consult",
        channel_ref: "dashboard:launch-room",
        thread_ref: "thread_launch_002",
        taskgraph_ref: "tg_launch_002",
        runtrace_ref: "rt_launch_002",
      },
    ],
    follow_ups: [
      {
        source_work_ticket_ref: "wt_launch_001",
        source_title: "Launch AI MVP to first design partners",
        source_runtrace_ref: "rt_launch_001",
        follow_up_ticket_ref: "wt_follow_001",
        follow_up_title: "Post-launch cadence · Launch AI MVP to first design partners",
        follow_up_runtrace_ref: "rt_follow_001",
        follow_up_thread_ref: "thread_follow_001",
        trigger_type: "scheduled_heartbeat",
        created_at: "2026-03-15T10:15:00Z",
        status: "consulting",
        note: "post_launch_cadence_auto_route",
      },
    ],
    feedback_memories: [
      {
        memory_id: "mem_post_001",
        namespace_id: "company:default",
        scope: "company_shared",
        kind: "semantic",
        tags: ["post_launch_feedback", "executive_synthesis"],
        content: "第一批用户对 onboarding 清晰度反馈积极，但 FAQ 需要补齐。",
        created_at: "2026-03-15T10:16:00Z",
      },
    ],
  },
}

const details = {
  ticket: {
    ticket: collections.tickets[0],
    checkpoints: [{ checkpoint_id: "cp_001", kind: "formal", verdict_state: "go", approval_state: "approved" }],
    memories: [{ memory_id: "mem_001", namespace_id: "company:default", scope: "company_shared", kind: "summary", content: "Runtime migration summary" }],
    artifacts: [{ source_type: "quality_evidence", bucket: "artifacts", summary: "Launch note", object_key: "artifact_001" }],
    thread: collections.threads[0],
    taskGraph: { nodes: [{ node_id: "node_001", title: "Executive review", owner_department: "Executive Office", status: "completed" }] },
    runTrace: { events: [{ event_type: "runtime_execution_completed", message: "Run completed" }] },
  },
  deadLetter: {
    dead_letter: collections.feishuDeadLetters[0],
    replay_history: collections.feishuReplayAudit,
  },
  session: {
    ...collections.openclawSessions[0],
    transcript_count: 1,
    last_transcript_at: "2026-03-15T10:00:00Z",
    transcript: collections.threads[0].transcript,
    bound_agent_ids: ["chief-of-staff"],
    participant_ids: ["ceo", "chief-of-staff"],
    recent_run_strategies: ["openclaw_native_gateway"],
  },
  run: {
    ...collections.openclawRecentRuns[0],
    events: [{ event_type: "runtime_execution_completed", message: "Run completed", created_at: "2026-03-15T10:05:00Z" }],
  },
  agentDetail: {
    agent: {
      employee_id: "chief-of-staff",
      employee_name: "Chief of Staff",
      department: "Executive Office",
      openclaw_agent_id: "opc-chief-of-staff",
      primary_model_ref: "openclaw:opc-chief-of-staff",
      provider_name: "openclaw",
      provider_base_url: "http://openclaw-gateway:18789",
      model_id: "opc-chief-of-staff",
      model_name: "Chief of Staff Native",
      tool_profile: "orchestrator",
      sandbox_profile: "workspace-write",
      source_persona_roles: ["Studio Producer"],
      workflow_hints: ["routing", "executive_synthesis"],
      memory_instructions: ["sync executive summaries"],
      identity_profile: {
        identity: "你是 Chief of Staff，负责 framing、routing 和 executive synthesis。",
        decision_lens: ["先判断该由谁承接，再综合输出给 CEO。"],
        role_boundaries: ["不替 Product、Design、Engineering 做专业结论。"],
        collaboration_rules: ["接棒时明确点名下一位 bot。"],
      },
      system_prompt: "Chief of Staff system prompt",
    },
    binding: collections.openclawBindings[0],
    workspace_bundle: collections.openclawWorkspaceBundles[0],
    workspace_files: [
      { path: "BOOTSTRAP.md", content: "# Bootstrap" },
      { path: "AGENTS.md", content: "# Agents" },
      { path: "IDENTITY.md", content: "# Identity" },
      { path: "SOUL.md", content: "# Soul" },
      { path: "SKILLS.md", content: "# Skills" },
      { path: "TOOLS.md", content: "# Tools" },
      { path: "HEARTBEAT.md", content: "# Heartbeat" },
      { path: "USER.md", content: "# User" },
    ],
    native_skills: [
      {
        skill_id: "skill_001",
        skill_name: "Project Manager Senior",
        scope: "professional",
        native_skill_name: "opc-chief-of-staff--project-manager-senior",
        workspace_relative_dir: "skills/opc-chief-of-staff--project-manager-senior",
        workspace_relative_path: "skills/opc-chief-of-staff--project-manager-senior/SKILL.md",
        source_ref: {
          repo_url: "https://github.com/msitarzewski/agency-agents",
          repo_name: "agency-agents",
          commit_sha: "demo-sha",
          path: "project-management/project-manager-senior.md",
          license: "MIT",
          install_method: "python scripts/sync_skills.py --repo agency-agents",
          verify_command: "python -m pytest -q tests/test_skill_catalog.py",
          local_path: "/workspace/third_party/skills/repos/agency-agents/demo-sha/project-management/project-manager-senior.md",
        },
        entrypoint_type: "instructional_skill",
        fit_rationale: "适合 Chief of Staff 做组织和路由。",
        exported: true,
        discovered: true,
        verification_status: "verified",
      },
      {
        skill_id: "skill_002",
        skill_name: "Api Designer",
        scope: "general",
        native_skill_name: "opc-chief-of-staff--api-designer",
        workspace_relative_dir: "skills/opc-chief-of-staff--api-designer",
        workspace_relative_path: "skills/opc-chief-of-staff--api-designer/SKILL.md",
        source_ref: {
          repo_url: "https://github.com/VoltAgent/awesome-claude-code-subagents",
          repo_name: "awesome-claude-code-subagents",
          commit_sha: "demo-sha",
          path: "categories/01-core-development/api-designer.md",
          license: "MIT",
          install_method: "python scripts/sync_skills.py --repo awesome-claude-code-subagents",
          verify_command: "python -m pytest -q tests/test_skill_catalog.py",
          local_path: "/workspace/third_party/skills/repos/awesome-claude-code-subagents/demo-sha/categories/01-core-development/api-designer.md",
        },
        entrypoint_type: "instructional_skill",
        fit_rationale: "通用技能。",
        exported: true,
        discovered: true,
        verification_status: "verified",
      },
    ],
    memory_namespaces: collections.namespaces,
    recent_memory_records: [
      {
        memory_id: "mem_001",
        namespace_id: "company:default",
        scope: "company_shared",
        kind: "summary",
        content: "Runtime migration summary",
      },
    ],
    recent_sessions: collections.openclawSessions,
    recent_runs: collections.openclawRecentRuns,
  },
}

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname

    const json = (() => {
      switch (path) {
        case "/api/v1/control-plane/work-tickets":
          return collections.tickets
        case "/api/v1/conversations/threads":
          return collections.threads
        case "/api/v1/persona/employee-packs":
          return collections.employeePacks
        case "/api/v1/memory/namespaces":
          return collections.namespaces
        case "/api/v1/feishu/bot-apps":
          return collections.feishuBots
        case "/api/v1/conversations/channel-bindings":
          return collections.channelBindings
        case "/api/v1/conversations/bot-seat-bindings":
          return collections.botSeatBindings
        case "/api/v1/conversations/room-policies":
          return collections.roomPolicies
        case "/api/v1/feishu/inbound-events":
          return collections.feishuInbound
        case "/api/v1/feishu/group-debug-events":
          return collections.feishuGroupDebug
        case "/api/v1/feishu/outbound-messages":
          return collections.feishuOutbound
        case "/api/v1/feishu/dead-letters":
          return collections.feishuDeadLetters
        case "/api/v1/feishu/replay-audit":
          return collections.feishuReplayAudit
        case "/api/v1/openclaw/gateway/health":
          return collections.openclawGatewayHealth
        case "/api/v1/openclaw/gateway/runtime-mode":
          return collections.openclawRuntimeMode
        case "/api/v1/openclaw/gateway/token-setup":
          return collections.openclawTokenSetup
        case "/api/v1/openclaw/gateway/sessions":
          return collections.openclawSessions
        case "/api/v1/openclaw/gateway/recent-runs":
          return collections.openclawRecentRuns
        case "/api/v1/openclaw/gateway/hooks":
          return collections.openclawHooks
        case "/api/v1/openclaw/gateway/issues":
          return collections.openclawIssues
        case "/api/v1/openclaw/bindings":
          return collections.openclawBindings
        case "/api/v1/openclaw/workspace-bundles":
          return collections.openclawWorkspaceBundles
        case "/api/v1/runtime/post-launch/summary":
          return collections.postLaunchSummary
        case "/api/v1/control-plane/work-tickets/wt_001":
          return details.ticket.ticket
        case "/api/v1/control-plane/work-tickets/wt_001/checkpoints":
          return details.ticket.checkpoints
        case "/api/v1/memory/work-tickets/wt_001":
          return details.ticket.memories
        case "/api/v1/artifacts/work-tickets/wt_001/blobs":
          return details.ticket.artifacts
        case "/api/v1/conversations/threads/thread_001":
          return details.session
        case "/api/v1/control-plane/task-graphs/tg_001":
          return details.ticket.taskGraph
        case "/api/v1/control-plane/run-traces/rt_001":
          return details.ticket.runTrace
        case "/api/v1/feishu/dead-letters/dead_001":
          return details.deadLetter
        case "/api/v1/openclaw/gateway/sessions/thread_001":
          return details.session
        case "/api/v1/openclaw/gateway/recent-runs/rt_001":
          return details.run
        case "/api/v1/openclaw/agents/chief-of-staff/detail":
          return details.agentDetail
        default:
          if (path.startsWith("/api/v1/feishu/outbound-messages/dead_001/replay")) {
            return { replay_result: { status: "sent" }, source_outbound_ref: "dead_001" }
          }
          return {}
      }
    })()

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(json),
    })
  })
})

test("dashboard shell can load and navigate major views", async ({ page }) => {
  await page.goto("/dashboard")

  await expect(page.getByRole("heading", { name: "CEO Dashboard" })).toBeVisible()
  await expect(page.getByText("Recent Native Runs")).toBeVisible()

  await page.getByRole("link", { name: "OpenClaw Runtime", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Gateway、Session、Native Runs 与原生 hooks" })).toBeVisible()
  await page.getByText("Selected Session Detail").first().waitFor()
  await page.getByRole("tab", { name: "Visible Handoffs" }).click()
  await expect(page.locator("tbody").getByText("product-lead").first()).toBeVisible()

  await page.getByRole("link", { name: "Growth Ops", exact: true }).click()
  await expect(page.getByRole("heading", { name: "管理 launch tickets、post-launch cadence 和反馈回写。" })).toBeVisible()
  await page.getByText("Cadence Follow-ups").first().waitFor()
  await page.getByPlaceholder("搜索工单标题 / ID / 类型").fill("FAQ expansion")
  const launchTable = page.locator("table").first()
  await expect(launchTable.getByText("Prepare support FAQ expansion for launch week")).toBeVisible()
  await expect(launchTable.getByText("Launch AI MVP to first design partners")).toHaveCount(0)

  await page.getByRole("link", { name: "Feishu Ops", exact: true }).click()
  await expect(page.getByRole("heading", { name: "机器人、通道、收发事件与 dead-letter 重放" })).toBeVisible()
  await page.getByText("Selected Dead Letter").first().waitFor()
  await page.getByRole("tab", { name: "Group Debug" }).click()
  await expect(page.getByText("Selected Group Debug Event")).toBeVisible()

  await page.getByRole("tab", { name: "Dead Letters" }).click()
  await expect(page.getByText("Retry me.").first()).toBeVisible()
  await page.getByText("Retry me.").first().click()
  await expect(page.getByRole("button", { name: "Replay Dead Letter" })).toBeVisible({ timeout: 10000 })

  await page.getByRole("link", { name: "Agents", exact: true }).click()
  await expect(page.getByRole("heading", { name: "核心 7 席位的 OpenClaw 原生 Agent 管理台" })).toBeVisible()
  await expect(page.getByText("Chief of Staff Native")).toBeVisible()
  await page.getByRole("tab", { name: "Native Skills" }).click()
  await expect(page.getByText("Project Manager Senior")).toBeVisible()
})
