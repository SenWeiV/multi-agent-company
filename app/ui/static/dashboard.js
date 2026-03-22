const config = window.__dashboardConfig || { apiPrefix: "/api/v1" };
const apiPrefix = config.apiPrefix;

const state = {
  tickets: [],
  threads: [],
  employeePacks: [],
  namespaces: [],
  feishuBots: [],
  channelBindings: [],
  botSeatBindings: [],
  roomPolicies: [],
  feishuInbound: [],
  feishuOutbound: [],
  feishuDeadLetters: [],
  feishuReplayAudit: [],
  feishuDeadLetterDetail: null,
  openclawGatewayHealth: null,
  openclawRuntimeMode: null,
  openclawTokenSetup: null,
  openclawSessions: [],
  openclawSessionDetail: null,
  openclawRecentRuns: [],
  openclawRunDetail: null,
  openclawHooks: null,
  openclawIssues: [],
  openclawBindings: [],
  openclawWorkspaceBundles: [],
  selectedTicketId: null,
  selectedDeadLetterId: null,
  selectedOpenClawThreadId: null,
  selectedOpenClawRunId: null,
};

function qs(id) {
  return document.getElementById(id);
}

function renderMetaRows(rows) {
  return rows
    .filter((row) => row && row.value !== undefined && row.value !== null && row.value !== "")
    .map(
      (row) => `
        <div class="meta-row">
          <span class="meta-label">${escapeHtml(row.label)}</span>
          <span class="meta-value">${row.code ? `<code>${escapeHtml(String(row.value))}</code>` : escapeHtml(String(row.value))}</span>
        </div>
      `
    )
    .join("");
}

function renderTagRow(values, variant = "") {
  const items = Array.isArray(values)
    ? values.filter(Boolean)
    : values && typeof values === "object"
      ? Object.entries(values)
          .filter(([, value]) => value)
          .map(([key, value]) => `${key}: ${value}`)
      : [];
  if (!items.length) {
    return `<div class="tag-row"><span class="tag ${variant}">none</span></div>`;
  }
  return `
    <div class="tag-row">
      ${items.map((value) => `<span class="tag ${variant}">${escapeHtml(String(value))}</span>`).join("")}
    </div>
  `;
}

function summarizeHookConfig(config) {
  const entries = Object.entries(config || {});
  if (!entries.length) {
    return "default";
  }
  return entries
    .map(([key, value]) => `${key}=${typeof value === "string" ? value : JSON.stringify(value)}`)
    .join(" · ");
}

function workspaceFileNames(bundle) {
  return (bundle.bootstrap_files || [])
    .map((file) => file.path || file.filename || file.name || String(file))
    .filter(Boolean);
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${apiPrefix}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `${response.status} ${response.statusText}`);
  }
  return response.json();
}

async function refreshAll() {
  try {
    const [
      tickets,
      threads,
      employeePacks,
      namespaces,
      feishuBots,
      channelBindings,
      botSeatBindings,
      roomPolicies,
      feishuInbound,
      feishuOutbound,
      feishuDeadLetters,
      feishuReplayAudit,
      openclawGatewayHealth,
      openclawRuntimeMode,
      openclawTokenSetup,
      openclawSessions,
      openclawRecentRuns,
      openclawHooks,
      openclawIssues,
      openclawBindings,
      openclawWorkspaceBundles,
    ] = await Promise.all([
      apiRequest("/control-plane/work-tickets"),
      apiRequest("/conversations/threads"),
      apiRequest("/persona/employee-packs?core_only=true"),
      apiRequest("/memory/namespaces"),
      apiRequest("/feishu/bot-apps"),
      apiRequest("/conversations/channel-bindings"),
      apiRequest("/conversations/bot-seat-bindings"),
      apiRequest("/conversations/room-policies"),
      apiRequest("/feishu/inbound-events?limit=12"),
      apiRequest("/feishu/outbound-messages?limit=12"),
      apiRequest("/feishu/dead-letters?limit=12"),
      apiRequest("/feishu/replay-audit?limit=20"),
      apiRequest("/openclaw/gateway/health"),
      apiRequest("/openclaw/gateway/runtime-mode"),
      apiRequest("/openclaw/gateway/token-setup"),
      apiRequest("/openclaw/gateway/sessions"),
      apiRequest("/openclaw/gateway/recent-runs"),
      apiRequest("/openclaw/gateway/hooks"),
      apiRequest("/openclaw/gateway/issues"),
      apiRequest("/openclaw/bindings"),
      apiRequest("/openclaw/workspace-bundles"),
    ]);

    state.tickets = tickets;
    state.threads = threads;
    state.employeePacks = employeePacks;
    state.namespaces = namespaces;
    state.feishuBots = feishuBots;
    state.channelBindings = channelBindings;
    state.botSeatBindings = botSeatBindings;
    state.roomPolicies = roomPolicies;
    state.feishuInbound = feishuInbound;
    state.feishuOutbound = feishuOutbound;
    state.feishuDeadLetters = feishuDeadLetters;
    state.feishuReplayAudit = feishuReplayAudit;
    state.openclawGatewayHealth = openclawGatewayHealth;
    state.openclawRuntimeMode = openclawRuntimeMode;
    state.openclawTokenSetup = openclawTokenSetup;
    state.openclawSessions = openclawSessions;
    state.openclawRecentRuns = openclawRecentRuns;
    state.openclawHooks = openclawHooks;
    state.openclawIssues = openclawIssues;
    state.openclawBindings = openclawBindings;
    state.openclawWorkspaceBundles = openclawWorkspaceBundles;

    renderSummary();
    renderTickets();
    renderThreads();
    renderEmployeePacks();
    renderNamespaces();
    renderFeishuBots();
    renderFeishuChannels();
    renderFeishuInbound();
    renderFeishuOutbound();
    renderFeishuDeadLetters();
    renderFeishuReplayAudit();
    renderFeishuDeadLetterDetail();
    renderFeishuConfigEditor();
    renderOpenClawGatewayHealth();
    renderOpenClawRuntimeMode();
    renderOpenClawTokenSetup();
    renderOpenClawSessions();
    renderOpenClawRecentRuns();
    renderOpenClawSessionDetail();
    renderOpenClawRunDetail();
    renderOpenClawHooks();
    renderOpenClawIssues();
    renderOpenClawBindings();
    renderOpenClawWorkspaces();
    renderOpenClawConfigEditor();
    renderOpenClawHookEditor();
    populateEmployeeOptions();
    populateFeishuBotOptions();

    if (state.selectedTicketId) {
      await selectTicket(state.selectedTicketId);
    }
    if (state.selectedDeadLetterId) {
      await selectDeadLetter(state.selectedDeadLetterId);
    } else if (state.feishuDeadLetters.length) {
      await selectDeadLetter(state.feishuDeadLetters[0].outbound_id);
    }
    if (state.selectedOpenClawThreadId) {
      await selectOpenClawSession(state.selectedOpenClawThreadId);
    } else if (state.openclawSessions.length) {
      await selectOpenClawSession(state.openclawSessions[0].thread_id);
    }
    if (state.selectedOpenClawRunId) {
      await selectOpenClawRun(state.selectedOpenClawRunId);
    } else if (state.openclawRecentRuns.length) {
      await selectOpenClawRun(state.openclawRecentRuns[0].runtrace_id);
    }
  } catch (error) {
    renderLastIntake(`刷新失败：${error.message}`);
  }
}

async function selectDeadLetter(outboundId) {
  if (!outboundId) {
    state.selectedDeadLetterId = null;
    state.feishuDeadLetterDetail = null;
    renderFeishuDeadLetters();
    renderFeishuDeadLetterDetail();
    return;
  }
  state.selectedDeadLetterId = outboundId;
  renderFeishuDeadLetters();
  try {
    state.feishuDeadLetterDetail = await apiRequest(`/feishu/dead-letters/${outboundId}`);
    renderFeishuDeadLetterDetail();
  } catch (error) {
    state.feishuDeadLetterDetail = null;
    renderLastIntake(`加载 dead letter 详情失败：${error.message}`);
    renderFeishuDeadLetterDetail();
  }
}

function renderSummary() {
  qs("stat-tickets").textContent = String(state.tickets.length);
  qs("stat-threads").textContent = String(state.threads.length);
  qs("stat-employees").textContent = String(state.employeePacks.length);
  qs("stat-namespaces").textContent = String(state.namespaces.length);
  qs("ticket-count-pill").textContent = `${state.tickets.length} items`;
}

function renderTickets() {
  const container = qs("tickets-list");
  if (!state.tickets.length) {
    container.innerHTML = `<div class="empty-state">还没有 Work Ticket。先通过 CEO Inbox 发起一条指令。</div>`;
    return;
  }

  container.innerHTML = state.tickets
    .slice()
    .reverse()
    .map((ticket) => {
      const selectedClass = ticket.ticket_id === state.selectedTicketId ? "is-selected" : "";
      return `
        <article class="ticket-card ${selectedClass}" data-ticket-id="${ticket.ticket_id}">
          <div class="card-topline">
            <p class="card-title">${escapeHtml(ticket.title)}</p>
            <span class="pill">${escapeHtml(ticket.status)}</span>
          </div>
          <div class="card-meta">type: ${escapeHtml(ticket.ticket_type)}</div>
          <div class="card-submeta"><code>${escapeHtml(ticket.ticket_id)}</code></div>
        </article>
      `;
    })
    .join("");

  container.querySelectorAll("[data-ticket-id]").forEach((element) => {
    element.addEventListener("click", () => selectTicket(element.dataset.ticketId));
  });
}

async function selectTicket(ticketId) {
  state.selectedTicketId = ticketId;
  renderTickets();

  try {
    const ticket = await apiRequest(`/control-plane/work-tickets/${ticketId}`);
    const checkpointsPromise = apiRequest(`/control-plane/work-tickets/${ticketId}/checkpoints`);
    const memoryPromise = apiRequest(`/memory/work-tickets/${ticketId}`);
    const artifactsPromise = apiRequest(`/artifacts/work-tickets/${ticketId}/blobs`);
    const threadPromise = ticket.thread_ref ? apiRequest(`/conversations/threads/${ticket.thread_ref}`) : Promise.resolve(null);
    const taskGraphPromise = ticket.taskgraph_ref
      ? apiRequest(`/control-plane/task-graphs/${ticket.taskgraph_ref}`)
      : Promise.resolve(null);
    const runTracePromise = ticket.runtrace_ref
      ? apiRequest(`/control-plane/run-traces/${ticket.runtrace_ref}`)
      : Promise.resolve(null);

    const [checkpoints, memories, artifacts, thread, taskGraph, runTrace] = await Promise.all([
      checkpointsPromise,
      memoryPromise,
      artifactsPromise,
      threadPromise,
      taskGraphPromise,
      runTracePromise,
    ]);

    renderTicketDetail(ticket, checkpoints, thread);
    renderTaskGraph(taskGraph);
    renderRunTrace(runTrace);
    renderMemories(memories);
    renderArtifacts(artifacts);
    setupActionButtons(ticket, checkpoints);
  } catch (error) {
    qs("ticket-detail").textContent = `加载详情失败：${error.message}`;
  }
}

function renderTicketDetail(ticket, checkpoints, thread) {
  qs("ticket-detail").textContent = JSON.stringify(
    {
      ticket,
      checkpoints: checkpoints.map((checkpoint) => ({
        checkpoint_id: checkpoint.checkpoint_id,
        kind: checkpoint.kind,
        verdict_state: checkpoint.verdict_state,
        approval_state: checkpoint.approval_state,
      })),
      thread,
    },
    null,
    2
  );
}

function renderTaskGraph(taskGraph) {
  const container = qs("taskgraph-detail");
  if (!taskGraph) {
    container.className = "node-grid empty-state";
    container.textContent = "暂无 TaskGraph";
    return;
  }
  container.className = "node-grid";
  container.innerHTML = taskGraph.nodes
    .map(
      (node) => `
        <article class="node-card">
          <strong>${escapeHtml(node.owner_department)}</strong>
          <span>${escapeHtml(node.title)}</span>
          <span>output: ${escapeHtml(node.output_kind || "Deliverable")}</span>
          <span class="node-status">${escapeHtml(node.status)}</span>
        </article>
      `
    )
    .join("");
}

function renderRunTrace(runTrace) {
  const container = qs("runtrace-detail");
  if (!runTrace) {
    container.className = "timeline empty-state";
    container.textContent = "暂无 RunTrace";
    return;
  }
  container.className = "timeline";
  container.innerHTML = runTrace.events
    .map(
      (event) => `
        <article class="timeline-item">
          <strong>${escapeHtml(event.event_type)}</strong>
          <span>${escapeHtml(event.message)}</span>
        </article>
      `
    )
    .join("");
}

function renderMemories(memories) {
  const container = qs("memory-detail");
  if (!memories.length) {
    container.className = "memory-list empty-state";
    container.textContent = "这个 Work Ticket 还没有 memory 记录。";
    return;
  }

  container.className = "memory-list";
  container.innerHTML = memories
    .map(
      (memory) => `
        <article class="memory-card">
          <div class="card-topline">
            <p class="card-title">${escapeHtml(memory.scope)} / ${escapeHtml(memory.kind)}</p>
            <span class="pill">${escapeHtml(memory.namespace_id)}</span>
          </div>
          <div class="card-meta">${escapeHtml(memory.content)}</div>
          <div class="card-submeta"><code>${escapeHtml(memory.memory_id)}</code></div>
        </article>
      `
    )
    .join("");
}

function renderArtifacts(artifacts) {
  const container = qs("artifacts-detail");
  if (!artifacts.length) {
    container.className = "memory-list empty-state";
    container.textContent = "这个 Work Ticket 还没有落盘 Artifact。";
    return;
  }

  container.className = "memory-list";
  container.innerHTML = artifacts
    .map(
      (artifact) => `
        <article class="memory-card">
          <div class="card-topline">
            <p class="card-title">${escapeHtml(artifact.source_type)}</p>
            <span class="pill">${escapeHtml(artifact.bucket)}</span>
          </div>
          <div class="card-meta">${escapeHtml(artifact.summary)}</div>
          <div class="card-submeta"><code>${escapeHtml(artifact.object_key)}</code></div>
        </article>
      `
    )
    .join("");
}

function renderThreads() {
  const container = qs("threads-list");
  if (!state.threads.length) {
    container.innerHTML = `<div class="empty-state">还没有 ConversationThread。</div>`;
    return;
  }
  container.innerHTML = state.threads
    .slice()
    .reverse()
    .map(
      (thread) => `
        <article class="thread-card">
          <div class="card-topline">
            <p class="card-title">${escapeHtml(thread.surface)}</p>
            <span class="pill">${escapeHtml(thread.status)}</span>
          </div>
          <div class="card-meta">${escapeHtml(thread.title)}</div>
          <div class="card-submeta"><code>${escapeHtml(thread.thread_id)}</code></div>
        </article>
      `
    )
    .join("");
}

function renderNamespaces() {
  const container = qs("namespaces-list");
  if (!state.namespaces.length) {
    container.innerHTML = `<div class="empty-state">还没有 MemoryNamespace。</div>`;
    return;
  }
  container.innerHTML = state.namespaces
    .map(
      (namespace) => `
        <article class="namespace-card">
          <p class="card-title">${escapeHtml(namespace.scope)}</p>
          <div class="card-submeta"><code>${escapeHtml(namespace.namespace_id)}</code></div>
        </article>
      `
    )
    .join("");
}

function renderFeishuBots() {
  const container = qs("feishu-bots-list");
  if (!state.feishuBots.length) {
    container.innerHTML = `<div class="empty-state">当前没有配置 Feishu bot。</div>`;
    return;
  }
  container.innerHTML = state.feishuBots
    .map((bot) => {
      const seatBinding = state.botSeatBindings.find((binding) => binding.virtual_employee === bot.employee_id);
      return `
        <article class="feishu-card">
          <div class="card-topline">
            <p class="card-title">${escapeHtml(bot.display_name || bot.employee_id)}</p>
            <span class="pill">${escapeHtml(bot.employee_id)}</span>
          </div>
          <div class="card-meta">app: <code>${escapeHtml(bot.app_id)}</code></div>
          <div class="card-meta">open_id: <code>${escapeHtml(bot.bot_open_id || "n/a")}</code></div>
          <div class="card-submeta">seat binding: ${escapeHtml(seatBinding?.binding_id || "unbound")}</div>
        </article>
      `;
    })
    .join("");
}

function renderFeishuChannels() {
  const container = qs("feishu-channels-list");
  const bindings = state.channelBindings.filter((binding) => binding.provider === "feishu");
  if (!bindings.length) {
    container.innerHTML = `<div class="empty-state">当前没有 Feishu channel binding。</div>`;
    return;
  }
  container.innerHTML = bindings
    .map(
      (binding) => `
        <article class="feishu-card">
          <div class="card-topline">
            <p class="card-title">${escapeHtml(binding.surface)}</p>
            <span class="pill">${escapeHtml(binding.default_route)}</span>
          </div>
          <div class="card-meta">mention: ${escapeHtml(binding.mention_policy)}</div>
          <div class="card-submeta">sync-back: ${escapeHtml(binding.sync_back_policy)}</div>
        </article>
      `
    )
    .join("");
}

function renderFeishuInbound() {
  const container = qs("feishu-inbound-list");
  if (!state.feishuInbound.length) {
    container.innerHTML = `<div class="empty-state">最近没有 Feishu inbound event。</div>`;
    return;
  }
  container.innerHTML = state.feishuInbound
    .slice()
    .reverse()
    .map(
      (event) => `
        <article class="feishu-card">
          <div class="card-topline">
            <p class="card-title">${escapeHtml(event.surface)}</p>
            <span class="pill">${escapeHtml(event.app_id)}</span>
          </div>
          <div class="card-meta">chat: <code>${escapeHtml(event.chat_id)}</code></div>
          <div class="card-submeta">ticket: <code>${escapeHtml(event.work_ticket_ref || "n/a")}</code></div>
        </article>
      `
    )
    .join("");
}

function renderFeishuOutbound() {
  const container = qs("feishu-outbound-list");
  if (!state.feishuOutbound.length) {
    container.innerHTML = `<div class="empty-state">最近没有 Feishu outbound message。</div>`;
    return;
  }
  container.innerHTML = state.feishuOutbound
    .slice()
    .reverse()
    .map(
      (message) => `
        <article class="feishu-card ${message.status === "failed" ? "is-error" : ""}">
          <div class="card-topline">
            <p class="card-title">${escapeHtml(message.source_kind)}</p>
            <span class="pill">${escapeHtml(message.status || message.app_id)}</span>
          </div>
          <div class="meta-list">
            ${renderMetaRows([
              { label: "app", value: message.app_id, code: true },
              { label: "attempts", value: String(message.attempt_count || 1) },
              { label: "chat", value: message.receive_id, code: true },
            ])}
          </div>
          <div class="card-meta">${escapeHtml(message.text)}</div>
          <div class="card-submeta"><code>${escapeHtml(message.attachment_object_ref || "no-blob")}</code></div>
          ${message.error_detail ? `<div class="card-submeta error-text">${escapeHtml(message.error_detail)}</div>` : ""}
        </article>
      `
    )
    .join("");
}

function renderFeishuDeadLetters() {
  const container = qs("feishu-dead-letters");
  const query = String(qs("feishu-dead-letter-search")?.value || "").trim().toLowerCase();
  const items = state.feishuDeadLetters.filter((message) => {
    if (!query) {
      return true;
    }
    return [
      message.outbound_id,
      message.receive_id,
      message.text,
      message.error_detail || "",
      message.work_ticket_ref || "",
    ]
      .join(" ")
      .toLowerCase()
      .includes(query);
  });
  if (!items.length) {
    container.innerHTML = `<div class="empty-state">当前没有待处理 dead letter。</div>`;
    return;
  }
  container.innerHTML = items
    .map(
      (message) => `
        <article class="feishu-card is-error ${message.outbound_id === state.selectedDeadLetterId ? "is-selected" : ""}" data-dead-letter-id="${escapeHtml(message.outbound_id)}">
          <div class="card-topline">
            <p class="card-title">${escapeHtml(message.source_kind)}</p>
            <span class="pill">${escapeHtml(message.receive_id_type)}</span>
          </div>
          <div class="meta-list">
            ${renderMetaRows([
              { label: "ref", value: message.outbound_id, code: true },
              { label: "chat", value: message.receive_id, code: true },
              { label: "attempts", value: String(message.attempt_count || 1) },
              { label: "replays", value: String(message.replay_attempt_count || 0) },
            ])}
          </div>
          <div class="card-meta">${escapeHtml(message.text)}</div>
          ${message.error_detail ? `<div class="card-submeta error-text">${escapeHtml(message.error_detail)}</div>` : ""}
          <div class="form-actions inline-actions">
            <button type="button" class="secondary" data-dead-letter-replay="${escapeHtml(message.outbound_id)}">Replay</button>
          </div>
        </article>
      `
    )
    .join("");

  container.querySelectorAll("[data-dead-letter-id]").forEach((element) => {
    element.addEventListener("click", async () => {
      const outboundId = element.getAttribute("data-dead-letter-id");
      if (!outboundId) {
        return;
      }
      await selectDeadLetter(outboundId);
    });
  });

  container.querySelectorAll("[data-dead-letter-replay]").forEach((element) => {
    element.addEventListener("click", async (event) => {
      event.stopPropagation();
      const outboundId = element.getAttribute("data-dead-letter-replay");
      if (!outboundId) {
        return;
      }
      try {
        element.setAttribute("disabled", "disabled");
        const result = await apiRequest(`/feishu/outbound-messages/${outboundId}/replay`, { method: "POST" });
        renderLastIntake(`Dead letter 已重放：${result.replay_result.status} / ${result.source_outbound_ref}`);
        await refreshAll();
      } catch (error) {
        renderLastIntake(`Dead letter 重放失败：${error.message}`);
      } finally {
        element.removeAttribute("disabled");
      }
    });
  });
}

function renderFeishuReplayAudit() {
  const container = qs("feishu-replay-audit");
  const query = String(qs("feishu-replay-audit-search")?.value || "").trim().toLowerCase();
  const items = state.feishuReplayAudit.filter((entry) => {
    if (!query) {
      return true;
    }
    return [
      entry.outbound_id,
      entry.replay_source_outbound_ref || "",
      entry.replay_root_outbound_ref || "",
      entry.receive_id,
      entry.work_ticket_ref || "",
      entry.thread_ref || "",
      entry.runtrace_ref || "",
    ]
      .join(" ")
      .toLowerCase()
      .includes(query);
  });
  if (!items.length) {
    container.innerHTML = `<div class="empty-state">当前还没有 replay 审计记录。</div>`;
    return;
  }
  container.innerHTML = items
    .map(
      (entry) => `
        <article class="feishu-card">
          <div class="card-topline">
            <p class="card-title">${escapeHtml(entry.status)}</p>
            <span class="pill">${escapeHtml(entry.source_kind)}</span>
          </div>
          <div class="meta-list">
            ${renderMetaRows([
              { label: "outbound", value: entry.outbound_id, code: true },
              { label: "source", value: entry.replay_source_outbound_ref || "n/a", code: Boolean(entry.replay_source_outbound_ref) },
              { label: "chat", value: entry.receive_id, code: true },
              { label: "at", value: new Date(entry.created_at).toLocaleString() },
            ])}
          </div>
          ${entry.error_detail ? `<div class="card-submeta error-text">${escapeHtml(entry.error_detail)}</div>` : ""}
        </article>
      `
    )
    .join("");
}

function renderFeishuDeadLetterDetail() {
  const container = qs("feishu-dead-letter-detail");
  const detail = state.feishuDeadLetterDetail;
  if (!detail) {
    container.innerHTML = `<div class="empty-state">选择一个 dead letter 查看错误细节和 replay 审计链路。</div>`;
    return;
  }
  const deadLetter = detail.dead_letter;
  container.innerHTML = `
    <article class="feishu-card is-error">
      <div class="card-topline">
        <p class="card-title">${escapeHtml(deadLetter.source_kind)}</p>
        <span class="pill">${escapeHtml(deadLetter.outbound_id)}</span>
      </div>
      <div class="meta-list">
        ${renderMetaRows([
          { label: "chat", value: deadLetter.receive_id, code: true },
          { label: "ticket", value: deadLetter.work_ticket_ref || "n/a", code: Boolean(deadLetter.work_ticket_ref) },
          { label: "thread", value: deadLetter.thread_ref || "n/a", code: Boolean(deadLetter.thread_ref) },
          { label: "runtrace", value: deadLetter.runtrace_ref || "n/a", code: Boolean(deadLetter.runtrace_ref) },
          { label: "attempts", value: String(deadLetter.attempt_count || 1) },
          { label: "replays", value: String(deadLetter.replay_attempt_count || 0) },
        ])}
      </div>
      <div class="card-meta">${escapeHtml(deadLetter.text)}</div>
      ${deadLetter.error_detail ? `<div class="card-submeta error-text">${escapeHtml(deadLetter.error_detail)}</div>` : ""}
      <div class="detail-list">
        ${(detail.replay_history || [])
          .map(
            (entry) => `
              <article class="timeline-item compact-item">
                <strong>${escapeHtml(entry.outbound_id)}</strong>
                <span>${escapeHtml(entry.status)} · ${escapeHtml(entry.source_kind)}</span>
                <span>${escapeHtml(new Date(entry.created_at).toLocaleString())}</span>
              </article>
            `
          )
          .join("") || `<div class="empty-state">这个 dead letter 还没有 replay 历史。</div>`}
      </div>
    </article>
  `;
}

function renderFeishuConfigEditor() {
  const container = qs("feishu-config-editor");
  const channelCards = state.channelBindings
    .filter((binding) => binding.provider === "feishu")
    .map(
      (binding) => `
        <form class="config-card" data-channel-binding-id="${escapeHtml(binding.binding_id)}">
          <div class="card-topline">
            <p class="card-title">${escapeHtml(binding.binding_id)}</p>
            <span class="pill">${escapeHtml(binding.surface)}</span>
          </div>
          <label><span>default route</span><input name="default_route" value="${escapeHtml(binding.default_route)}" /></label>
          <label><span>mention policy</span><input name="mention_policy" value="${escapeHtml(binding.mention_policy)}" /></label>
          <label><span>sync back</span><input name="sync_back_policy" value="${escapeHtml(binding.sync_back_policy)}" /></label>
          <label><span>room policy ref</span><input name="room_policy_ref" value="${escapeHtml(binding.room_policy_ref || "")}" /></label>
          <div class="form-actions inline-actions"><button type="submit" class="secondary">Save</button></div>
        </form>
      `
    )
    .join("");

  const roomCards = state.roomPolicies
    .map(
      (policy) => `
        <form class="config-card" data-room-policy-id="${escapeHtml(policy.room_policy_id)}">
          <div class="card-topline">
            <p class="card-title">${escapeHtml(policy.room_type)}</p>
            <span class="pill">${escapeHtml(policy.room_policy_id)}</span>
          </div>
          <label>
            <span>speaker mode</span>
            <select name="speaker_mode">
              ${["direct", "chief_of_staff_moderated", "mention_fan_out_visible"]
                .map((mode) => `<option value="${mode}" ${policy.speaker_mode === mode ? "selected" : ""}>${mode}</option>`)
                .join("")}
            </select>
          </label>
          <label><span>visible participants</span><input name="visible_participants" value="${escapeHtml((policy.visible_participants || []).join(","))}" /></label>
          <label><span>turn taking rule</span><input name="turn_taking_rule" value="${escapeHtml(policy.turn_taking_rule)}" /></label>
          <label><span>escalation rule</span><input name="escalation_rule" value="${escapeHtml(policy.escalation_rule)}" /></label>
          <div class="form-actions inline-actions"><button type="submit" class="secondary">Save</button></div>
        </form>
      `
    )
    .join("");

  container.innerHTML = `${channelCards}${roomCards}` || `<div class="empty-state">暂无可编辑 Feishu 配置。</div>`;

  container.querySelectorAll("[data-channel-binding-id]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const bindingId = form.getAttribute("data-channel-binding-id");
      const formData = new FormData(form);
      try {
        await apiRequest(`/conversations/channel-bindings/${bindingId}`, {
          method: "PUT",
          body: JSON.stringify({
            default_route: formData.get("default_route"),
            mention_policy: formData.get("mention_policy"),
            sync_back_policy: formData.get("sync_back_policy"),
            room_policy_ref: formData.get("room_policy_ref") || null,
          }),
        });
        renderLastIntake(`Feishu channel binding 已更新：${bindingId}`);
        await refreshAll();
      } catch (error) {
        renderLastIntake(`Feishu channel binding 更新失败：${error.message}`);
      }
    });
  });

  container.querySelectorAll("[data-room-policy-id]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const roomPolicyId = form.getAttribute("data-room-policy-id");
      const formData = new FormData(form);
      try {
        await apiRequest(`/conversations/room-policies/${roomPolicyId}`, {
          method: "PUT",
          body: JSON.stringify({
            speaker_mode: formData.get("speaker_mode"),
            visible_participants: parseCommaList(formData.get("visible_participants")),
            turn_taking_rule: formData.get("turn_taking_rule"),
            escalation_rule: formData.get("escalation_rule"),
          }),
        });
        renderLastIntake(`Room policy 已更新：${roomPolicyId}`);
        await refreshAll();
      } catch (error) {
        renderLastIntake(`Room policy 更新失败：${error.message}`);
      }
    });
  });
}

function renderOpenClawGatewayHealth() {
  const container = qs("openclaw-gateway-health");
  const health = state.openclawGatewayHealth;
  if (!health) {
    container.innerHTML = `<div class="empty-state">Gateway health 暂不可用。</div>`;
    return;
  }
  container.innerHTML = `
    <article class="feishu-card">
      <div class="card-topline">
        <p class="card-title">${escapeHtml(health.status)}</p>
        <span class="pill">${escapeHtml(String(health.reachable))}</span>
      </div>
      <div class="meta-list">
        ${renderMetaRows([
          { label: "gateway", value: health.gateway_base_url || "n/a", code: true },
          { label: "config", value: health.config_path, code: true },
          { label: "sessions", value: String(health.active_session_refs || 0) },
        ])}
      </div>
      ${health.error_detail ? `<div class="card-submeta">${escapeHtml(health.error_detail)}</div>` : ""}
    </article>
  `;
}

function renderOpenClawRuntimeMode() {
  const container = qs("openclaw-runtime-mode");
  const runtimeMode = state.openclawRuntimeMode;
  if (!runtimeMode) {
    container.innerHTML = `<div class="empty-state">Runtime mode 暂不可用。</div>`;
    return;
  }
  container.innerHTML = `
    <article class="feishu-card">
      <div class="card-topline">
        <p class="card-title">${escapeHtml(runtimeMode.runtime_mode)}</p>
        <span class="pill">OpenClaw</span>
      </div>
      <div class="meta-list">
        ${renderMetaRows([
          { label: "base url", value: runtimeMode.gateway_base_url || "n/a", code: true },
          { label: "runtime", value: runtimeMode.runtime_home, code: true },
          { label: "route", value: "backend default = native gateway" },
        ])}
      </div>
      <div class="card-submeta"><a href="${escapeHtml(runtimeMode.control_ui_url)}" target="_blank" rel="noreferrer">Open Control UI</a></div>
    </article>
  `;
}

function renderOpenClawTokenSetup() {
  const container = qs("openclaw-token-setup");
  const setup = state.openclawTokenSetup;
  if (!setup) {
    container.innerHTML = `<div class="empty-state">Control UI access 暂不可用。</div>`;
    return;
  }

  const steps = (setup.setup_steps || [])
    .map((step) => `<li>${escapeHtml(step)}</li>`)
    .join("");

  container.innerHTML = `
    <article class="feishu-card">
      <div class="card-topline">
        <p class="card-title">${setup.pairing_ready ? "Control UI 已可直开" : "Control UI 需检查配对"}</p>
        <span class="pill">${escapeHtml(setup.runtime_mode)}</span>
      </div>
      <div class="meta-list">
        ${renderMetaRows([
          { label: "source", value: `${setup.token_source} → ${setup.token_env_key}` },
          { label: "token", value: setup.token_configured ? "configured in backend env" : "missing" },
          { label: "pairing", value: setup.pairing_ready ? "ready" : "check env / gateway" },
        ])}
      </div>
      <div class="launch-actions">
        <a class="button-link" href="${escapeHtml(setup.launch_url)}" target="_blank" rel="noreferrer">Open Ready Control UI</a>
        <a class="text-link" href="${escapeHtml(setup.control_ui_url)}" target="_blank" rel="noreferrer">Open Raw Control UI</a>
      </div>
      <ol class="setup-steps">${steps}</ol>
    </article>
  `;
}

function renderOpenClawSessions() {
  const container = qs("openclaw-sessions");
  const search = String(qs("openclaw-session-search")?.value || "").trim().toLowerCase();
  const surface = String(qs("openclaw-session-surface-filter")?.value || "").trim();
  const status = String(qs("openclaw-session-status-filter")?.value || "").trim();
  const items = state.openclawSessions.filter((sessionView) => {
    if (surface && sessionView.surface !== surface) {
      return false;
    }
    if (status && sessionView.status !== status) {
      return false;
    }
    if (!search) {
      return true;
    }
    return [
      sessionView.thread_id,
      sessionView.title,
      sessionView.channel_id,
      sessionView.work_ticket_ref || "",
      Object.values(sessionView.openclaw_session_refs || {}).join(" "),
    ]
      .join(" ")
      .toLowerCase()
      .includes(search);
  });
  if (!items.length) {
    container.innerHTML = `<div class="empty-state">当前还没有挂接 OpenClaw session 的线程。</div>`;
    return;
  }
  container.innerHTML = items
    .map(
      (sessionView) => `
        <article class="feishu-card ${sessionView.thread_id === state.selectedOpenClawThreadId ? "is-selected" : ""}" data-openclaw-thread-id="${escapeHtml(sessionView.thread_id)}">
          <div class="card-topline">
            <p class="card-title">${escapeHtml(sessionView.title)}</p>
            <span class="pill">${escapeHtml(sessionView.surface)}</span>
          </div>
          <div class="meta-list">
            ${renderMetaRows([
              { label: "thread", value: sessionView.thread_id, code: true },
              { label: "channel", value: sessionView.channel_id, code: true },
              { label: "status", value: sessionView.status },
            ])}
          </div>
          ${renderTagRow(sessionView.openclaw_session_refs, "subtle")}
        </article>
      `
    )
    .join("");

  container.querySelectorAll("[data-openclaw-thread-id]").forEach((element) => {
    element.addEventListener("click", () => selectOpenClawSession(element.getAttribute("data-openclaw-thread-id")));
  });
}

function renderOpenClawRecentRuns() {
  const container = qs("openclaw-recent-runs");
  const search = String(qs("openclaw-run-search")?.value || "").trim().toLowerCase();
  const surface = String(qs("openclaw-run-surface-filter")?.value || "").trim();
  const status = String(qs("openclaw-run-status-filter")?.value || "").trim();
  const items = state.openclawRecentRuns.filter((run) => {
    if (surface && run.surface !== surface) {
      return false;
    }
    if (status && run.status !== status) {
      return false;
    }
    if (!search) {
      return true;
    }
    return [
      run.runtrace_id,
      run.work_ticket_ref,
      run.thread_ref || "",
      run.model_ref,
      run.strategy,
      run.interaction_mode,
    ]
      .join(" ")
      .toLowerCase()
      .includes(search);
  });
  if (!items.length) {
    container.innerHTML = `<div class="empty-state">最近还没有 native gateway run。</div>`;
    return;
  }
  container.innerHTML = items
    .map(
      (run) => `
        <article class="feishu-card ${run.error_detail ? "is-error" : ""} ${run.runtrace_id === state.selectedOpenClawRunId ? "is-selected" : ""}" data-openclaw-runtrace-id="${escapeHtml(run.runtrace_id)}">
          <div class="card-topline">
            <p class="card-title">${escapeHtml(run.work_ticket_ref)}</p>
            <span class="pill">${escapeHtml(run.strategy)}</span>
          </div>
          <div class="meta-list">
            ${renderMetaRows([
              { label: "model", value: run.model_ref, code: true },
              { label: "status", value: run.status },
              { label: "surface", value: run.surface },
              { label: "at", value: new Date(run.last_event_at).toLocaleString() },
            ])}
          </div>
          ${renderTagRow(run.session_refs, "subtle")}
          ${run.error_detail ? `<div class="card-submeta error-text">${escapeHtml(run.error_detail)}</div>` : ""}
        </article>
      `
    )
    .join("");

  container.querySelectorAll("[data-openclaw-runtrace-id]").forEach((element) => {
    element.addEventListener("click", () => selectOpenClawRun(element.getAttribute("data-openclaw-runtrace-id")));
  });
}

function renderOpenClawSessionDetail() {
  const container = qs("openclaw-session-detail");
  const detail = state.openclawSessionDetail;
  if (!detail) {
    container.innerHTML = `<div class="empty-state">选择一个 session 查看 transcript、session refs 和关联 ticket。</div>`;
    return;
  }
  container.innerHTML = `
    <article class="feishu-card">
      <div class="card-topline">
        <p class="card-title">${escapeHtml(detail.title)}</p>
        <span class="pill">${escapeHtml(detail.surface)}</span>
      </div>
      <div class="meta-list">
        ${renderMetaRows([
          { label: "thread", value: detail.thread_id, code: true },
          { label: "channel", value: detail.channel_id, code: true },
          { label: "ticket", value: detail.work_ticket_ref || "n/a", code: Boolean(detail.work_ticket_ref) },
          { label: "runtrace", value: detail.runtrace_ref || "n/a", code: Boolean(detail.runtrace_ref) },
          { label: "taskgraph", value: detail.taskgraph_ref || "n/a", code: Boolean(detail.taskgraph_ref) },
          { label: "entries", value: String(detail.transcript_count || 0) },
          { label: "last seen", value: detail.last_transcript_at ? new Date(detail.last_transcript_at).toLocaleString() : "n/a" },
        ])}
      </div>
      ${renderTagRow(detail.bound_agent_ids, "subtle")}
      ${renderTagRow(detail.participant_ids, "subtle")}
      ${renderTagRow(detail.openclaw_session_refs, "subtle")}
      ${renderTagRow(detail.recent_run_strategies, "subtle")}
      <div class="detail-list">
        ${(detail.transcript || [])
          .map(
            (entry) => `
              <article class="timeline-item compact-item">
                <strong>${escapeHtml(entry.actor)}</strong>
                <span>${escapeHtml(entry.text)}</span>
                <span>${escapeHtml(new Date(entry.created_at).toLocaleString())}</span>
              </article>
            `
          )
          .join("") || `<div class="empty-state">当前 session 还没有可见 transcript。</div>`}
      </div>
    </article>
  `;
}

function renderOpenClawRunDetail() {
  const container = qs("openclaw-run-detail");
  const detail = state.openclawRunDetail;
  if (!detail) {
    container.innerHTML = `<div class="empty-state">选择一个 native run 查看事件和 session 细节。</div>`;
    return;
  }
  container.innerHTML = `
    <article class="feishu-card ${detail.error_detail ? "is-error" : ""}">
      <div class="card-topline">
        <p class="card-title">${escapeHtml(detail.work_ticket_ref)}</p>
        <span class="pill">${escapeHtml(detail.strategy)}</span>
      </div>
      <div class="meta-list">
        ${renderMetaRows([
          { label: "runtrace", value: detail.runtrace_id, code: true },
          { label: "thread", value: detail.thread_ref || "n/a", code: Boolean(detail.thread_ref) },
          { label: "taskgraph", value: detail.taskgraph_ref || "n/a", code: Boolean(detail.taskgraph_ref) },
          { label: "model", value: detail.model_ref, code: true },
          { label: "mode", value: detail.interaction_mode },
          { label: "status", value: detail.status },
          { label: "trigger", value: detail.trigger_type },
          { label: "events", value: String(detail.event_count || 0) },
        ])}
      </div>
      ${renderTagRow(detail.session_refs, "subtle")}
      ${renderTagRow(detail.dispatch_targets, "subtle")}
      ${renderTagRow(detail.activated_departments, "subtle")}
      ${renderTagRow(detail.visible_speakers, "subtle")}
      ${detail.error_detail ? `<div class="card-submeta error-text">${escapeHtml(detail.error_detail)}</div>` : ""}
      <div class="detail-list">
        ${(detail.events || [])
          .map(
            (event) => `
              <article class="timeline-item compact-item">
                <strong>${escapeHtml(event.event_type)}</strong>
                <span>${escapeHtml(event.message)}</span>
                ${Object.keys(event.metadata || {}).length ? `<span><code>${escapeHtml(JSON.stringify(event.metadata))}</code></span>` : ""}
                <span>${escapeHtml(new Date(event.created_at).toLocaleString())}</span>
              </article>
            `
          )
          .join("")}
      </div>
    </article>
  `;
}

function renderOpenClawHooks() {
  const container = qs("openclaw-hooks");
  const hooks = state.openclawHooks;
  if (!hooks) {
    container.innerHTML = `<div class="empty-state">Hooks 配置暂不可用。</div>`;
    return;
  }
  if (!hooks.entries.length) {
    container.innerHTML = `<div class="empty-state">当前没有声明 OpenClaw hooks entries。</div>`;
    return;
  }
  container.innerHTML = hooks.entries
    .map(
      (entry) => `
        <article class="feishu-card">
          <div class="card-topline">
            <p class="card-title">${escapeHtml(entry.hook_id)}</p>
            <span class="pill">${escapeHtml(String(entry.enabled))}</span>
          </div>
          <div class="meta-list">
            ${renderMetaRows([
              { label: "source", value: entry.source },
              { label: "config", value: summarizeHookConfig(entry.config || {}) },
            ])}
          </div>
        </article>
      `
    )
    .join("");
}

function renderOpenClawIssues() {
  const container = qs("openclaw-issues");
  if (!state.openclawIssues.length) {
    container.innerHTML = `<div class="empty-state">当前没有需要处理的 Gateway / delivery issue。</div>`;
    return;
  }
  container.innerHTML = state.openclawIssues
    .map(
      (issue) => `
        <article class="feishu-card is-error">
          <div class="card-topline">
            <p class="card-title">${escapeHtml(issue.title)}</p>
            <span class="pill">${escapeHtml(issue.severity)}</span>
          </div>
          <div class="meta-list">
            ${renderMetaRows([
              { label: "source", value: issue.source },
              { label: "ref", value: issue.ref || "n/a", code: Boolean(issue.ref) },
            ])}
          </div>
          <div class="card-submeta error-text">${escapeHtml(issue.detail)}</div>
        </article>
      `
    )
    .join("");
}

function renderOpenClawBindings() {
  const container = qs("openclaw-bindings");
  if (!state.openclawBindings.length) {
    container.innerHTML = `<div class="empty-state">当前没有 OpenClaw agent binding。</div>`;
    return;
  }
  container.innerHTML = state.openclawBindings
    .map(
      (binding) => `
        <article class="feishu-card">
          <div class="card-topline">
            <p class="card-title">${escapeHtml(binding.employee_id)}</p>
            <span class="pill">${escapeHtml(binding.openclaw_agent_id)}</span>
          </div>
          <div class="meta-list">
            ${renderMetaRows([
              { label: "workspace", value: binding.workspace_home_ref, code: true },
              { label: "tool", value: binding.tool_profile },
              { label: "sandbox", value: binding.sandbox_profile },
            ])}
          </div>
        </article>
      `
    )
    .join("");
}

function renderOpenClawWorkspaces() {
  const container = qs("openclaw-workspaces");
  if (!state.openclawWorkspaceBundles.length) {
    container.innerHTML = `<div class="empty-state">当前没有 OpenClaw workspace bundle。</div>`;
    return;
  }
  container.innerHTML = state.openclawWorkspaceBundles
    .map(
      (bundle) => `
        <article class="feishu-card">
          <div class="card-topline">
            <p class="card-title">${escapeHtml(bundle.employee_id)}</p>
            <span class="pill">${escapeHtml(bundle.bootstrap_entrypoint)}</span>
          </div>
          <div class="meta-list">
            ${renderMetaRows([
              { label: "workspace", value: bundle.workspace_path, code: true },
              { label: "files", value: String(bundle.bootstrap_files.length) },
            ])}
          </div>
          ${renderTagRow(workspaceFileNames(bundle).slice(0, 5))}
          <div class="card-submeta">channel accounts: <code>${escapeHtml(JSON.stringify(bundle.channel_accounts || {}))}</code></div>
        </article>
      `
    )
    .join("");
}

function renderOpenClawConfigEditor() {
  const container = qs("openclaw-config-editor");
  if (!state.openclawBindings.length) {
    container.innerHTML = `<div class="empty-state">当前没有可编辑的 OpenClaw agent binding。</div>`;
    return;
  }
  container.innerHTML = state.openclawBindings
    .map(
      (binding) => `
        <form class="config-card" data-openclaw-binding-id="${escapeHtml(binding.employee_id)}">
          <div class="card-topline">
            <p class="card-title">${escapeHtml(binding.employee_id)}</p>
            <span class="pill">${escapeHtml(binding.openclaw_agent_id)}</span>
          </div>
          <label><span>tool profile</span><input name="tool_profile" value="${escapeHtml(binding.tool_profile)}" /></label>
          <label><span>sandbox profile</span><input name="sandbox_profile" value="${escapeHtml(binding.sandbox_profile)}" /></label>
          <div class="form-actions inline-actions"><button type="submit" class="secondary">Save + Sync</button></div>
        </form>
      `
    )
    .join("");

  container.querySelectorAll("[data-openclaw-binding-id]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const employeeId = form.getAttribute("data-openclaw-binding-id");
      const formData = new FormData(form);
      try {
        await apiRequest(`/openclaw/bindings/${employeeId}`, {
          method: "PUT",
          body: JSON.stringify({
            tool_profile: formData.get("tool_profile"),
            sandbox_profile: formData.get("sandbox_profile"),
          }),
        });
        renderLastIntake(`OpenClaw binding 已更新：${employeeId}`);
        await refreshAll();
      } catch (error) {
        renderLastIntake(`OpenClaw binding 更新失败：${error.message}`);
      }
    });
  });
}

function renderOpenClawHookEditor() {
  const container = qs("openclaw-hook-editor");
  const entries = state.openclawHooks?.entries || [];
  if (!entries.length) {
    container.innerHTML = `<div class="empty-state">当前没有可编辑的 Hook entry。</div>`;
    return;
  }
  container.innerHTML = entries
    .map(
      (entry) => `
        <form class="config-card" data-openclaw-hook-id="${escapeHtml(entry.hook_id)}">
          <div class="card-topline">
            <p class="card-title">${escapeHtml(entry.hook_id)}</p>
            <span class="pill">${escapeHtml(entry.source)}</span>
          </div>
          <label>
            <span>enabled</span>
            <select name="enabled">
              <option value="true" ${entry.enabled ? "selected" : ""}>true</option>
              <option value="false" ${!entry.enabled ? "selected" : ""}>false</option>
            </select>
          </label>
          <label class="textarea-field">
            <span>config json</span>
            <textarea name="config" rows="4">${escapeHtml(JSON.stringify(entry.config || {}, null, 2))}</textarea>
          </label>
          <div class="form-actions inline-actions"><button type="submit" class="secondary">Save + Sync</button></div>
        </form>
      `
    )
    .join("");

  container.querySelectorAll("[data-openclaw-hook-id]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const hookId = form.getAttribute("data-openclaw-hook-id");
      const formData = new FormData(form);
      try {
        const rawConfig = String(formData.get("config") || "{}").trim();
        const config = rawConfig ? JSON.parse(rawConfig) : {};
        await apiRequest(`/openclaw/gateway/hooks/${hookId}`, {
          method: "PUT",
          body: JSON.stringify({
            enabled: String(formData.get("enabled")) === "true",
            config,
          }),
        });
        renderLastIntake(`OpenClaw hook 已更新：${hookId}`);
        await refreshAll();
      } catch (error) {
        renderLastIntake(`OpenClaw hook 更新失败：${error.message}`);
      }
    });
  });
}

function renderEmployeePacks() {
  const container = qs("employee-packs");
  if (!state.employeePacks.length) {
    container.innerHTML = `<div class="empty-state">还没有 Employee Pack。</div>`;
    return;
  }
  container.innerHTML = state.employeePacks
    .map(
      (pack) => `
        <article class="employee-card">
          <div class="card-topline">
            <p class="card-title">${escapeHtml(pack.employee_name)}</p>
            <span class="pill">${escapeHtml(pack.department)}</span>
          </div>
          <div class="card-meta">${escapeHtml(pack.summary)}</div>
          <ul>
            ${pack.source_persona_packs
              .map((persona) => `<li>${escapeHtml(persona.role_name)}</li>`)
              .join("")}
          </ul>
        </article>
      `
    )
    .join("");
}

function populateEmployeeOptions() {
  const select = qs("bound-agent");
  const current = select.value;
  const options = [
    `<option value="">自动路由</option>`,
    ...state.employeePacks.map(
      (pack) => `<option value="${escapeHtml(pack.employee_id)}">${escapeHtml(pack.employee_name)} · ${escapeHtml(pack.department)}</option>`
    ),
  ];
  select.innerHTML = options.join("");
  if (current) {
    select.value = current;
  }
}

function populateFeishuBotOptions() {
  const select = qs("feishu-app-id");
  const options = state.feishuBots.map(
    (bot) => `<option value="${escapeHtml(bot.app_id)}">${escapeHtml(bot.display_name || bot.employee_id)}</option>`
  );
  select.innerHTML = options.join("");
}

function setupActionButtons(ticket, checkpoints) {
  const executeButton = qs("execute-ticket");
  const restoreButton = qs("restore-ticket");

  executeButton.disabled = !ticket.taskgraph_ref;
  restoreButton.disabled = !checkpoints.length;

  executeButton.onclick = async () => {
    if (!ticket.taskgraph_ref) return;
    try {
      await apiRequest(`/runtime/work-tickets/${ticket.ticket_id}/execute`, { method: "POST" });
      renderLastIntake(`Runtime 已执行：${ticket.title}`);
      await refreshAll();
      await selectTicket(ticket.ticket_id);
    } catch (error) {
      renderLastIntake(`执行失败：${error.message}`);
    }
  };

  restoreButton.onclick = async () => {
    if (!checkpoints.length) return;
    const latest = checkpoints[checkpoints.length - 1];
    try {
      await apiRequest(`/control-plane/checkpoints/${latest.checkpoint_id}/restore`, { method: "POST" });
      renderLastIntake(`Checkpoint 已恢复：${latest.checkpoint_id}`);
      await refreshAll();
      await selectTicket(ticket.ticket_id);
    } catch (error) {
      renderLastIntake(`恢复失败：${error.message}`);
    }
  };
}

async function selectOpenClawSession(threadId) {
  if (!threadId) {
    state.selectedOpenClawThreadId = null;
    state.openclawSessionDetail = null;
    renderOpenClawSessions();
    renderOpenClawSessionDetail();
    return;
  }
  state.selectedOpenClawThreadId = threadId;
  renderOpenClawSessions();
  try {
    state.openclawSessionDetail = await apiRequest(`/openclaw/gateway/sessions/${threadId}`);
    renderOpenClawSessionDetail();
  } catch (error) {
    state.openclawSessionDetail = null;
    renderLastIntake(`加载 OpenClaw session 详情失败：${error.message}`);
    renderOpenClawSessionDetail();
  }
}

async function selectOpenClawRun(runtraceId) {
  if (!runtraceId) {
    state.selectedOpenClawRunId = null;
    state.openclawRunDetail = null;
    renderOpenClawRecentRuns();
    renderOpenClawRunDetail();
    return;
  }
  state.selectedOpenClawRunId = runtraceId;
  renderOpenClawRecentRuns();
  try {
    state.openclawRunDetail = await apiRequest(`/openclaw/gateway/recent-runs/${runtraceId}`);
    renderOpenClawRunDetail();
  } catch (error) {
    state.openclawRunDetail = null;
    renderLastIntake(`加载 OpenClaw native run 详情失败：${error.message}`);
    renderOpenClawRunDetail();
  }
}

function renderLastIntake(message, detail = "") {
  const container = qs("last-intake");
  container.innerHTML = `
    <strong>Last intake</strong>
    <p>${escapeHtml(message)}</p>
    ${detail ? `<p><code>${escapeHtml(detail)}</code></p>` : ""}
  `;
}

function buildParticipantIds(surface, boundAgent) {
  if (surface === "dashboard") {
    return ["ceo"];
  }
  if (surface === "feishu_dm") {
    return ["ceo", boundAgent ? `feishu-${boundAgent}` : "feishu-chief-of-staff"];
  }
  return ["ceo", "feishu-chief-of-staff", ...(boundAgent ? [`feishu-${boundAgent}`] : [])];
}

function defaultChannelFor(surface, boundAgent) {
  if (surface === "dashboard") return "dashboard:ceo";
  if (surface === "feishu_dm") return `feishu:dm:${boundAgent || "chief-of-staff"}`;
  return "feishu:group:project-room";
}

function bindForm() {
  const form = qs("command-form");
  const surfaceSelect = qs("surface");
  const channelInput = qs("channel-id");
  const boundAgentSelect = qs("bound-agent");

  surfaceSelect.addEventListener("change", () => {
    if (!channelInput.dataset.touched) {
      channelInput.value = defaultChannelFor(surfaceSelect.value, boundAgentSelect.value);
    }
  });
  boundAgentSelect.addEventListener("change", () => {
    if (!channelInput.dataset.touched) {
      channelInput.value = defaultChannelFor(surfaceSelect.value, boundAgentSelect.value);
    }
  });
  channelInput.addEventListener("input", () => {
    channelInput.dataset.touched = "true";
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const surface = surfaceSelect.value;
    const intent = qs("intent").value.trim();
    const boundAgent = boundAgentSelect.value;
    const channelId = channelInput.value.trim() || defaultChannelFor(surface, boundAgent);

    if (!intent) {
      renderLastIntake("请先输入 CEO 指令。");
      return;
    }

    const payload = {
      surface,
      channel_id: channelId,
      participant_ids: buildParticipantIds(surface, boundAgent),
      bound_agent_ids: boundAgent ? [boundAgent] : [],
      command: {
        intent,
      },
    };

    try {
      const response = await apiRequest("/conversations/intake", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      state.selectedTicketId = response.command_result.work_ticket.ticket_id;
      renderLastIntake(
        `${response.command_result.classification.interaction_mode} 已创建`,
        response.command_result.work_ticket.ticket_id
      );
      qs("intent").value = "";
      await refreshAll();
      await selectTicket(state.selectedTicketId);
    } catch (error) {
      renderLastIntake(`提交失败：${error.message}`);
    }
  });

  qs("refresh-all").addEventListener("click", refreshAll);
}

function bindFeishuSendForm() {
  const form = qs("feishu-send-form");
  if (!form) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const appId = qs("feishu-app-id").value;
    const chatId = qs("feishu-chat-id").value.trim();
    const text = qs("feishu-text").value.trim();
    const mentions = qs("feishu-mentions").value
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);

    if (!appId || !chatId || !text) {
      renderLastIntake("Feishu test send 缺少 app_id / chat_id / text。");
      return;
    }

    try {
      const response = await apiRequest("/feishu/send", {
        method: "POST",
        body: JSON.stringify({
          app_id: appId,
          chat_id: chatId,
          text,
          mention_employee_ids: mentions,
        }),
      });
      renderLastIntake("Feishu test send 已发送", response.message_id || response.outbound_ref || "sent");
      qs("feishu-text").value = "";
      qs("feishu-mentions").value = "";
      await refreshAll();
    } catch (error) {
      renderLastIntake(`Feishu send 失败：${error.message}`);
    }
  });
}

function bindDashboardFilters() {
  [
    "feishu-dead-letter-search",
    "feishu-replay-audit-search",
    "openclaw-session-search",
    "openclaw-session-surface-filter",
    "openclaw-session-status-filter",
    "openclaw-run-search",
    "openclaw-run-surface-filter",
    "openclaw-run-status-filter",
  ].forEach((id) => {
    const element = qs(id);
    if (!element) {
      return;
    }
    const eventName = element.tagName === "SELECT" ? "change" : "input";
    element.addEventListener(eventName, () => {
      renderFeishuDeadLetters();
      renderFeishuReplayAudit();
      renderOpenClawSessions();
      renderOpenClawRecentRuns();
    });
  });
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function parseCommaList(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

document.addEventListener("DOMContentLoaded", async () => {
  bindForm();
  bindFeishuSendForm();
  bindDashboardFilters();
  await refreshAll();
});
