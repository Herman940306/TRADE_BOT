# Server Migration Preparation

**Project:** Autonomous Alpha (Trade_Bot) v1.9.0
**Target Server:** tower.local (Shared Home Server — Unraid)
**Allowed Workspace:** `\\tower.local\herman\Herman\New_Trade_Bot`
**Date:** 2026-03-29
**Author:** Deployment Sub-Agent
**Status:** INITIAL ASSESSMENT

---

## 1. Mission

Migrate the Autonomous Alpha trading bot into the allowed folder on tour.local, a shared home server, without disrupting any existing services, containers, networks, volumes, or other users' workloads.

**Core Objectives:**

1. Deploy New_Trade_Bot safely into the designated folder only
2. Coexist with all existing Docker workloads — zero interference
3. Produce a reversible, incremental, non-destructive deployment path
4. Never bind to ports, claim networks, or consume resources already in use
5. All operator secrets supplied manually — never copied from dev machine
6. No live/production trading on first server boot — DEMO/PAPER mode only

---

## 2. Server Safety Rules

### Non-Negotiable Constraints

| # | Rule | Consequence of Violation |
|---|------|--------------------------|
| 1 | All work MUST stay inside `\\tower.local\herman\Herman\New_Trade_Bot` | Server-wide impact |
| 2 | No stopping, restarting, or modifying unrelated Docker containers | Other users lose service |
| 3 | No global Docker commands (`docker system prune`, `docker volume prune`, etc.) | Data loss for others |
| 4 | No claiming ports without verified availability | Port conflict crashes services |
| 5 | No modifying reverse proxies, system configs, or shared infrastructure | Broad-scope damage |
| 6 | No moving files outside the allowed workspace | Scope violation |
| 7 | No assuming ownership of any existing container, network, or volume | Namespace collision |
| 8 | No `docker compose down` against unrelated stacks | Service outage |
| 9 | No destructive commands at any phase | Irreversible damage |
| 10 | Shared server safety takes absolute priority over deployment convenience | Mission integrity |

### Command Blacklist (NEVER Execute on This Server)

```bash
# FORBIDDEN — these affect ALL Docker workloads
docker system prune
docker volume prune
docker network prune
docker container prune
docker image prune -a
docker stop $(docker ps -q)
docker rm $(docker ps -aq)
docker compose down          # (when not scoped to THIS project)
systemctl restart docker
```

---

## 3. Allowed Workspace

### Path

```
\\tower.local\herman\Herman\New_Trade_Bot
```

Equivalent Linux path on the server (probable Unraid mapping):

```
/mnt/user/herman/Herman/New_Trade_Bot
```

> **Note:** The exact Linux-side mount path must be confirmed by the operator before
> running any `docker compose` commands, since Docker Compose bind-mount paths must
> use the server's local filesystem path, not the SMB/UNC path.

### Scope Boundary

- ✅ Read, write, create, delete files **inside** `New_Trade_Bot/`
- ✅ Build Docker images from Dockerfiles **inside** this folder
- ✅ Run `docker compose` commands scoped to **this project only**
- ❌ No modifications to `Legacy_Trade_Bot/` or `MCP_Server/` (sibling folders)
- ❌ No modifications to parent folder structure
- ❌ No writes anywhere outside this path

### Observed Sibling Folders

| Folder | Status |
|--------|--------|
| `Legacy_Trade_Bot/` | **DO NOT TOUCH** — may be running or archived |
| `MCP_Server/` | **DO NOT TOUCH** — may be active |
| `New_Trade_Bot/` | ✅ **This is our workspace** (currently empty) |

---

## 4. Read-Only Environment Discovery

### 4.1 Server Accessibility

| Check | Result |
|-------|--------|
| SMB path reachable from dev machine | ✅ Yes (`Test-Path` returned True) |
| `New_Trade_Bot/` folder exists | ✅ Yes |
| `New_Trade_Bot/` contents | ✅ Empty (0 files/folders) |
| Sibling folders visible | ✅ `Legacy_Trade_Bot/`, `MCP_Server/` |

### 4.2 What Could NOT Be Safely Determined (Requires SSH or Operator Input)

The following discovery items require server-side SSH access or operator-provided information. They **cannot** be determined via SMB share alone and must be resolved before deployment:

| Item | Why It Matters | How to Resolve |
|------|----------------|----------------|
| Docker version installed | Compose V2 syntax support | `docker --version` via SSH |
| Docker Compose version | V1 vs V2 plugin (`docker compose` vs `docker-compose`) | `docker compose version` via SSH |
| Running containers list | Name collision avoidance | `docker ps --format '{{.Names}}'` via SSH |
| Existing Docker networks | Network naming collision avoidance | `docker network ls` via SSH |
| Existing Docker volumes | Volume naming collision avoidance | `docker volume ls` via SSH |
| Ports currently in use | Port binding safety | `ss -tlnp` or `docker ps --format '{{.Ports}}'` via SSH |
| GPU/NVIDIA runtime availability | Ollama GPU acceleration | `nvidia-smi` via SSH |
| Server OS and architecture | Image compatibility (amd64 vs arm64) | `uname -m` via SSH |
| Linux-side mount path for SMB share | Docker bind-mount correctness | Operator must confirm |
| Available disk space | Image/volume storage | `df -h` via SSH |
| Available RAM | Container memory limits | `free -h` via SSH |
| Existing PostgreSQL on port 5432 | Port conflict (noted in prod compose) | `ss -tlnp | grep 5432` via SSH |

### 4.3 Safe Discovery Commands (For Operator to Run via SSH)

The operator should run these **read-only** commands and share results before deployment:

```bash
# --- System Info ---
uname -a
cat /etc/os-release 2>/dev/null || cat /etc/unraid-version 2>/dev/null
free -h
df -h /mnt/user/herman/Herman/New_Trade_Bot
nproc

# --- Docker Info ---
docker --version
docker compose version
docker info --format '{{.ServerVersion}}'

# --- Running Containers (names only) ---
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | sort

# --- Docker Networks ---
docker network ls --format 'table {{.Name}}\t{{.Driver}}\t{{.Scope}}'

# --- Docker Volumes ---
docker volume ls --format 'table {{.Name}}\t{{.Driver}}'

# --- Ports in Use ---
ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null

# --- GPU (optional) ---
nvidia-smi 2>/dev/null || echo "No NVIDIA GPU detected"

# --- Exact path of SMB share mount ---
ls -la /mnt/user/herman/Herman/New_Trade_Bot/
```

---

## 5. Project Folder Inventory

### 5.1 Target Folder Status

**`\\tower.local\herman\Herman\New_Trade_Bot`** is currently **EMPTY**.

All project files will need to be transferred from the dev repository at `d:\dev\repos\TRADE_BOT`.

### 5.2 Source Project Files (From Dev Repository)

#### Docker Deployment Files

| File | Purpose | Target Compose |
|------|---------|----------------|
| `docker-compose.yml` | Dev PostgreSQL only | Development |
| `docker-compose.local.yml` | Full local stack (DB + App + Bot + Ollama) | Local dev/testing |
| `docker-compose.prod.yml` | **Production stack (8 services)** | **Server deployment** |
| `docker-compose.test.yml` | Test runner stack | CI/testing |
| `Dockerfile` | Production bot image (main.py orchestrator) | Prod bot service |
| `Dockerfile.local` | Local dev image (uvicorn HTTP server) | Local app service |
| `Dockerfile.test` | Test runner image | Test execution |

#### Environment Templates

| File | Purpose | Contains Secrets? |
|------|---------|-------------------|
| `.env.example` | General env template | ❌ Placeholders only |
| `.env.live.example` | Live trading env template (progressive modes) | ❌ Placeholders only |
| `.env` | **ACTIVE dev environment** | ⚠️ **YES — REAL API KEYS & PASSWORDS** |

#### Key Application Directories

| Directory | Size | Purpose |
|-----------|------|---------|
| `app/` | ~25,000 LOC | FastAPI application, exchange, logic, schemas |
| `services/` | ~8,500 LOC | Core trade, HITL, Guardian services |
| `data_ingestion/` | ~400 LOC | Market data adapters |
| `database/migrations/` | 26 SQL files | PostgreSQL schema migrations |
| `scripts/` | 20+ files | Operational scripts, validation, monitoring |
| `tests/` | 39 files | Unit, property, integration tests |
| `jobs/` | 4 files | Background jobs (RGI, simulation) |
| `tools/` | 4 files | Utilities |
| `grafana/` | dashboards + provisioning | Grafana auto-provisioning |
| `prometheus/` | 1 config file | Prometheus scrape config |
| `bridge/` | 3 files | Email bridge + Dockerfile |
| `aura_bridge/` | 6 files | MCP AI assistant bridge + Dockerfile |
| `frontend/` | Vite + React + Tailwind | Frontend (not yet deployed) |
| `data/` | JSON state files | Demo broker state, guardian audit |
| `logs/` | Runtime logs | Application logs |

### 5.3 Secrets Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| `.env` file contains real API keys (VALR, Binance), DB passwords, HMAC secrets | 🔴 **CRITICAL** | **DO NOT copy `.env` to server.** Create a fresh `.env` on the server from `.env.live.example` with newly generated secrets. |
| `docker-compose.prod.yml` contains hardcoded default password `sovereign_secret_2024` | 🟡 **MEDIUM** | Override via `POSTGRES_PASSWORD` env var (template already supports this) |
| `.gitignore` excludes `.env*` files | ✅ | Secrets are not in git |
| `data/demo_broker_state.json` may contain trade state | 🟢 **LOW** | Start fresh on server — do not copy dev state |

---

## 6. Docker Coexistence Assessment

### 6.1 Production Compose Services (docker-compose.prod.yml)

The production stack defines **8 services**:

| Service | Container Name | Host Port | Image | Risk Level |
|---------|---------------|-----------|-------|------------|
| `db` | `autonomous_alpha_db` | 5433:5432 | postgres:15-alpine | 🟡 Port + name collision risk |
| `bot` | `autonomous_alpha_bot` | 8085:8080 | Custom build | 🟡 Port collision risk |
| `email_bridge` | `autonomous_alpha_bridge` | None | Custom build | 🟢 Low risk |
| `prometheus` | `autonomous_alpha_prometheus` | 9095:9090 | prom/prometheus:v2.48.0 | 🟡 Port collision risk |
| `grafana` | `autonomous_alpha_grafana` | 3005:3000 | grafana/grafana:latest | 🟡 Port collision risk |
| `cloudflare-tunnel` | `autonomous_alpha_tunnel` | None | cloudflare/cloudflared:latest | 🟢 Low risk |
| `aura_bridge` | `autonomous_alpha_aura` | 8086:8086 | Custom build | 🟡 Port collision risk |
| `ollama` | `autonomous_alpha_ollama` | 11435:11434 | ollama/ollama:latest | 🟡 Port + GPU collision risk |

### 6.2 Naming Strategy Assessment

**Current Names (from docker-compose.prod.yml):**

- Container prefix: `autonomous_alpha_*`
- Network: `sovereign_network`
- Volumes: `autonomous_alpha_postgres_data`, `autonomous_alpha_prometheus_data`, `autonomous_alpha_grafana_data`, `autonomous_alpha_ollama_data`

**Risk:** If the `Legacy_Trade_Bot` sibling folder runs the same compose file, container names, network names, and volume names **will collide**.

**Recommendation — Project-Scoped Naming:**

All names should be prefixed with a unique project identifier. The compose `COMPOSE_PROJECT_NAME` variable should be set explicitly:

```bash
# In .env on the server:
COMPOSE_PROJECT_NAME=new_tradebot
```

This will automatically prefix all container names, networks, and volumes with `new_tradebot_`, ensuring isolation.

**Alternative:** Explicitly rename all container names in the compose file to use a unique prefix like `ntb_*` (new trade bot).

### 6.3 Recommended Safe Naming Convention

| Resource | Current Name | Safe Name |
|----------|-------------|-----------|
| Compose project | (default from folder) | `new_tradebot` |
| DB container | `autonomous_alpha_db` | `ntb_db` |
| Bot container | `autonomous_alpha_bot` | `ntb_bot` |
| Network | `sovereign_network` | `ntb_network` |
| Volume (postgres) | `autonomous_alpha_postgres_data` | `ntb_postgres_data` |
| Volume (prometheus) | `autonomous_alpha_prometheus_data` | `ntb_prometheus_data` |
| Volume (grafana) | `autonomous_alpha_grafana_data` | `ntb_grafana_data` |
| Volume (ollama) | `autonomous_alpha_ollama_data` | `ntb_ollama_data` |

### 6.4 Network Isolation

The prod compose defines a single bridge network (`sovereign_network`). This is already good isolation practice — containers communicate internally and only exposed ports are reachable externally.

**Recommendation:** Rename the network to `ntb_network` (or use `COMPOSE_PROJECT_NAME` auto-prefixing) to guarantee no collisions with any existing Docker network on the server.

**The project should NOT use the default bridge network or any host-mode networking.**

---

## 7. Port and Network Safety Assessment

### 7.1 Ports Requested by Production Compose

| Host Port | Internal Port | Service | Conflict Risk |
|-----------|---------------|---------|---------------|
| **5433** | 5432 | PostgreSQL | 🟡 Unknown — must verify via SSH |
| **8085** | 8080 | Bot API (webhook, health, HITL) | 🟡 Unknown — must verify |
| **9095** | 9090 | Prometheus | 🟡 Unknown — must verify |
| **3005** | 3000 | Grafana | 🟡 Unknown — must verify |
| **8086** | 8086 | Aura MCP Bridge | 🟡 Unknown — must verify |
| **11435** | 11434 | Ollama LLM | 🟡 Unknown — must verify |

**Total: 6 host ports need verification.**

### 7.2 Port Selection Rationale (From Existing Compose)

The prod compose already uses **non-standard host ports** to avoid conflicts:

- PostgreSQL on **5433** (not 5432) — comment says "NAS has native Postgres on 5432"
- Prometheus on **9095** (not 9090)
- Grafana on **3005** (not 3000)
- Bot on **8085** (not 8080)
- Ollama on **11435** (not 11434)

This is good practice, but **still requires verification** against the shared server's active ports.

### 7.3 Port Verification Script (For Operator)

```bash
# Run on the server via SSH — READ-ONLY
for port in 5433 8085 9095 3005 8086 11435; do
  result=$(ss -tlnp 2>/dev/null | grep ":${port} " || echo "FREE")
  echo "Port ${port}: ${result}"
done
```

### 7.4 Fallback Port Plan

If any port is in use, the operator must choose an alternative. Suggested fallback ranges:

| Service | Primary | Fallback Range |
|---------|---------|----------------|
| PostgreSQL | 5433 | 5434–5439 |
| Bot API | 8085 | 8087–8099 |
| Prometheus | 9095 | 9096–9099 |
| Grafana | 3005 | 3006–3019 |
| Aura Bridge | 8086 | 8087–8099 |
| Ollama | 11435 | 11436–11439 |

### 7.5 Internal-Only Option

For maximum safety on first deployment, **all host port bindings can be removed**. Services communicate via the internal Docker network. Only the bot's webhook port needs external exposure (and only if TradingView webhooks are configured to reach it).

```yaml
# Example: bind to localhost only (not externally reachable)
ports:
  - "127.0.0.1:8085:8080"
```

---

## 8. Volume and Data Safety Assessment

### 8.1 Named Volumes (Production Compose)

| Volume Name | Service | Data Risk | Collision Risk |
|-------------|---------|-----------|----------------|
| `autonomous_alpha_postgres_data` | PostgreSQL | Trade history, audit trail | 🔴 If Legacy_Trade_Bot uses same name |
| `autonomous_alpha_prometheus_data` | Prometheus | Metrics TSDB | 🟡 Medium |
| `autonomous_alpha_grafana_data` | Grafana | Dashboard state | 🟡 Medium |
| `autonomous_alpha_ollama_data` | Ollama | Model weights (~5GB) | 🟡 Medium |

### 8.2 Bind Mounts (Production Compose)

| Host Path | Container Path | Mode | Risk |
|-----------|---------------|------|------|
| `./logs` | `/app/logs` | RW | 🟢 Project-scoped |
| `./data` | `/app/data` | RW | 🟢 Project-scoped |
| `./data/budget_reports` | `/app/data/budget_reports` | RO | 🟢 Project-scoped |
| `./database/migrations` | `/docker-entrypoint-initdb.d` | RO | 🟢 Project-scoped |
| `./prometheus/prometheus.yml` | `/etc/prometheus/prometheus.yml` | RO | 🟢 Project-scoped |
| `./grafana/provisioning/*` | `/etc/grafana/provisioning/*` | RO | 🟢 Project-scoped |
| `./grafana/dashboards` | `/var/lib/grafana/dashboards` | RO | 🟢 Project-scoped |

**Bind mounts are relative to the compose file location** — they are inherently project-scoped and safe.

### 8.3 Volume Naming Recommendation

Rename all named volumes with the `ntb_` prefix to guarantee uniqueness:

```yaml
volumes:
  ntb_postgres_data:
    name: ntb_postgres_data
  ntb_prometheus_data:
    name: ntb_prometheus_data
  ntb_grafana_data:
    name: ntb_grafana_data
  ntb_ollama_data:
    name: ntb_ollama_data
```

### 8.4 Data Persistence Strategy

- **PostgreSQL data:** Persisted in Docker named volume. Survives container restarts.
- **Application state:** `data/` bind mount stores `demo_broker_state.json`, `guardian_lock.json`. Start empty on first deploy.
- **Logs:** `logs/` bind mount. Start empty.
- **Ollama models:** Persisted in Docker named volume. Models must be pulled after first startup (`docker exec ntb_ollama ollama pull qwen3:8b`).

### 8.5 Volume Cleanup Safety

If rollback is needed:

- ✅ Remove ONLY volumes prefixed with `ntb_*`
- ❌ NEVER run `docker volume prune` (would destroy other users' volumes)

---

## 9. Safe Deployment Strategy

### Phase 1: File Readiness

```bash
# 1a. Verify target folder is empty
ls -la /path/to/New_Trade_Bot/

# 1b. Clone or copy project files into allowed folder
# Option A: Git clone (preferred — clean, auditable)
cd /path/to/New_Trade_Bot
git clone https://github.com/Herman940306/TRADE_BOT.git .

# Option B: SCP from dev machine (if no git on server)
# scp -r d:\dev\repos\TRADE_BOT\* user@tower.local:/path/to/New_Trade_Bot/

# 1c. Verify critical files
ls -la docker-compose.prod.yml Dockerfile requirements.txt app/ database/ services/
```

### Phase 2: Safe Environment Preparation

```bash
# 2a. Create fresh .env from template (NEVER copy dev .env)
cp .env.live.example .env

# 2b. Generate unique secrets for this server instance
python3 -c "import secrets; print(f'POSTGRES_PASSWORD={secrets.token_hex(16)}')"
python3 -c "import secrets; print(f'DB_PASSWORD={secrets.token_hex(16)}')"
python3 -c "import secrets; print(f'SOVEREIGN_SECRET={secrets.token_hex(32)}')"
python3 -c "import secrets; print(f'GUARDIAN_ADMIN_TOKEN={secrets.token_hex(16)}')"
python3 -c "import secrets; print(f'GUARDIAN_RESET_CODE={secrets.token_hex(16)}')"

# 2c. Edit .env with generated values (use nano/vi)
nano .env

# 2d. Set EXECUTION_MODE=DEMO (PAPER mode — NO live trading on first boot)
# This should already be the default in .env.live.example

# 2e. Confirm .env has no placeholder markers left
grep '<.*>' .env  # Should return nothing
```

### Phase 3: Compose Configuration Validation (No Containers Started)

```bash
# 3a. Validate compose file syntax (does NOT start anything)
docker compose -f docker-compose.prod.yml config

# 3b. Verify container names don't collide with running containers
docker ps --format '{{.Names}}' | grep -i "autonomous_alpha\|ntb_\|sovereign" || echo "No collisions"

# 3c. Verify volume names don't collide
docker volume ls --format '{{.Name}}' | grep -i "autonomous_alpha\|ntb_\|sovereign" || echo "No collisions"

# 3d. Verify network names don't collide
docker network ls --format '{{.Name}}' | grep -i "sovereign\|ntb_" || echo "No collisions"
```

### Phase 4: Isolated Image Build (No Containers Started)

```bash
# 4a. Build images only — does NOT start containers
docker compose -f docker-compose.prod.yml build

# 4b. Verify built images
docker images | grep -i "autonomous\|ntb\|trade"
```

### Phase 5: Minimal Service Test Boot

```bash
# 5a. Start ONLY the database first (lowest risk)
docker compose -f docker-compose.prod.yml up -d db

# 5b. Wait for health check
docker compose -f docker-compose.prod.yml ps db
# Verify: STATUS = "Up ... (healthy)"

# 5c. If DB is healthy, start the bot
docker compose -f docker-compose.prod.yml up -d bot

# 5d. Check bot health
docker compose -f docker-compose.prod.yml logs --tail=50 bot

# 5e. Verify bot health endpoint (if port is exposed)
curl -s http://localhost:8085/health || echo "Health check pending..."
```

### Phase 6: Health Verification

```bash
# 6a. Confirm ONLY this project's containers are running
docker compose -f docker-compose.prod.yml ps

# 6b. Confirm no unrelated containers were affected
docker ps --format 'table {{.Names}}\t{{.Status}}' | sort

# 6c. Verify database migrations applied
docker compose -f docker-compose.prod.yml exec db psql -U sovereign -d autonomous_alpha -c "\dt"

# 6d. Verify DEMO/PAPER mode is active (check bot logs)
docker compose -f docker-compose.prod.yml logs bot | grep -i "EXECUTION_MODE\|DEMO\|PAPER"
```

### Phase 7: Staged Additional Service Enablement

Only after core (db + bot) are proven stable:

```bash
# 7a. Start Prometheus + Grafana (monitoring)
docker compose -f docker-compose.prod.yml up -d prometheus grafana

# 7b. Start Ollama (if GPU available — OPTIONAL)
docker compose -f docker-compose.prod.yml up -d ollama

# 7c. Start email bridge (OPTIONAL — only if TradingView email alerts needed)
docker compose -f docker-compose.prod.yml up -d email_bridge

# 7d. Start aura bridge (OPTIONAL — for AI assistant integration)
docker compose -f docker-compose.prod.yml up -d aura_bridge

# 7e. Start tunnel (OPTIONAL — for external webhook ingress)
docker compose -f docker-compose.prod.yml up -d cloudflare-tunnel
```

### Deployment Order Summary

```
Phase 1: Files → Phase 2: .env → Phase 3: Validate → Phase 4: Build
    → Phase 5: db → bot → Phase 6: Verify → Phase 7: Optional services
```

**At NO point should `docker compose up` be called without the `-d` flag and service specifier.** Always bring up services individually.

---

## 10. Non-Destructive Test Plan

### 10.1 Pre-Deployment Validation (Before Starting Containers)

| # | Test | Command | Expected Result |
|---|------|---------|-----------------|
| T1 | Compose syntax valid | `docker compose -f docker-compose.prod.yml config` | Prints resolved YAML without errors |
| T2 | Images build successfully | `docker compose -f docker-compose.prod.yml build --no-cache` | Build completes without errors |
| T3 | No container name collisions | `docker ps --format '{{.Names}}' \| grep "autonomous_alpha"` | No matches (or explicitly different prefix) |
| T4 | No volume name collisions | `docker volume ls --format '{{.Name}}' \| grep "autonomous_alpha"` | No matches (or explicitly different prefix) |
| T5 | No network name collisions | `docker network ls --format '{{.Name}}' \| grep "sovereign_network"` | No matches |
| T6 | Target ports are free | `ss -tlnp \| grep -E '5433\|8085\|9095\|3005\|8086\|11435'` | No matches (ports free) |
| T7 | .env file has no placeholders | `grep '<.*>' .env` | No matches |
| T8 | .env file is not dev copy | Verify EXECUTION_MODE=DEMO | Must be DEMO, not LIVE |

### 10.2 Post-Startup Validation (After Starting Containers)

| # | Test | Command | Expected Result |
|---|------|---------|-----------------|
| T9 | DB container healthy | `docker inspect ntb_db --format '{{.State.Health.Status}}'` | `healthy` |
| T10 | Bot container running | `docker inspect ntb_bot --format '{{.State.Status}}'` | `running` |
| T11 | Health endpoint responds | `curl -sf http://localhost:8085/health` | 200 OK |
| T12 | Metrics endpoint responds | `curl -sf http://localhost:8085/metrics` | 200 OK with Prometheus metrics |
| T13 | Database has tables | `docker exec ntb_db psql -U sovereign -d autonomous_alpha -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"` | Count > 0 |
| T14 | Bot in DEMO mode | `docker logs ntb_bot 2>&1 \| grep -i "EXECUTION_MODE"` | Shows DEMO or DRY_RUN |
| T15 | No unrelated container changes | `docker ps --format '{{.Names}}\t{{.Status}}'` | All pre-existing containers unchanged |

### 10.3 Network Isolation Validation

| # | Test | Command | Expected Result |
|---|------|---------|-----------------|
| T16 | Project network exists | `docker network inspect ntb_network` | Network details shown |
| T17 | Only project containers on network | `docker network inspect ntb_network --format '{{range .Containers}}{{.Name}} {{end}}'` | Only `ntb_*` containers |
| T18 | Bot can reach DB internally | `docker exec ntb_bot curl -sf http://db:5432 2>&1 \|\| echo "connection attempted"` | Connection attempted (expected — DB is not HTTP) |

### 10.4 Volume Path Validation

| # | Test | Command | Expected Result |
|---|------|---------|-----------------|
| T19 | Postgres volume exists | `docker volume inspect ntb_postgres_data` | Volume details shown |
| T20 | Bind mount logs/ exists | `ls -la /path/to/New_Trade_Bot/logs/` | Directory exists |
| T21 | Bind mount data/ exists | `ls -la /path/to/New_Trade_Bot/data/` | Directory exists |

---

## 11. Rollback Plan

### Scope: This Project ONLY

All rollback actions affect **exclusively** the New_Trade_Bot deployment. No unrelated Docker resources are touched.

### Step 1: Stop This Project's Containers

```bash
cd /path/to/New_Trade_Bot
docker compose -f docker-compose.prod.yml down
```

This stops and removes **only** containers defined in this compose file.

### Step 2: Verify No Unrelated Impact

```bash
# Confirm all other containers are still running
docker ps --format 'table {{.Names}}\t{{.Status}}' | sort
```

### Step 3: Remove This Project's Volumes (If Operator Chooses)

**Conservative option** (keep data for retry):

```bash
# Volumes are preserved — container can be restarted later
echo "Volumes preserved. Restart with: docker compose -f docker-compose.prod.yml up -d"
```

**Full cleanup option** (remove all project data):

```bash
# Remove ONLY this project's named volumes
docker volume rm ntb_postgres_data ntb_prometheus_data ntb_grafana_data ntb_ollama_data 2>/dev/null
# These commands will fail harmlessly if volumes don't exist or use the old names
docker volume rm autonomous_alpha_postgres_data autonomous_alpha_prometheus_data autonomous_alpha_grafana_data autonomous_alpha_ollama_data 2>/dev/null
```

### Step 4: Remove Built Images (Optional)

```bash
# Remove ONLY this project's custom-built images
docker images | grep -E "new_trade_bot|ntb_" | awk '{print $3}' | xargs -r docker rmi
```

### Step 5: Remove Project Network (If Orphaned)

```bash
docker network rm ntb_network 2>/dev/null || true
docker network rm sovereign_network 2>/dev/null || true
```

### What Is NEVER Part of Rollback

- ❌ `docker system prune`
- ❌ `docker volume prune`
- ❌ `docker network prune`
- ❌ Deleting folders outside `New_Trade_Bot/`
- ❌ Stopping any container not in this project's compose file

---

## 12. Explicit Do-Not-Touch List

### Containers

- ❌ **DO NOT** stop, restart, remove, or inspect internals of any container not owned by this project
- ❌ **DO NOT** run `docker stop` or `docker rm` without specifying exact project container names
- ❌ **DO NOT** assume any running container can be safely restarted

### Docker Resources

- ❌ **DO NOT** run `docker system prune` (destroys unused images/containers/networks server-wide)
- ❌ **DO NOT** run `docker volume prune` (destroys unnamed volumes across all projects)
- ❌ **DO NOT** run `docker network prune` (removes idle networks that may be needed by stopped containers)
- ❌ **DO NOT** run `docker image prune -a` (removes all untagged images server-wide)

### Networks

- ❌ **DO NOT** delete or modify any Docker network not created by this project
- ❌ **DO NOT** connect this project's containers to existing third-party networks
- ❌ **DO NOT** use `host` networking mode (exposes all container ports without isolation)

### Ports

- ❌ **DO NOT** bind to any port without first verifying it is free via `ss -tlnp`
- ❌ **DO NOT** assume a port is free because "it's an unusual number"
- ❌ **DO NOT** bind to port 80, 443, or any commonly used port without explicit operator approval

### Files and Configuration

- ❌ **DO NOT** edit any file outside `New_Trade_Bot/`
- ❌ **DO NOT** modify `Legacy_Trade_Bot/` or `MCP_Server/` folders
- ❌ **DO NOT** edit system-level Docker daemon config (`/etc/docker/daemon.json`)
- ❌ **DO NOT** modify any reverse proxy configuration (nginx, traefik, caddy, etc.)
- ❌ **DO NOT** overwrite `.env` files without creating a backup first
- ❌ **DO NOT** copy the dev machine's `.env` file to the server (contains real API keys)

### Server Operations

- ❌ **DO NOT** restart the Docker daemon (`systemctl restart docker`)
- ❌ **DO NOT** reboot the server
- ❌ **DO NOT** modify cron jobs, systemd services, or boot scripts
- ❌ **DO NOT** change user permissions outside this project folder
- ❌ **DO NOT** install system-level packages without operator approval

---

## 13. Required Operator Inputs

The following inputs are **required** from the operator before deployment can proceed safely. Each item is critical and cannot be assumed.

### Must-Have (Blocking)

| # | Input | Purpose | How to Provide |
|---|-------|---------|----------------|
| 1 | **Linux-side path** of `New_Trade_Bot` | Docker bind-mount correctness | Run `realpath /mnt/user/herman/Herman/New_Trade_Bot` |
| 2 | **Output of discovery commands** (Section 4.3) | Port/name collision avoidance | Run commands via SSH, share output |
| 3 | **Docker & Docker Compose versions** on server | Compose file syntax compatibility | `docker --version && docker compose version` |
| 4 | **Chosen safe port numbers** (or confirm defaults) | Port binding without conflicts | After running port check script |
| 5 | **COMPOSE_PROJECT_NAME** decision | Container/volume/network isolation | Choose a unique prefix (e.g., `ntb`) |
| 6 | **Fresh `.env` secrets** generated on server | Security — never copy dev secrets | Generate per Section 9, Phase 2 |

### Should-Have (Before Full Stack)

| # | Input | Purpose | Default If Not Provided |
|---|-------|---------|-------------------------|
| 7 | Whether **frontend** should be exposed initially | Scope control | No — backend only |
| 8 | Whether deployment is **paper-only** or includes live-read-only | Safety | DEMO/PAPER only |
| 9 | Whether server has **NVIDIA GPU** for Ollama | Ollama service config | CPU-only mode |
| 10 | **Available RAM** on server | Memory limit tuning | Use compose defaults |
| 11 | **Available disk space** | Volume/image storage planning | Minimum 10GB needed |
| 12 | Whether **Cloudflare Tunnel** should be started | External webhook ingress | No — internal only first |

### Nice-to-Have (Later Phases)

| # | Input | Purpose |
|---|-------|---------|
| 13 | Whether reverse proxy integration is desired later | External HTTPS access |
| 14 | Whether Discord webhook URL is available | Trade notifications |
| 15 | Whether VALR API credentials are ready | Exchange integration (read-only first) |
| 16 | Backup schedule preferences | Data protection |

---

## 14. Final Migration Readiness Verdict

### Assessment Summary

| Category | Status | Notes |
|----------|--------|-------|
| Target folder exists and is empty | ✅ READY | Clean deployment surface |
| Project files ready for transfer | ✅ READY | Full codebase in dev repo |
| Docker compose files available | ✅ READY | Prod compose with 8 services |
| Env templates available | ✅ READY | `.env.live.example` with progressive modes |
| Container naming strategy | ⚠️ NEEDS ACTION | Must set `COMPOSE_PROJECT_NAME` or rename containers |
| Port availability verified | ❌ UNKNOWN | Requires server-side `ss -tlnp` check |
| Network collision check | ❌ UNKNOWN | Requires `docker network ls` on server |
| Volume collision check | ❌ UNKNOWN | Requires `docker volume ls` on server |
| Running container names checked | ❌ UNKNOWN | Requires `docker ps` on server |
| Server OS/arch confirmed | ❌ UNKNOWN | Must be amd64 Linux |
| Docker version confirmed | ❌ UNKNOWN | Need Compose V2 |
| GPU availability confirmed | ❌ UNKNOWN | Needed for Ollama GPU mode |
| Secrets generated for server | ❌ NOT YET | Must generate fresh secrets on server |
| Linux-side mount path confirmed | ❌ UNKNOWN | Needed for bind-mount paths |

### Verdict

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│   VERDICT: PARTIAL — MORE SAFE DISCOVERY NEEDED                        │
│                                                                         │
│   The project is structurally ready for deployment.                     │
│   The target folder is clean and accessible.                            │
│   The compose file, Dockerfiles, and env templates are complete.        │
│                                                                         │
│   HOWEVER, server-side read-only discovery has not been performed.      │
│   We cannot confirm port availability, naming collisions, Docker        │
│   version compatibility, or resource availability without SSH access    │
│   to the server.                                                        │
│                                                                         │
│   NEXT STEP: Operator must run the read-only discovery commands from    │
│   Section 4.3 via SSH and share the output.                             │
│                                                                         │
│   Once discovery output is received, this document will be updated      │
│   to READY or BLOCKED with specific findings.                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Conditions to Upgrade to READY

1. ✅ Server-side discovery commands output received and analyzed
2. ✅ No port collisions found (or fallback ports chosen)
3. ✅ No container/volume/network naming collisions found
4. ✅ Docker Compose V2 confirmed available
5. ✅ Linux-side mount path confirmed
6. ✅ Fresh `.env` generated on server with unique secrets
7. ✅ `COMPOSE_PROJECT_NAME` or renamed containers applied

### Pre-Migration Checklist (For Operator)

- [ ] Run all discovery commands from Section 4.3 and share output
- [ ] Confirm Linux-side path of New_Trade_Bot
- [ ] Confirm Docker and Docker Compose versions
- [ ] Verify all 6 target ports are free (or choose alternatives)
- [ ] Decide on `COMPOSE_PROJECT_NAME` (recommend: `ntb`)
- [ ] Decide whether to start with paper-only or include read-only live
- [ ] Confirm whether GPU is available for Ollama
- [ ] Confirm available disk space ≥ 10GB
- [ ] Confirm available RAM ≥ 2GB for core services (db + bot)

---

## Appendix A: Files Inspected

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Dev compose (PostgreSQL only) |
| `docker-compose.local.yml` | Local dev stack (4 services) |
| `docker-compose.prod.yml` | Production stack (8 services) — **primary deployment file** |
| `docker-compose.test.yml` | Test runner stack |
| `Dockerfile` | Production bot image |
| `Dockerfile.local` | Local dev image |
| `Dockerfile.test` | Test runner image |
| `.env.example` | General env template |
| `.env.live.example` | Live trading env template |
| `.env` | Active dev env (**contains real secrets — DO NOT COPY**) |
| `.gitignore` | Confirms .env is excluded |
| `prometheus/prometheus.yml` | Prometheus scrape config |
| `DEPLOYMENT.md` | Existing deployment guide (Synology NAS focused) |
| `NAS_QUICK_START.md` | Empty — not yet written |

## Appendix B: Safe Discovery Commands Used

| Command | Scope | Purpose |
|---------|-------|---------|
| `Test-Path "\\tower.local\..."` | Read-only | Verify path exists |
| `Get-ChildItem "\\tower.local\..."` | Read-only | List folder contents |
| `Select-String .env` (masked) | Read-only | Assess secrets presence |
| `Select-String .gitignore` | Read-only | Verify .env exclusion |

## Appendix C: Top Risks

| # | Risk | Severity | Mitigation |
|---|------|----------|------------|
| 1 | Port collision with existing services | 🟡 High | Verify via SSH before binding |
| 2 | Container name collision with Legacy_Trade_Bot | 🟡 High | Use unique `COMPOSE_PROJECT_NAME` |
| 3 | Copying dev `.env` with real API keys to server | 🔴 Critical | Generate fresh secrets on server |
| 4 | Volume name collision with Legacy_Trade_Bot | 🟡 High | Use unique volume name prefix |
| 5 | Starting in LIVE mode accidentally | 🔴 Critical | `.env.live.example` defaults to DEMO |
| 6 | GPU contention if Ollama runs alongside other GPU workloads | 🟡 Medium | Confirm GPU availability first |
| 7 | Disk space exhaustion from Docker images/volumes | 🟡 Medium | Verify ≥ 10GB free |
| 8 | Bind-mount path mismatch (SMB vs Linux filesystem) | 🟡 High | Confirm Linux path via SSH |
