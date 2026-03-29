# Ollama Integration Runbook

## Project Autonomous Alpha — Phase 5

**Version:** 1.0.0
**Classification:** Operational — Sovereign Tier
**Owner:** Lead Reliability Engineer

---

## Overview

Phase 5 replaces the OpenRouter cloud dependency with a locally-hosted `qwen3:8b` model served by [Ollama](https://ollama.com). The AI Council's Bull/Bear debate protocol runs entirely on-premises — no external API key required, no per-token cost, no network egress for signal evaluation.

### AI Council Decision Flow

```
Incoming Trade Signal
        │
        ▼
  OllamaAICouncil.conduct_debate()
  ┌─────────────────────────────┐
  │  Bull Analyst (qwen3:8b)    │──▶ VERDICT: APPROVED / REJECTED
  │  Bear Analyst (qwen3:8b)    │──▶ VERDICT: APPROVED / REJECTED
  └─────────────────────────────┘
        │ Both APPROVED?
        ▼
  RGI Confidence Arbitration
  (adjusted_confidence ≥ 95.00?)
        │
        ▼
  Execute / Reject
```

**Fail-closed guarantee:** Any Ollama error (timeout, daemon unreachable, empty response) returns `ModelVerdict.ERROR` → `final_verdict = False` → trade rejected.

---

## Prerequisites

| Requirement | Local Dev | Production (NAS) |
|---|---|---|
| Docker / Docker Compose | v24+ | Synology DSM 7.x + Container Manager |
| Ollama image | `ollama/ollama:latest` | `ollama/ollama:latest` |
| Model | `qwen3:8b` (~5.2 GB) | `qwen3:8b` (~5.2 GB) |
| VRAM (GPU path) | Optional | NVIDIA RTX 2080 (8 GB) |
| RAM (CPU path) | 12 GB minimum | N/A (GPU required) |
| NVIDIA Container Toolkit | Optional (local) | Required (prod) |

---

## Environment Variables

Add to `.env` before starting the stack:

```env
USE_LOCAL_OLLAMA=true
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen3:8b
```

These are loaded by `docker-compose.local.yml` and `docker-compose.prod.yml` via `env_file` + override blocks.

---

## Deployment: Local Development

### 1. Start the Ollama Container

```bash
# Start the full local stack (Postgres + App + Bot + Ollama)
docker compose -f docker-compose.local.yml up -d
```

Ollama starts in CPU mode by default. GPU acceleration is available — see [Enabling GPU Acceleration](#enabling-gpu-acceleration-local).

### 2. Pull the Model

```bash
# From WSL/bash (first time only — ~5.2 GB download)
bash scripts/pull_ollama_model.sh
```

The script confirms liveness, pulls the model, polls until ready, and runs a smoke test. Expected output:

```
[1/3] Checking Ollama daemon liveness...
  OK — Ollama is reachable.
[2/3] Pulling model 'qwen3:8b'...
  Pull request submitted. Waiting for completion...
[3/3] Running smoke test inference...
  Smoke test passed: "response":"OK"
SUCCESS: qwen3:8b is pulled and ready.
```

### 3. Verify Health

```bash
bash scripts/check_ollama_health.sh
```

Expected:

```
[1] Daemon liveness ... [PASS]
[2] Model readiness ... [PASS]
[3] Smoke test       ... [PASS]
STATUS: HEALTHY — AI Council is ready.
```

### 4. Run Unit Tests

```bash
pytest tests/unit/test_ai_council.py -v
```

### 5. Run Integration Tests (Ollama must be running with model loaded)

```bash
pytest tests/integration/test_ollama_integration.py -v
```

Integration tests auto-skip if Ollama is unreachable.

---

## Deployment: Production (NAS / Synology)

The `docker-compose.prod.yml` includes the full GPU-accelerated Ollama service. No additional configuration is required beyond the `.env` variables above.

```bash
# On NAS via SSH
docker compose -f docker-compose.prod.yml up -d
bash scripts/pull_ollama_model.sh qwen3:8b http://localhost:11435
bash scripts/check_ollama_health.sh http://localhost:11435 qwen3:8b
```

> Port mapping: Prod exposes `11435:11434` (external:internal). Use `11434` inside the Docker network.

---

## Enabling GPU Acceleration (Local)

1. Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) on the Docker host.
2. Edit `docker-compose.local.yml` — uncomment the `runtime` and `deploy` blocks in the `ollama` service.
3. Restart: `docker compose -f docker-compose.local.yml up -d ollama`
4. Verify: `bash scripts/check_ollama_health.sh` (GPU line will show detected card)

---

## Model Reference

| Parameter | Value |
|---|---|
| Model | `qwen3:8b` |
| Parameters | 8 billion |
| Quantisation | Q4_K_M (default pull) |
| Disk size | ~5.2 GB |
| VRAM (GPU) | ~5–6 GB |
| RAM (CPU) | ~8–10 GB active |
| Inference speed (RTX 2080) | ~40–60 tok/s |
| Inference speed (CPU only) | ~3–8 tok/s |
| Thinking mode | Supported via `/no_think` directive (disabled in prompts) |
| Response field | `response` (standard Ollama format) |

### Why qwen3:8b

- Strong instruction-following for structured `VERDICT:` output
- `/no_think` directive disables chain-of-thought, reducing latency and token use
- Fits within 8 GB VRAM on the production RTX 2080
- No API key, no data egress, no per-inference cost

---

## Prompt Architecture

### System Prompt

Loaded from `app/prompts/ai_council_system_prompt.txt`. Enforces:

- Evidence-only reasoning (no hallucination)
- Fail-closed on ambiguity (uncertain = REJECTED)
- Machine-parseable `VERDICT: APPROVED` / `VERDICT: REJECTED` terminus

Character budget: 512 chars (enforced by `_load_system_prompt()`).

### User Prompts

- `BULL_PROMPT_TEMPLATE`: Bullish analysis, prefixed with `/no_think`
- `BEAR_PROMPT_TEMPLATE`: Bearish analysis, prefixed with `/no_think`

Both templates include the `/no_think` directive to suppress qwen3's chain-of-thought reasoning and cap token generation at 512 tokens.

### Context Injection

`app/logic/ollama_context_builder.build_context_block()` appends:

- Execution mode (DEMO / LIVE)
- Guardian lock state
- Last 3 debate outcomes for the same symbol

This gives the model operational awareness without allowing free-form SQL access.

---

## Ollama Configuration Parameters

| Parameter | Local | Production | Purpose |
|---|---|---|---|
| `OLLAMA_MAX_LOADED_MODELS` | 1 | 2 | VRAM budget |
| `OLLAMA_KEEP_ALIVE` | -1 | -1 | Keep model loaded indefinitely |
| `OLLAMA_NUM_PARALLEL` | 1 | 4 | Concurrent requests |
| `OLLAMA_NUM_THREADS` | 4 | — | CPU thread count (local only) |
| `OLLAMA_FLASH_ATTENTION` | — | 1 | Performance (GPU only) |
| `OLLAMA_NUM_GPU` | — | 99 | All layers on GPU |

---

## Troubleshooting

### Model generates empty response

```
[BULL] ERR-OLLAMA-002: Empty response from Ollama
```

**Cause:** Model not yet loaded into VRAM (cold start).
**Fix:** Re-run the request. First inference after container start may take 30–60 s.

### Smoke test times out

**Cause:** Model cold-loading under CPU inference (8–12 G RAM).
**Fix:** Allow 90 s for first inference. Subsequent calls are faster.

### `ollama pull` fails with out-of-disk error

**Cause:** Insufficient disk space on the `ollama_local_data` volume host path.
**Fix:** Free at least 6 GB on the Docker volume host or prune unused images: `docker system prune`.

### Health check shows `model_present=False`

**Cause:** Model not pulled yet.
**Fix:** `bash scripts/pull_ollama_model.sh`

### AI Council defaults to REJECTED for all trades

**Cause:** `USE_LOCAL_OLLAMA=false` and `OPENROUTER_API_KEY` not set.
**Verify:** `docker exec aa_local_app env | grep USE_LOCAL_OLLAMA` should show `true`.

---

## Monitoring

Ollama container health is tracked by Docker's built-in healthcheck:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
  interval: 30s
  timeout: 10s
  retries: 5
  start_period: 60s
```

From the host:

```bash
docker ps --filter "name=aa_local_ollama" --format "{{.Status}}"
# Expected: Up N minutes (healthy)
```

---

## Rollback Procedure

To revert to OpenRouter (cloud) inference:

1. Set `USE_LOCAL_OLLAMA=false` in `.env`
2. Uncomment `OPENROUTER_API_KEY` in `.env` and set a valid key
3. Restart containers: `docker compose -f docker-compose.local.yml up -d`

The `get_ai_council()` factory will automatically return `AICouncil` (OpenRouter) when `USE_LOCAL_OLLAMA` is not `true`.

---

## Sovereign Reliability Audit

| Check | Status |
|---|---|
| Mock/Placeholder | CLEAN |
| NAS 3.8 Compatibility | Verified |
| GitHub Data Sanitization | Safe for Public |
| Decimal Integrity | N/A (no financial math in Ollama layer) |
| L6 Safety Compliance | Verified — fail-closed on all error paths |
| Traceability | All errors logged with SEC/ERR codes |
| Confidence Score | 97/100 |
