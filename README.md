# MITRE ATT&CK Threat Analyzer

An AI-powered web application that maps natural-language attack descriptions to the [MITRE ATT&CK](https://attack.mitre.org/) framework. Describe what you observed; the AI agent identifies matching Tactics, Techniques, and Mitigations in real time.

Built with FastAPI + React + Microsoft Agent Framework (MAF) + Azure OpenAI.

---

## Features

- **AI Threat Analysis** — describe attack symptoms in plain language; the MAF agent streams back matched ATT&CK techniques and mitigations
- **MITRE Data Browser** — browse all 14 enterprise tactics, 700+ techniques, and mitigations
- **Keyword Search** — full-text search across the ATT&CK knowledge base
- **Auto Sync** — STIX data pulled from MITRE GitHub daily and on first startup

---

## Prerequisites

### Local development
| Tool | Version |
|---|---|
| Python | 3.11+ |
| Node.js | 20+ |
| Docker + Docker Compose | any recent |

### Azure deployment (additional)
| Tool | Notes |
|---|---|
| Azure CLI (`az`) | [Install](https://learn.microsoft.com/cli/azure/install-azure-cli) |
| Docker | for building the image |
| `jq` | for JSON parsing in deploy scripts |
| Azure subscription | with an existing Resource Group |
| Azure OpenAI / AI Foundry | a deployed chat model (e.g. GPT-4o) |

---

## Local Development

### 1. Clone and configure

```bash
git clone <repo-url>
cd MITRE

cp .env.example .env.local
# Edit .env.local — fill in AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_KEY
```

### 2. Run with Docker Compose (recommended)

```bash
docker compose up --build
```

The app is available at `http://localhost:8000` (frontend + API).
The SQLite database is persisted in `./data/mitre.db`.
On first start, MITRE ATT&CK data syncs automatically (~30–60 s).

### 3. Run without Docker (hot-reload)

**Backend:**
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend** (in a separate terminal):
```bash
cd frontend
npm install
npm run dev          # runs on http://localhost:5173, proxied to backend
```

### 4. Verify

```bash
curl http://localhost:8000/api/v1/health      # {"status":"ok","version":"0.2.0"}
curl http://localhost:8000/api/v1/sync/status # {"status":"success",...} after sync
```

---

## Azure Deployment

### 1. Prerequisites

- An Azure Resource Group already exists
- Azure OpenAI resource with a deployed chat model
- `az login` completed

```bash
az login
az group create --name rg-mitre --location eastus2   # skip if group already exists
```

### 2. Configure resource names

```bash
cp azure/deploy.config.example azure/deploy.config
# Edit azure/deploy.config — set your own resource names
# ACR_NAME and SQL_SERVER_NAME must be globally unique across all of Azure
nano azure/deploy.config
```

### 3. Configure credentials

```bash
cp .env.example .env.local
# Fill in:
#   AZURE_OPENAI_ENDPOINT
#   AZURE_OPENAI_DEPLOYMENT
#   AZURE_OPENAI_API_KEY
#   SQL_ADMIN_LOGIN
#   SQL_ADMIN_PASSWORD
nano .env.local
```

### 4. Provision Azure resources (one time)

Creates ACR, Container Apps environment, Azure SQL Serverless, and the Container App.

```bash
bash azure/setup.sh
```

### 5. Build and deploy

Builds the Docker image (React frontend bundled inside), pushes to ACR, and updates the Container App.

```bash
bash azure/deploy.sh
```

The script automatically runs three post-deployment checks (container health, database, STIX sync) and prints the app URL when complete.

### Re-deploying after code changes

```bash
bash azure/deploy.sh   # every time you push new code
```

### Useful debug commands

```bash
# Live logs
az containerapp logs show --name ca-mitre-backend --resource-group rg-mitre --follow --format text

# Check sync status
curl https://<your-app-url>/api/v1/sync/status

# Trigger a manual sync
curl -X POST https://<your-app-url>/api/v1/sync/trigger
```

---

## Project Structure

```
├── app/                  # Python backend (FastAPI)
│   ├── agent/            # MAF agent + tools
│   ├── api/              # REST endpoints
│   ├── models/           # SQLAlchemy ORM
│   ├── sync/             # STIX downloader + parser + scheduler
│   └── main.py           # App factory + lifespan
├── frontend/             # React + CopilotKit SPA
│   └── src/
├── azure/
│   ├── deploy.config.example  # Resource names template → copy to deploy.config
│   ├── setup.sh               # One-time Azure provisioning
│   └── deploy.sh              # Build + deploy
├── .env.example          # Credentials template → copy to .env.local
├── docker-compose.yml    # Local dev
└── Dockerfile            # Multi-stage: Node (npm build) → Python
```

---

## Environment Variables

See `.env.example` for the full list with descriptions.
Key variables:

| Variable | Required | Description |
|---|---|---|
| `AZURE_OPENAI_ENDPOINT` | Yes | Azure OpenAI / AI Foundry endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT` | Yes | Model deployment name |
| `AZURE_OPENAI_API_KEY` | Local only | API key (production uses Managed Identity) |
| `SQL_ADMIN_LOGIN` | Azure deploy | Azure SQL admin username |
| `SQL_ADMIN_PASSWORD` | Azure deploy | Azure SQL admin password |
| `DATABASE_URL` | Auto-set | SQLite for local; set by deploy.sh for Azure |
| `DEBUG` | No | `true` for local dev, `false` for production |
