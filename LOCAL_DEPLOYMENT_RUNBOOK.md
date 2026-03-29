# Local Deployment Runbook

## Project Autonomous Alpha — Local Desktop Deployment

**Reliability Level:** SOVEREIGN TIER (Mission-Critical)
**Target:** Windows 11 + WSL2 + Docker Desktop
**Compose File:** `docker-compose.local.yml`

---

## 1. System Requirements

| Component | Specification |
|-----------|--------------|
| CPU | i7-9700K (8 cores) or equivalent |
| RAM | 16GB total system |
| GPU | NVIDIA GTX 1080 Ti (11GB VRAM) or compatible |
| Storage | HDD or SSD (D: drive for workloads) |
| OS | Windows 11 |
| WSL2 | Ubuntu with `memory=10GB`, `processors=6` |
| Docker | Docker Desktop with WSL2 backend |
| NVIDIA | nvidia-container-toolkit installed in WSL2 |

### WSL2 Configuration

File: `%USERPROFILE%\.wslconfig`

```ini
[wsl2]
memory=10GB
processors=6
swap=4GB
```

After editing, restart WSL:

```powershell
wsl --shutdown
```

### NVIDIA Container Toolkit (WSL2)

```bash
# Inside WSL2 Ubuntu:
distribution=$(. /etc/os-release; echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

Verify:

```bash
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

---

## 2. Resource Allocation

| Service | Memory Limit | CPU Limit | Purpose |
|---------|-------------|-----------|---------|
| ollama | 6 GB | 3.0 | GPU-accelerated LLM (qwen3:8b) |
| app | 2 GB | 2.0 | FastAPI webhook ingress |
| bot | 2 GB | 2.0 | Sovereign Orchestrator loop |
| db | 1.5 GB | 1.0 | PostgreSQL 15 |
| prometheus | 512 MB | 0.5 | Metrics collection |
| grafana | 512 MB | 0.5 | Dashboard visualization |
| email_bridge | 256 MB | 0.5 | Email poller (optional) |
| aura_bridge | 256 MB | 0.5 | MCP bridge (optional) |

**Typical steady-state usage:** 6–8 GB (fits within 10 GB WSL2 limit).

Bridges are behind the `bridges` profile and do not start by default.

---

## 3. How to Start the Stack

### Prerequisites

1. Ensure `.env` file exists in the project root with required secrets
2. Ensure Docker Desktop is running with WSL2 backend
3. Ensure WSL2 is configured per Section 1

### Full Stack (trading + monitoring)

```bash
cd /mnt/d/dev/repos/TRADE_BOT

docker compose -f docker-compose.local.yml up -d --build
```

### Minimal Stack (trading only, saves ~1 GB RAM)

```bash
docker compose -f docker-compose.local.yml up -d db app bot ollama
```

### With Bridges (email + aura)

```bash
docker compose -f docker-compose.local.yml --profile bridges up -d --build
```

### Startup Sequence

The compose file enforces this order via `depends_on`:

```
1. db             (starts first, health-checked)
2. app            (waits for db healthy)
3. bot            (waits for db healthy)
4. ollama         (independent, starts in parallel)
5. prometheus     (waits for app healthy)
6. grafana        (waits for prometheus)
7. email_bridge   (waits for app healthy, profile: bridges)
8. aura_bridge    (waits for db healthy, profile: bridges)
```

---

## 4. How to Stop the Stack

### Graceful Stop (preserves data)

```bash
docker compose -f docker-compose.local.yml down
```

### Stop and Remove Volumes (DESTRUCTIVE — resets all data)

```bash
docker compose -f docker-compose.local.yml down -v
```

### Stop Individual Service

```bash
docker compose -f docker-compose.local.yml stop ollama
```

---

## 5. Health Check Verification

### Check All Service Health

```bash
docker compose -f docker-compose.local.yml ps
```

All critical services should show `(healthy)` status.

### Check Individual Services

```bash
# Database
docker exec aa_local_db pg_isready -U sovereign -d autonomous_alpha

# App (FastAPI)
curl -s http://127.0.0.1:8080/health

# Ollama
curl -s http://127.0.0.1:11434/api/tags

# Prometheus
curl -s http://127.0.0.1:9090/-/healthy

# Grafana
curl -s http://127.0.0.1:3000/api/health
```

---

## 6. Verify GPU Usage

### Check GPU is Visible in Ollama Container

```bash
docker exec aa_local_ollama nvidia-smi
```

Expected: Shows GTX 1080 Ti with VRAM usage.

### Check Ollama is Using GPU

```bash
# Pull the model (first time only)
docker exec aa_local_ollama ollama pull qwen3:8b

# Run a test inference and watch nvidia-smi
docker exec aa_local_ollama ollama run qwen3:8b "Say hello" --verbose
```

If GPU is working, you'll see VRAM usage spike in `nvidia-smi`.

### GPU Not Available?

If NVIDIA toolkit is not installed, remove the `deploy` block from the ollama service in the compose file. Ollama will fall back to CPU inference automatically:

```yaml
  ollama:
    image: ollama/ollama:latest
    # ... keep everything else ...
    # DELETE the deploy: block below
    # deploy:
    #   resources:
    #     reservations:
    #       devices:
    #         - driver: nvidia
    #           count: all
    #           capabilities: [gpu]
```

---

## 7. Verify Ollama Model

### Check Available Models

```bash
curl -s http://127.0.0.1:11434/api/tags | python3 -m json.tool
```

### Pull qwen3:8b (First Time Setup)

```bash
docker exec aa_local_ollama ollama pull qwen3:8b
```

This downloads ~5 GB. Only needs to be done once — the model persists in the `ollama_local_data` volume.

### Verify Model Responds

```bash
curl -s http://127.0.0.1:11434/api/generate \
  -d '{"model":"qwen3:8b","prompt":"What is 2+2?","stream":false}' | \
  python3 -m json.tool
```

### Model Discipline

**ONLY `qwen3:8b` should be pulled.** Do not pull additional models — each model consumes disk space and VRAM. The compose file enforces:

- `OLLAMA_MAX_LOADED_MODELS=1`
- `OLLAMA_KEEP_ALIVE=-1` (keep single model in memory)
- `OLLAMA_NUM_PARALLEL=1`

---

## 8. Monitor Memory Usage

### Container Memory

```bash
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}"
```

### WSL2 Memory

From PowerShell:

```powershell
wsl -- free -h
```

### Check No Container Exceeds Limits

```bash
docker stats --no-stream --format "{{.Name}}: {{.MemUsage}}" | sort
```

All containers should stay below their `mem_limit` values.

---

## 9. Port Map (localhost only)

| Port | Service | URL |
|------|---------|-----|
| 5432 | PostgreSQL | `127.0.0.1:5432` |
| 8080 | FastAPI (app) | `http://127.0.0.1:8080` |
| 11434 | Ollama | `http://127.0.0.1:11434` |
| 9090 | Prometheus | `http://127.0.0.1:9090` |
| 3000 | Grafana | `http://127.0.0.1:3000` |
| 8086 | Aura Bridge | `http://127.0.0.1:8086` (bridges profile) |

All ports are bound to `127.0.0.1` — not accessible from other machines on the network.

---

## 10. Persistent Volumes

| Volume | Service | Contents |
|--------|---------|----------|
| `aa_local_postgres_data` | db | Database files |
| `aa_local_ollama_data` | ollama | Downloaded models (~5 GB for qwen3:8b) |
| `aa_local_prometheus_data` | prometheus | Metrics (30-day retention, 1 GB max) |
| `aa_local_grafana_data` | grafana | Dashboard state |

Volumes survive `docker compose down`. Use `down -v` to delete them.

---

## 11. Troubleshooting

### Container Won't Start

```bash
docker compose -f docker-compose.local.yml logs <service_name>
```

### Database Connection Refused

```bash
# Check db is healthy
docker compose -f docker-compose.local.yml ps db

# Check migrations ran
docker exec aa_local_db psql -U sovereign -d autonomous_alpha -c "\dt"
```

### Ollama Out of Memory

```bash
# Check loaded models
curl -s http://127.0.0.1:11434/api/ps

# If multiple models loaded, restart Ollama
docker compose -f docker-compose.local.yml restart ollama
```

### WSL2 Using Too Much Memory

```powershell
# Check from PowerShell
wsl -- free -h

# If WSL is consuming too much, stop non-essential services
docker compose -f docker-compose.local.yml stop prometheus grafana
```

### GPU Not Detected

1. Verify NVIDIA driver in Windows: `nvidia-smi` in PowerShell
2. Verify nvidia-container-toolkit in WSL2: `nvidia-smi` inside WSL
3. Verify Docker GPU support: `docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi`
4. If all fail, remove the `deploy` block from ollama — it will use CPU

### App Health Check Failing

```bash
# Check app logs
docker compose -f docker-compose.local.yml logs app --tail 50

# Verify FastAPI started
docker exec aa_local_app curl -s http://localhost:8080/health
```

### Restart Everything Clean

```bash
docker compose -f docker-compose.local.yml down
docker compose -f docker-compose.local.yml up -d --build
```

---

## 12. Quick Reference

```bash
# Start full stack
docker compose -f docker-compose.local.yml up -d --build

# Start minimal (no monitoring)
docker compose -f docker-compose.local.yml up -d db app bot ollama

# Check health
docker compose -f docker-compose.local.yml ps

# View logs
docker compose -f docker-compose.local.yml logs -f app bot

# Memory check
docker stats --no-stream

# Stop
docker compose -f docker-compose.local.yml down

# Pull Ollama model (first time)
docker exec aa_local_ollama ollama pull qwen3:8b

# GPU check
docker exec aa_local_ollama nvidia-smi
```
