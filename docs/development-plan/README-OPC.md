# OPC

> An open-source multi-agent system that models real companies — where AI agents communicate **peer-to-peer across departments** based on explicit organizational relationships, and conversations end when **semantic consensus** is reached, not when a hardcoded round counter expires.

**Status:** Design phase · Pre-alpha

<!-- TODO: add badges (license / build / discord) once the project is set up -->

---

## 🎯 What is OPC?

Most multi-agent frameworks today fall into one of two camps:

1. **Top-down task delivery** (Paperclip, CrewAI, AutoGen) — a manager agent assigns tasks to workers; communication flows along a fixed delegation tree.
2. **Hard-coded pipelines** (ChatDev, MetaGPT) — agents pass artifacts through a predefined sequence of roles (CEO → CTO → Programmer → Tester).

Both work for _getting one task done_. Neither captures how real companies actually operate — where **marketing negotiates with engineering**, where **a junior PM pings a senior researcher across reporting lines**, and where **discussions converge naturally** when everyone agrees, not when a token budget runs out.

OPC explores a third path:

> An **organizational graph** drives communication, agents **autonomously choose collaborators** based on relationship type, and dialogues end when **semantic convergence** is detected.

---

## 🚀 Core Innovations

### 1. Relationship Module as a First-Class Citizen

Most frameworks model the org chart as a single reporting tree. OPC defines **four distinct relationship types**, each affecting routing differently:

| Relationship      | Example                        | Affects                          |
| ----------------- | ------------------------------ | -------------------------------- |
| **Reporting**     | CTO → Engineer                 | Authority, approvals             |
| **Collaboration** | PM ↔ Designer                  | Day-to-day cross-functional work |
| **Information**   | Dev → Security (CC)            | Broadcast / awareness only       |
| **Informal**      | Engineer ↔ Engineer (off-team) | Off-the-record consultation      |

The relationship graph is **declarative** (YAML / JSON), **versionable** (lives next to your code), and **renderable** as a visual org chart.

### 2. Autonomous Communication Routing

In existing frameworks, a **central coordinator** decides who talks next:

- AutoGen GroupChat → a `selector` LLM picks the next speaker
- CrewAI Hierarchical → the `manager` agent assigns tasks
- ChatDev → the chat chain is predefined at design time

In OPC, **each agent decides for itself**: _"I need budget approval — that's a reporting-line escalation to Finance"_ or _"I need design input — that's a collaboration-line request to the Design team."_ Routing decisions are made **locally**, based on the agent's current context and the relationship graph.

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

This builds directly on recent academic work (see _Related Research_ below).

---

## 📊 How OPC Differs From Existing Frameworks

| Dimension              | Paperclip      | CrewAI             | ChatDev 2.0      | MacNet             | IoA              | **OPC**                            |
| ---------------------- | -------------- | ------------------ | ---------------- | ------------------ | ---------------- | ---------------------------------- |
| **Positioning**        | Zero-human ops | Task orchestration | Software dev     | Research artifact  | A2A protocol     | **Org collaboration simulation**   |
| **Relationship model** | Reporting only | Delegation chain   | Role description | Topology           | Capability cards | **Multi-type relationship graph**  |
| **Communication**      | Top-down       | Top-down           | Linear chain     | DAG (one-way)      | P2P              | **Multi-directional + structured** |
| **Routing**            | Top-down       | Manager-assigned   | Predefined       | Topology traversal | Capability match | **Relationship-aware**             |
| **Stop condition**     | Budget         | `max_iter`         | Flow end         | DAG terminus       | Task complete    | **Semantic convergence**           |
| **Cross-dept dialog**  | ❌             | ❌                 | ⚠️ Weak          | ❌                 | ✅               | **✅ Core**                        |
| **Department concept** | ✅             | ⚠️                 | ✅               | ❌                 | ❌               | **✅ Core**                        |

---

## 🎬 Target Use Cases

OPC isn't competing with "get-work-done" frameworks like Paperclip. It targets a different category:

- **Organizational simulation** — stress-test how a new team structure would actually communicate before reorganizing
- **Process modeling** — digital twin of cross-departmental approval flows, product launches, incident response
- **Management education** — let students observe AI departments collaborate; more vivid than static case studies
- **Decision-making support** — multi-perspective simulation for investment committees, strategic reviews, M&A scenarios

---

## 🏗️ Architecture (Work in Progress)

```
┌─────────────────────────────────────────────────┐
│              Relationship Graph                  │
│  (reporting / collab / info / informal lines)   │
└──────────────────┬──────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
   ┌────▼─────┐         ┌────▼─────┐
   │ Agent A  │◄───────►│ Agent B  │   ◄── Autonomous routing
   │ (Eng.)   │   ...   │ (Design) │      based on the graph
   └────┬─────┘         └────┬─────┘
        │                     │
        └──────────┬──────────┘
                   │
        ┌──────────▼─────────────┐
        │  Convergence Monitor   │   ◄── Semantic stopping
        │  (consistency, satura.)│
        └────────────────────────┘
```

**Components:**

- **Relationship Module** — declarative org graph with multi-type edges
- **Agent Runtime** — built on [IoA](https://github.com/OpenBMB/IoA) for P2P comms (planned)
- **Routing Engine** — local, relationship-aware decision making
- **Convergence Monitor** — semantic consistency tracker for stop detection
- **Org Designer** — visual editor for defining and tweaking org charts

---

## 📚 Related Research

OPC stands on the shoulders of several recent lines of work:

- **[MacNet (ICLR 2025)](https://arxiv.org/abs/2406.07155)** — graph topology matters; irregular topologies outperform regular ones at scale
- **[OrgAgent (2026)](https://arxiv.org/abs/2604.01020)** — three-layer hierarchies (governance / execution / compliance) beat flat coordination, with both better accuracy and lower token cost
- **[Internet of Agents (ICLR 2025)](https://arxiv.org/abs/2407.07061)** — agent registration & discovery, IM-like architecture, dynamic conversation flow control
- **[Aegean (2025)](https://arxiv.org/abs/2512.20184)** — consensus protocol with early termination when sufficient agents converge
- **[Emergent Convergence (2025)](https://arxiv.org/abs/2512.00047)** — process-level metrics: code stability, semantic self-consistency, lexical confidence
- **[ChatDev (ACL 2024)](https://arxiv.org/abs/2307.07924)** — the original "virtual software company" paradigm
- **[TheAgentCompany (CMU)](https://github.com/TheAgentCompany/TheAgentCompany)** — workplace-simulation benchmark, useful as an evaluation environment

---

## 🛣️ Roadmap

### Phase 0 — Concept & Validation _(now)_

- [x] Literature review across multi-agent frameworks
- [x] Differentiation analysis vs. Paperclip / CrewAI / ChatDev / IoA
- [ ] Two-week prototype: 5–10 agent simulated company
- [ ] Decision: continue as standalone product _or_ fold into existing framework (e.g., IoA / Paperclip plugin)

### Phase 1 — Core Engine

- [ ] Relationship graph data model & loader
- [ ] Basic routing engine (relationship-type aware)
- [ ] Convergence monitor v0 (lexical + embedding-based)
- [ ] Integration with IoA / AutoGen as runtime backend

### Phase 2 — Org Designer

- [ ] Visual org-chart editor
- [ ] Department / role / agent templates
- [ ] Pre-built company archetypes (startup / enterprise / agency)

### Phase 3 — Evaluation

- [ ] Adapt TheAgentCompany scenarios for OPC
- [ ] Process-level metrics dashboard (convergence, fairness, info flow)
- [ ] Comparative benchmarks vs. flat / hierarchical baselines

---

## 🤔 Honest Caveats

I want to be upfront about what's still uncertain:

- **Market is unproven.** "Org simulation" doesn't yet have a clear monetization template.
- **Components are research-grade.** Semantic stopping and dynamic routing are active research areas, not solved problems.
- **Evaluation is hard.** "Did the AI departments collaborate well?" is not trivially measurable.
- **Competitive risk:** Paperclip's planned _Self-Organization_ feature could narrow the gap.

This repo is part exploration, part hypothesis test. Constructive challenge is welcome.

---

## 🤝 Get Involved

- 💬 **Discussion:** open an issue or start a discussion in this repo
- 📧 **Contact:** _[m13230016773@gmail.com]_
- 🔬 **Researchers:** if you work on multi-agent communication, semantic convergence, or organizational AI, I'd love to talk
- 🏢 **Practitioners:** if you've ever tried to digitally model your company's cross-departmental flows and hit a wall, please share what broke

---

## 📋 Update Log

### 2026-05-23 · V1.8.1 — Session Isolation & Orchestration Fixes

**Bug Fixes:**
- **Session Isolation**: `/end` and `/reset` properly isolate gateway sessions. New messages after ending a conversation automatically get a fresh `topic_id` → distinct `session_key` → clean LLM context.
- **Respect HANDOFF: none**: Removed forced handoff fallback. Agents can now reply independently without triggering unwanted multi-agent orchestration.
- **Bot self-reply loop prevention**: `sender_type == "app"` filter prevents bot-to-bot message loops.
- **Summary phase redundancy**: `PhaseOrchestrator` enforces `max_turns=2` and clears participants on summary phases.
- **`/reset` crash fix**: Corrected import error that caused `/reset` to silently fail.

**New Features:**
- `/new` command for fresh conversation topics within the same group.
- Gateway session clear on `/reset` (best-effort).
- Ended thread auto-rotation — no manual `/new` required after `/end`.

**Infrastructure:**
- `app/feishu/commands.py` — command utilities.
- Test coverage: session rotation, commands, dead letter cleanup, work ticket FSM.
- V1.8 enhancement roadmap in `docs/development-plan/v1.8-enhancement-roadmap.md`.

---

## 📄 License

_To be decided (likely Apache-2.0 or MIT)._

---

_OPC is in active design — code is not yet released. This repository currently hosts the design document, research notes, and roadmap. Star to follow along._
