# Multi-Agent Company

A multi-agent orchestration platform that simulates a fully-staffed virtual company. Seven AI agents with distinct roles collaborate autonomously through structured discussions in Feishu (Lark) group chats, powered by LLM backends and the OpenClaw agent runtime.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Feishu Group Chat                            │
│  User @Chief-of-Staff → structured multi-agent discussion       │
└────────────────────────────┬────────────────────────────────────┘
                             │ WebSocket (Long Connection × 7 bots)
┌────────────────────────────▼────────────────────────────────────┐
│              feishu-long-conn (7 processes)                      │
│  Dispatch routing → Primary election → Source turn              │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│           app-dev (FastAPI Control Plane)                        │
│  Conversation state │ Work tickets │ Run traces │ Dashboard UI  │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│           OpenClaw Gateway (Agent Runtime)                       │
│  LLM orchestration │ Tool execution │ Session management        │
└─────────────────────────────────────────────────────────────────┘
```

## Agents

| Role | Responsibility |
|------|---------------|
| **Chief of Staff** | Intake coordinator. Analyzes requests, plans discussion phases, delivers final summaries. |
| **Product Lead** | Product strategy, requirements, MoSCoW prioritization, MVP scope definition. |
| **Research Lead** | Market research, competitive analysis, data source evaluation. |
| **Design Lead** | UX/UI architecture, interaction design, visual direction. |
| **Engineering Lead** | Technical architecture, feasibility assessment, implementation planning. |
| **Quality Lead** | Quality gates, test strategy, GO/NO-GO decisions. |
| **Delivery Lead** | Sprint planning, timeline estimation, cross-team coordination. |

## Key Features

### Phase Discussion (Structured Multi-Agent Collaboration)
When a user messages the group, the Chief of Staff produces a `PHASE_PLAN` that defines structured discussion phases with designated leads and participants. The `PhaseOrchestrator` then executes each phase in order, ensuring focused and productive multi-agent collaboration rather than unstructured chatter.

### Primary Dispatcher Election
In Feishu group chats, all 7 bots receive every message. A deterministic election ensures **only one bot** (the @mentioned agent) processes the message as the primary dispatcher. Others skip immediately, preventing duplicate or competing responses.

### OpenClaw Agent Runtime
Each agent runs as an autonomous LLM-powered process with:
- Persistent session memory per channel
- Tool execution capabilities
- Structured output parsing (PHASE_PLAN, HANDOFF, TURN_COMPLETE directives)

### Control Plane
- Conversation threading and state management
- Work ticket lifecycle tracking
- Run trace observability (full audit trail of every agent action)
- Delivery guard epochs (preventing stale responses)

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.12, FastAPI, Pydantic |
| Agent Runtime | OpenClaw Gateway (Node.js) |
| LLM | DeepSeek V4 Pro (configurable) |
| Chat Platform | Feishu/Lark (WebSocket long connections) |
| Database | PostgreSQL 16 |
| Cache | Redis 7 |
| Vector DB | Qdrant |
| Object Store | MinIO |
| Deployment | Docker Compose |

## Project Structure

```
app/
├── api/              # FastAPI REST endpoints
├── company/          # Company bootstrap and org models
├── control_plane/    # Run traces, work tickets, observability
├── conversation/     # Thread state, handoff management
├── core/             # Config, logging
├── feishu/           # Feishu integration (dispatch, long connections)
├── orchestration/    # PhaseOrchestrator, plan parser, discussion models
├── openclaw/         # OpenClaw gateway client, agent provisioning
├── persona/          # Agent persona definitions
├── memory/           # Agent memory subsystem
├── skills/           # Skill catalog
└── ui/               # Dashboard frontend
tests/                # Comprehensive test suite
docs/                 # Development plans and roadmaps
scripts/              # Operational utilities
```

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Feishu bot apps configured (7 bots, one per agent role)
- LLM API access (DeepSeek or compatible)

### Setup

```bash
# Clone
git clone https://github.com/SenWeiV/multi-agent-company.git
cd multi-agent-company

# Configure environment
cp .env.example .env
# Edit .env with your Feishu bot credentials and LLM API keys

# Start infrastructure
docker compose up -d

# Start Feishu long connections (in a separate terminal)
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
2. Generate a structured PHASE_PLAN
3. Orchestrate multi-phase discussion across relevant agents
4. Deliver a comprehensive response with each department's input

## Configuration

Key environment variables (see `.env.example` for full list):

| Variable | Description |
|----------|-------------|
| `FEISHU_BOT_APPS_JSON` | JSON array of 7 bot configurations |
| `OPENCLAW_GATEWAY_API_KEY` | LLM API key for agent reasoning |
| `OPENCLAW_GATEWAY_TOKEN` | Gateway authentication token |
| `FEISHU_VISIBLE_HANDOFF_TURN_LIMIT` | Max turns per conversation (default: 20) |

## Development

```bash
# Run tests
python -m pytest tests/ -v

# Check logs (Feishu message processing)
docker logs feishu-long-conn -f

# Check logs (Agent runtime)
docker logs multi-agent-company-openclaw-gateway -f

# Clean agent sessions (reset state)
docker exec multi-agent-company-openclaw-gateway \
  sh -c 'rm -f /home/node/.openclaw/agents/opc-*/sessions/*.jsonl*'
```

## License

Private project. All rights reserved.
