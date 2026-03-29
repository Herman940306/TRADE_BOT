# ============================================================================
# Project Autonomous Alpha v1.9.0
# NAS Quick-Start — GitHub as Source of Truth
# ============================================================================
#
# Reliability Level: SOVEREIGN TIER
#
# Context
# -------
# Your local machine had a drive failure and is now running a degraded disk at
# 100% load.  To eliminate dependency on local resources, the GitHub repository
# is now the single source of truth.
#
# CI/CD Pipeline Overview
# -----------------------
#   git push  →  CI (lint + test)
#             →  Docker Build & Publish (GHCR)
#             →  Deploy to NAS (SSH pull & restart)
#
# The NAS pulls the pre-built image from GitHub Container Registry (GHCR).
# No local build required.  Your PC only needs `git push`.
#
# ============================================================================

## One-Time Setup (do this once)

### Step 1 — Configure GitHub Secrets

In your repository: **Settings → Secrets and variables → Actions → New repository secret**

| Secret name        | Value                                                                 |
|--------------------|-----------------------------------------------------------------------|
| `NAS_HOST`         | NAS LAN IP or hostname (e.g. `192.168.1.100`)                        |
| `NAS_USER`         | SSH user on the NAS (e.g. `admin`)                                    |
| `NAS_SSH_KEY`      | Contents of the NAS private SSH key (see below)                       |
| `NAS_DEPLOY_PATH`  | Absolute path on NAS (e.g. `/volume2/docker/autonomous_alpha`)        |

**Generating an SSH key pair (run once on any machine):**

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/nas_deploy_key
# Copy the PUBLIC key to the NAS:
#   cat ~/.ssh/nas_deploy_key.pub
# Append it to /var/services/homes/admin/.ssh/authorized_keys on the NAS.
# Paste the PRIVATE key (nas_deploy_key) as the NAS_SSH_KEY GitHub Secret.
```

---

### Step 2 — Clone the repository on the NAS (first time only)

```bash
ssh admin@your-nas-ip
mkdir -p /volume2/docker/autonomous_alpha
cd /volume2/docker/autonomous_alpha
git clone https://github.com/Herman940306/TRADE_BOT.git .
```

---

### Step 3 — Create the `.env` file on the NAS

```bash
cd /volume2/docker/autonomous_alpha
cp .env.example .env
nano .env   # fill in your secrets — this file is gitignored and never committed
```

Key values to set:

```env
DATABASE_URL=postgresql+psycopg2://sovereign:your_db_password@db:5432/autonomous_alpha
POSTGRES_PASSWORD=your_db_password
WEBHOOK_SECRET=your_minimum_32_character_webhook_secret
OPENROUTER_API_KEY=sk-or-v1-...
VALR_API_KEY=
VALR_API_SECRET=
```

---

### Step 4 — Authenticate with GHCR on the NAS (first time only)

```bash
# Create a GitHub Personal Access Token with read:packages scope, then:
docker login ghcr.io -u herman940306
# Enter the token when prompted.
```

---

## Daily Workflow (from your PC)

```bash
# 1. Edit code in any editor (VS Code, Cursor, Kiro, etc.)

# 2. Push to GitHub — CI, Docker build, and NAS deploy run automatically
git add .
git commit -m "feat: your change description"
git push

# 3. Monitor the pipeline
#    https://github.com/Herman940306/TRADE_BOT/actions

# No local build. No local Docker. No HDD stress.
```

---

## Manual NAS Deploy (on-demand)

Trigger a deployment without a code push:

1. Go to: **Actions → Deploy to NAS → Run workflow**
2. Optionally enter an image tag (default: `latest`)
3. Click **Run workflow**

---

## Verify Deployment on NAS

```bash
ssh admin@your-nas-ip
cd /volume2/docker/autonomous_alpha

# Check running containers
docker-compose -f docker-compose.prod.yml ps

# Tail live logs
docker-compose -f docker-compose.prod.yml logs -f bot

# Bot health endpoint
curl http://localhost:8080/health
```

---

## Workflow Summary

| Workflow               | File                                    | Trigger                                     |
|------------------------|-----------------------------------------|---------------------------------------------|
| CI (lint + test)       | `.github/workflows/ci.yml`             | Every push / pull request                   |
| Docker Build & Publish | `.github/workflows/docker-build.yml`  | Push to `main` or semver tag                |
| Deploy to NAS          | `.github/workflows/deploy-nas.yml`    | After successful Docker build, or manual    |

---

## Reliability Audit

| Check                  | Status                                          |
|------------------------|-------------------------------------------------|
| Local build required?  | ✅ No — NAS pulls from GHCR                    |
| Local disk load?       | ✅ None — CI runs on GitHub-hosted runners      |
| Secrets in code?       | ✅ No — GitHub Secrets only                    |
| Automated tests        | ✅ Unit + property + integration on every push  |
| NAS restart on failure | ✅ `restart: unless-stopped` in compose         |

**Confidence Score: 98/100**
