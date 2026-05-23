# OPC — One-Person Company

> A multi-agent system that models real companies — where AI agents communicate **peer-to-peer through enterprise IM (Feishu/Lark)** based on explicit organizational relationships, and discussions are **structured by LLM-planned phases** with deterministic orchestration.

**Status:** V1.8 · Phase Discussion + Primary Dispatcher Election · Running in production

---

## 🎯 What is OPC?

Most multi-agent frameworks today fall into one of two camps:

1. **Top-down task delivery** (CrewAI, AutoGen) — a manager agent assigns tasks to workers; communication flows along a fixed delegation tree.
2. **Hard-coded pipelines** (ChatDev, MetaGPT) — agents pass artifacts through a predefined sequence of roles (CEO → CTO → Programmer → Tester).

Both work for *getting one task done*. Neither captures how real companies actually operate — where **marketing negotiates with engineering**, where **a junior PM pings a senior researcher across reporting lines**, and where **discussions converge naturally** when everyone agrees, not when a token budget runs out.

OPC explores a third path:

> Agents communicate **through the same IM channel humans use**, autonomously choose collaborators via **relationship-aware routing**, and discussions are structured by **LLM-planned phases with deterministic execution**.

---

## 🚀 Core Innovations

### 1. Relationship Module as a First-Class Citizen

Most frameworks model the org chart as a single reporting tree. OPC defines **four distinct relationship types**, each affecting routing differently:

| Relationship   | Example                       | Affects                                |
| -------------- | ----------------------------- | -------------------------------------- |
| **Reporting**  | CTO → Engineer                | Authority, approvals                   |
| **Collaboration** | PM ↔ Designer              | Day-to-day cross-functional work       |
| **Information** | Dev → Security (CC)          | Broadcast / awareness only             |
| **Informal**   | Engineer ↔ Engineer (off-team) | Off-the-record consultation            |

The relationship graph is **declarative** (YAML / JSON), **versionable** (lives next to your code), and **renderable** as a visual org chart.

### 2. Autonomous Communication Routing

In existing frameworks, a **central coordinator** decides who talks next:

- AutoGen GroupChat → a `selector` LLM picks the next speaker
- CrewAI Hierarchical → the `manager` agent assigns tasks
- ChatDev → the chat chain is predefined at design time

In OPC, **each agent decides for itself**: *"I need budget approval — that's a reporting-line escalation to Finance"* or *"I need design input — that's a collaboration-line request to the Design team."* Routing decisions are made **locally**, based on the agent's current context and the relationship graph.

### 3. Horizontal & Bi-directional Conversation

Real cross-department communication is **multi-turn, bi-directional, and converges through discussion** — not one-shot artifact handoff.

- MacNet uses DAGs → no cycles, no back-and-forth
- ChatDev's chat chain → strictly sequential
- Paperclip → ticket-based async, no real-time discussion

OPC explicitly supports **departmental dialogues that loop until alignment** — much like an actual meeting.

### 4. Semantic Stop Rules

When does a conversation end? Most systems use crude heuristics:

- `max_rounds = N` (AutoGen, CrewAI)
- `budget = $X` (Paperclip)
- "Manager says done" (hierarchical patterns)

OPC explores **stopping when the discussion itself has converged**:

- **Semantic consistency** — agent positions stabilize across rounds
- **Information saturation** — new turns add little novel content
- **Consensus signaling** — agents explicitly declare alignment
- **Decision crystallization** — an actionable conclusion has emerged

### 5. Hierarchical Memory Architecture

Most multi-agent systems give each agent an isolated memory store, losing organizational knowledge when agents change or conversations end.

OPC implements a **three-layer memory hierarchy** that mirrors how real companies retain knowledge:

| Layer | Scope | Example |
|-------|-------|---------|
| **Company Memory** | Shared across all agents | Company strategy, product decisions, brand guidelines |
| **Department Memory** | Shared within a department | Engineering standards, design system specs, research findings |
| **Agent Private Memory** | Individual agent only | Personal working notes, in-progress drafts, interaction history |

Memory flows **upward** (agent insights promote to department/company level) and **downward** (new agents inherit organizational context immediately). This prevents knowledge silos and ensures continuity when agent sessions reset.

### 6. Layered Skill Catalog

Similarly, OPC's skill system follows the same organizational hierarchy:

| Layer | Scope | Example |
|-------|-------|---------|
| **Company Skills** | Available to all agents | Feishu messaging, document search, calendar access |
| **Department Skills** | Shared within a department | Code review (Engineering), user research (Design), competitor analysis (Research) |
| **Agent-Specific Skills** | Individual agent only | COS: phase planning; Quality Lead: test execution |

This mirrors how real companies operate — everyone can book a meeting room (company skill), only engineers can deploy code (department skill), and only the CTO can approve architecture changes (role-specific skill).

---

## 📊 How OPC Differs From Existing Frameworks

| Dimension              | Paperclip       | CrewAI            | ChatDev 2.0       | MacNet             | IoA                | **OPC**                          |
| ---------------------- | --------------- | ----------------- | ----------------- | ------------------ | ------------------ | -------------------------------- |
| **Positioning**        | Zero-human ops  | Task orchestration | Software dev      | Research artifact  | A2A protocol       | **Org collaboration simulation** |
| **Relationship model** | Reporting only  | Delegation chain  | Role description  | Topology           | Capability cards   | **Multi-type relationship graph** |
| **Communication**      | Top-down        | Top-down          | Linear chain      | DAG (one-way)      | P2P                | **Multi-directional + structured** |
| **Routing**            | Top-down        | Manager-assigned  | Predefined        | Topology traversal | Capability match   | **Relationship-aware**           |
| **Stop condition**     | Budget          | `max_iter`        | Flow end          | DAG terminus       | Task complete      | **Semantic convergence**         |
| **Cross-dept dialog**  | ❌              | ❌                | ⚠️ Weak           | ❌                 | ✅                 | **✅ Core**                       |
| **Department concept** | ✅              | ⚠️                | ✅                | ❌                 | ❌                 | **✅ Core**                       |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Feishu Group Chat                                │
│  User @Agent → structured multi-agent Phase Discussion              │
│  All agent replies visible in real-time                             │
└────────────────────────────┬────────────────────────────────────────┘
                             │ WebSocket Long Connection × 7 bots
┌────────────────────────────▼────────────────────────────────────────┐
│              feishu-long-conn (7 independent processes)              │
│                                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────────┐ │
│  │ Fan-out     │→ │ Primary      │→ │ Source Turn / Orchestration │ │
│  │ (all bots   │  │ Election     │  │ (only primary executes)    │ │
│  │  receive)   │  │ (lock-free)  │  │                            │ │
│  └─────────────┘  └──────────────┘  └────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│           app-dev (FastAPI Control Plane)                            │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Conversation │  │ Work Tickets │  │ Run Traces (full audit)  │  │
│  │ State        │  │ Lifecycle    │  │ + Delivery Guard Epochs  │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│           OpenClaw Gateway (Agent Runtime)                           │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ LLM          │  │ Tool         │  │ Session Memory           │  │
│  │ Orchestration│  │ Execution    │  │ (per agent × per channel)│  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

**Components:**

| Component | Role | Technology |
|-----------|------|-----------|
| **Feishu Group Chat** | Communication surface; human + agent co-exist | Feishu/Lark |
| **feishu-long-conn** | Message dispatch, Primary Election, Phase Orchestration | Python 3.12, multiprocessing |
| **app-dev** | Control plane: state, tickets, traces, API | FastAPI, Pydantic |
| **OpenClaw Gateway** | Agent runtime: LLM calls, tool use, session memory | Node.js |
| **PostgreSQL** | Persistent state store | PostgreSQL 16 |
| **Redis** | Cache, pub/sub | Redis 7 |
| **Qdrant** | Vector memory (agent long-term recall) | Qdrant |
| **MinIO** | Object storage (attachments, large outputs) | MinIO |

---

## 👥 Agents

| Role | Responsibility |
|------|---------------|
| **Chief of Staff** | Intake coordinator. Analyzes requests, plans PHASE_PLAN, delivers final summaries. |
| **Product Lead** | Product strategy, requirements, MoSCoW prioritization, MVP scope. |
| **Research Lead** | Market research, competitive analysis, data source evaluation. |
| **Design Lead** | UX/UI architecture, interaction design, visual direction. |
| **Engineering Lead** | Technical architecture, feasibility assessment, implementation planning. |
| **Quality Lead** | Quality gates, test strategy, GO/NO-GO decisions. |
| **Delivery Lead** | Sprint planning, timeline estimation, cross-team coordination. |

---

## 📚 Related Research

OPC builds on several recent lines of work:

- **[MacNet (ICLR 2025)](https://arxiv.org/abs/2406.07155)** — graph topology matters; irregular topologies outperform regular ones at scale
- **[OrgAgent (2026)](https://arxiv.org/abs/2604.01020)** — three-layer hierarchies (governance / execution / compliance) beat flat coordination
- **[Internet of Agents (ICLR 2025)](https://arxiv.org/abs/2407.07061)** — agent registration & discovery, IM-like architecture, dynamic conversation flow control
- **[Aegean (2025)](https://arxiv.org/abs/2512.20184)** — consensus protocol with early termination when sufficient agents converge
- **[ChatDev (ACL 2024)](https://arxiv.org/abs/2307.07924)** — the original "virtual software company" paradigm
- **[TheAgentCompany (CMU)](https://github.com/TheAgentCompany/TheAgentCompany)** — workplace-simulation benchmark

---

## 🛣️ Roadmap

### V1.0–V1.5 — Foundation ✅
- [x] 7 AI agents with distinct personas on Feishu group chat
- [x] OpenClaw Gateway integration (LLM runtime + session memory)
- [x] Sequential Handoff Queue (agents pass via `HANDOFF:` directives)
- [x] Work ticket lifecycle tracking
- [x] Run trace observability (full audit trail)
- [x] Delivery Guard Epoch (stale response prevention)
- [x] Interruption recovery (user mid-discussion intervention)

### V1.8 — Phase Discussion + Primary Election ✅ *(current)*
- [x] Deterministic Primary Dispatcher Election (lock-free, no central coordinator)
- [x] LLM-planned `PHASE_PLAN` generation by Chief of Staff
- [x] `PhaseOrchestrator` for structured multi-phase discussion execution
- [x] Phase-level turn limits and global turn budget
- [x] Dispatch path observability logging (feishu-long-conn container)
- [x] Non-primary bot skip with debug event recording

### V2.0 — Semantic Convergence *(next)*
- [ ] Semantic consistency detection — agent positions stabilize across rounds
- [ ] Information saturation — new turns add little novel content
- [ ] Consensus signaling — agents explicitly declare alignment
- [ ] Dynamic phase re-planning (COS adjusts phases mid-discussion)

### V2.5 — Relationship Graph
- [ ] Declarative multi-type relationship model (reporting / collaboration / information / informal)
- [ ] Relationship-aware routing engine (local decisions, not central dispatch)
- [ ] Visual org-chart editor
- [ ] Department / role / agent templates

### V3.0 — Evaluation & Benchmarks
- [ ] Adapt TheAgentCompany scenarios for OPC
- [ ] Process-level metrics dashboard (convergence, fairness, information flow)
- [ ] Comparative benchmarks vs. flat / hierarchical baselines

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Feishu bot apps configured (7 bots, one per agent role)
- LLM API access (DeepSeek or compatible)

### Setup

```bash
git clone https://github.com/SenWeiV/multi-agent-company.git
cd multi-agent-company

# Configure environment
cp .env.example .env
# Edit .env with your Feishu bot credentials and LLM API keys

# Start infrastructure
docker compose up -d

# Start Feishu long connections (7 independent bot processes)
docker run -d --name feishu-long-conn \
  --network multi-agent-company_default \
  -v $(pwd):/workspace \
  -w /workspace \
  --env-file .env.example --env-file .env \
  multi-agent-company-app-dev \
  python -m app.feishu.long_connection
```

### Usage

In your Feishu group chat (with all 7 bots added):

```
@Chief of Staff 我想做一个美股科技股实时看板产品
```

The Chief of Staff will:
1. Analyze the request
2. Generate a structured `PHASE_PLAN` (defining phases, leads, participants)
3. Orchestrate multi-phase discussion across relevant agents
4. Deliver a comprehensive response with each department's input

---

## 🤔 Honest Caveats

- **IM-coupling is a trade-off.** Feishu dependency limits portability; future work may abstract the communication layer.
- **Semantic convergence is unsolved.** V1.8 uses turn limits + phase structure as pragmatic boundaries; true semantic stopping is V2.0 research.
- **7 LLM calls per phase turn.** Token cost is meaningful; cost optimization (selective participation, caching) is planned.
- **Single-platform.** Currently Feishu-only; Slack/Teams/Discord adapters are feasible but not built.

---

## 📂 Project Structure

```
app/
├── api/              # FastAPI REST endpoints
├── company/          # Company bootstrap and org models
├── control_plane/    # Run traces, work tickets, observability
├── conversation/     # Thread state, handoff management
├── core/             # Config, logging
├── feishu/           # Feishu integration (dispatch, long connections, Primary Election)
├── orchestration/    # PhaseOrchestrator, plan parser, discussion models
├── openclaw/         # OpenClaw gateway client, agent provisioning
├── persona/          # Agent persona definitions
├── memory/           # Agent memory subsystem
├── skills/           # Skill catalog
└── ui/               # Dashboard frontend
tests/                # Test suite (phase orchestrator, plan parser, integration)
docs/                 # Development plans and roadmaps
```

---

## 📋 Update Log

### 2026-05-23 · V1.8.1 — Session Isolation & Orchestration Fixes

**Bug Fixes:**
- **Session Isolation**: `/end` and `/reset` now properly isolate gateway sessions. After ending a conversation, the next message automatically creates a new `topic_id`, generating a distinct `session_key` — ensuring the LLM sees a clean context with no prior conversation leakage.
- **Respect HANDOFF: none**: Removed forced handoff fallback that previously injected all downstream leads even when the agent explicitly declined handoff. COS can now reply independently without triggering unwanted multi-agent orchestration.
- **Bot self-reply loop prevention**: Added `sender_type == "app"` filter to prevent bot messages from being processed as user input by other bots in the group.
- **Summary phase redundancy**: `PhaseOrchestrator` now enforces constraints on summary phases — clears participants and caps `max_turns=2` to prevent repeated summarization loops.
- **`/reset` crash fix**: Fixed `ImportError` (`get_openclaw_service` → `get_openclaw_provisioning_service`) that caused `/reset` to silently fail.

**New Features:**
- **`/new` command**: Start a fresh conversation topic within the same group chat without needing `/end` + new message.
- **Gateway session clear**: `/reset` now attempts to clear gateway-side sessions (best-effort, graceful failure if gateway doesn't support DELETE).
- **Ended thread auto-rotation**: Messages sent after `/end` automatically create a new topic — no manual `/new` required.

**Infrastructure:**
- Added `app/feishu/commands.py` — command utilities (`generate_topic_id`, command parsing).
- Added test coverage: `test_session_rotation.py`, `test_feishu_commands.py`, `test_dead_letter_cleanup.py`, `test_work_ticket_fsm.py`.
- V1.8 enhancement roadmap documented in `docs/development-plan/v1.8-enhancement-roadmap.md`.

---

## 📄 License

*To be decided (likely Apache-2.0 or MIT).*
