# V1 本机运行与排障手册

这份 runbook 只覆盖当前 `multi-agent-company` 的 V1 本机 Docker 运行形态：

- `app-dev`
- `openclaw-gateway`
- `postgres`
- `redis`
- `qdrant`
- `minio`
- Feishu long connection runner

目标是让本机开发、联调和排障有固定入口，不再靠零散命令记忆。

## 1. 启动顺序

推荐把本机启动流程固化成下面这套命令，不再混用临时命令：

```bash
docker compose up -d postgres redis qdrant minio
make openclaw-sync
docker compose up -d app-dev openclaw-gateway
make feishu-long-conn
```

### 1.1 基础服务

```bash
docker compose up -d postgres redis qdrant minio
```

### 1.2 同步 OpenClaw runtime home

```bash
docker compose run --rm app-dev python -m app.openclaw.runtime_home
```

或：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/openclaw/provision/sync
```

### 1.3 启动主应用与 Gateway

```bash
docker compose up -d app-dev openclaw-gateway
```

### 1.4 启动 Feishu 长连接

```bash
make feishu-long-conn
```

## 2. 核心入口

- Dashboard
  - `http://localhost:8000/dashboard`
- OpenClaw Control UI
  - `http://127.0.0.1:18789/`
- Dashboard 内直开 Control UI
  - `http://localhost:8000/openclaw-control-ui/launch`

## 3. 正常状态检查

### 3.1 应用健康

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/api/v1/system/health
```

### 3.2 Gateway 健康

```bash
curl http://127.0.0.1:18789/healthz
curl http://127.0.0.1:8000/api/v1/openclaw/gateway/health
curl http://127.0.0.1:8000/api/v1/openclaw/gateway/runtime-mode
```

正常时应看到：

- `status = ok` 或 `healthy`
- `runtime_mode = gateway`

### 3.3 hooks 与 workspace

```bash
docker compose exec -T openclaw-gateway openclaw hooks list --json
```

当前本机默认：

- `bootstrap-extra-files = enabled`
- `command-logger = enabled`
- `session-memory = disabled`
- `boot-md = disabled`

### 3.4 Postgres / MinIO / Redis / Qdrant 基线检查

```bash
docker compose exec -T postgres pg_isready -U postgres
docker compose exec -T postgres psql -U postgres -d multi_agent_company -c "SELECT now();"
docker compose exec -T minio sh -lc 'test -d /data && echo minio-data-ok'
docker compose exec -T redis redis-cli ping
curl http://127.0.0.1:6333/healthz
```

检查单：

- `postgres` 必须返回 `accepting connections`
- `minio` 必须存在 `/data`
- `redis` 必须返回 `PONG`
- `qdrant` 必须返回 `healthz` 正常

## 4. Feishu 联调检查

### 4.1 最近入站

```bash
curl "http://127.0.0.1:8000/api/v1/feishu/inbound-events?limit=10"
```

### 4.2 最近出站

```bash
curl "http://127.0.0.1:8000/api/v1/feishu/outbound-messages?limit=10"
curl "http://127.0.0.1:8000/api/v1/feishu/outbound-messages?limit=10&status=failed"
curl "http://127.0.0.1:8000/api/v1/feishu/dead-letters?limit=10"
```

### 4.3 当前可见会话

```bash
curl "http://127.0.0.1:8000/api/v1/openclaw/gateway/sessions"
curl "http://127.0.0.1:8000/api/v1/openclaw/gateway/recent-runs"
curl "http://127.0.0.1:8000/api/v1/openclaw/gateway/issues"
```

## 5. 常见问题

### 5.1 Control UI 显示 `gateway token missing`

先确认你打开的是：

- Dashboard 里的 `Open Ready Control UI`
- 或 `http://localhost:8000/openclaw-control-ui/launch`

不要先打开裸 `http://127.0.0.1:18789/` 再手动排查。

如果 launch 后仍然报 token 问题：

- 检查 `.env` 里是否有 `OPENCLAW_GATEWAY_TOKEN`
- 检查 `app-dev` 与 `openclaw-gateway` 是否重新启动

### 5.2 Control UI 可打开但 `pairing required`

当前本机开发模式依赖：

- `gateway.controlUi.allowInsecureAuth = true`
- `gateway.controlUi.dangerouslyDisableDeviceAuth = true`

如果仍看到 `pairing required`：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/openclaw/provision/sync
docker compose up -d --force-recreate openclaw-gateway
```

### 5.3 后端能调模型，但 Control UI 右上角 `Health Offline`

这通常不是模型路径失效，而是浏览器端 Control UI 自己没连上 Gateway。

先查：

```bash
curl http://127.0.0.1:18789/healthz
docker compose logs --tail=120 openclaw-gateway
```

### 5.4 Feishu 有入站但 bot 没回

先查失败出站：

```bash
curl "http://127.0.0.1:8000/api/v1/feishu/outbound-messages?limit=20&status=failed"
```

再看：

- `attempt_count`
- `error_detail`
- 对应 `RunTrace` 是否有 `feishu_reply_failed`
- `dead-letter` 列表里是否还能看到该出站记录

### 5.5 Dashboard 能开，但 OpenClaw native run 明显不更新

优先看：

```bash
curl "http://127.0.0.1:8000/api/v1/openclaw/gateway/recent-runs"
curl "http://127.0.0.1:8000/api/v1/openclaw/gateway/issues"
docker compose logs --tail=120 openclaw-gateway
```

如果 `recent-runs` 没有新条目，但对话仍在工作，重点检查：

- `OPENCLAW_RUNTIME_MODE` 是否仍是 `gateway`
- `OPENCLAW_GATEWAY_BASE_URL` 是否仍指向 `http://openclaw-gateway:18789`
- `app-dev` 是否在最近重启后回退成 compat 配置

## 6. 备份与恢复

### 6.1 Postgres 备份

```bash
mkdir -p .backup
docker compose exec -T postgres pg_dump -U postgres multi_agent_company > .backup/postgres-$(date +%Y%m%d-%H%M%S).sql
```

### 6.2 Postgres 恢复

```bash
cat .backup/postgres-YYYYMMDD-HHMMSS.sql | docker compose exec -T postgres psql -U postgres multi_agent_company
```

恢复前建议先停掉 `app-dev` 和 Feishu 长连接，避免写入竞争。

### 6.3 MinIO 备份

当前 V1 采用最稳妥的目录级备份：

```bash
mkdir -p .backup
docker compose exec -T minio sh -lc 'tar -czf - /data' > .backup/minio-$(date +%Y%m%d-%H%M%S).tgz
```

### 6.4 MinIO 恢复

```bash
cat .backup/minio-YYYYMMDD-HHMMSS.tgz | docker compose exec -T minio sh -lc 'cd / && tar -xzf -'
```

恢复后需要重启：

```bash
docker compose restart minio app-dev
```

## 7. 密钥轮换检查单

需要统一纳入轮换范围的 key：

- `OPENCLAW_GATEWAY_TOKEN`
- `OPENCLAW_BAILIAN_API_KEY`
- `FEISHU_BOT_APPS_JSON` 中每个 bot 的 `app_secret`
- 如后续外放，再补 `MINIO` 与外部数据库访问凭证

轮换步骤：

1. 更新 `.env`
2. 重新同步 OpenClaw runtime home
3. 重启 `app-dev` 与 `openclaw-gateway`
4. 重启 Feishu 长连接
5. 检查 Dashboard 与 Control UI
6. 用飞书做 4 类真实消息回归

推荐命令：

```bash
make openclaw-sync
docker compose up -d --force-recreate app-dev openclaw-gateway
docker compose rm -sf $(docker ps -aq --filter "name=multi-agent-company-app-dev-run")
make feishu-long-conn
```

## 8. 固定命令集

### 8.1 正式启动

```bash
docker compose up -d postgres redis qdrant minio
make openclaw-sync
docker compose up -d app-dev openclaw-gateway
make feishu-long-conn
```

### 8.2 重启应用面

```bash
docker compose up -d --force-recreate app-dev
```

### 8.3 重启 Gateway

```bash
make openclaw-sync
docker compose up -d --force-recreate openclaw-gateway
```

### 8.4 重启 Feishu 长连接

```bash
docker ps --format '{{.ID}} {{.Names}}' | rg 'multi-agent-company-app-dev-run'
docker rm -f <container-id>
make feishu-long-conn
```

### 8.5 查看核心日志

```bash
docker compose logs --tail=120 app-dev
docker compose logs --tail=120 openclaw-gateway
docker compose logs --tail=120 postgres
docker compose logs --tail=120 minio
```

### 8.6 一键健康检查

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/api/v1/openclaw/gateway/health
curl "http://127.0.0.1:8000/api/v1/feishu/dead-letters?limit=10"
```

## 9. 回归测试

### 6.1 定向回归

```bash
docker compose run --rm app-dev pytest -q tests/test_dashboard_ui.py tests/test_openclaw_api.py tests/test_feishu_api.py tests/test_system_api.py
```

### 6.2 全量回归

```bash
docker compose run --rm app-dev pytest -q
```

## 10. 关闭

```bash
docker compose down
```

如果只想重启 Gateway：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/openclaw/provision/sync
docker compose up -d --force-recreate openclaw-gateway
```
