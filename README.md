# Atheris Hub v2.0 - Unified Dual-Node Homelab Dashboard

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Compose_v2-blue.svg)](https://docs.docker.com/compose/)
[![Tailscale](https://img.shields.io/badge/Tailscale-VPN_Mesh-3A3D40.svg)](https://tailscale.com)

**Atheris Hub v2.0** is a production-safe, zero-dependency dual-machine homelab monitoring dashboard and service gateway. Designed specifically for unattended long-distance operation on Fedora Linux nodes connected over Tailscale VPN.

---

## 📐 Architecture & Topology

```
                       [ YOUR WEB BROWSER / TAILSCALE CLIENT ]
                                         │
                                         │ Tailscale Encrypted Tunnel (100.116.47.43:3000)
                                         ▼
                      ┌───────────────────────────────────────┐
                      │    OPTIPLEX - Primary Power Server    │
                      │           (100.116.47.43)             │
                      │                                       │
                      │ ┌───────────────────────────────────┐ │
                      │ │  Atheris Master Hub (Port 3000)   │ │
                      │ │  - Cookie Session Auth Guard      │ │
                      │ │  - Local /proc & Unix Docker Sock │ │
                      │ │  - Serves Dashboard Web UI        │ │
                      │ └─────────────────┬─────────────────┘ │
                      └───────────────────┼───────────────────┘
                                          │
                                          │ Internal Tailscale Fetch (Port 8001)
                                          │ http://100.119.157.55:8001/api/metrics
                                          ▼
                      ┌───────────────────────────────────────┐
                      │      WYSE - Secondary Thin Client     │
                      │           (100.119.157.55)            │
                      │                                       │
                      │ ┌───────────────────────────────────┐ │
                      │ │ Atheris Satellite Agent (Port 8001)│ │
                      │ │ - Threading Python agent          │ │
                      │ │ - Reads local /proc & docker.sock │ │
                      │ │ - Footprint: 15MB RAM / 0MB Disk  │ │
                      │ └───────────────────────────────────┘ │
                      │                                       │
                      │ Active Services: ROMM (3040), GameHub │
                      └───────────────────────────────────────┘
```

---

## 🖥️ Dashboard Features

The dashboard consists of two clean, single-page views:
1. **Login Page (Unauthenticated)**: Custom dark-themed authentication form verifying credentials against `AUTH_USER` and `AUTH_PASS` with secure HTTP-only cookies.
2. **Dashboard Page (Authenticated)**: A clean, single-screen interface containing:
   - **Header Bar**: Branding, live Tailscale status, and Logout button.
   - **Dual-Node Metrics Row**: Live side-by-side cards for OptiPlex Master and Wyse Satellite (CPU, RAM, Disk, Network IO, Uptime). Auto-greys out if Wyse is offline without returning fake metrics.
   - **Service Links Grid**: Grouped quick-launch cards for Media & Storage, AI & Dev Studio, Retro Gaming, and System Admin.
   - **Docker Containers Table**: Dynamic status table rendered live from node container sockets.

---

## 🔑 Environment Variables

Copy `.env.example` to `.env` in the `master/` directory before running:

```env
AUTH_USER=sutej
AUTH_PASS=CHANGE_ME
BIND_IP=100.116.47.43
SESSION_SECRET=CHANGE_ME_64_RANDOM_CHARS
SESSION_EXPIRY_DAYS=7
OPTIPLEX_IP=100.116.47.43
WYSE_IP=100.119.157.55
WYSE_AGENT_PORT=8001
```

---

## 🚀 Deployment Steps (Git Clone Workflow)

### 1. Deploy Satellite Agent on Wyse (Thin Client)
```bash
# SSH into Wyse
ssh sutej@100.119.157.55

# Clone repository
git clone https://github.com/your-username/atheris-hub.git /home/sutej/atheris-hub
cd /home/sutej/atheris-hub/satellite

# Start agent
docker compose up -d

# Confirm health endpoint
curl http://100.119.157.55:8001/api/health
```

### 2. Deploy Master Dashboard on OptiPlex (Power Server)
```bash
# SSH into OptiPlex
ssh sutej@100.116.47.43

# Clone repository
git clone https://github.com/your-username/atheris-hub.git /home/sutej/atheris-hub
cd /home/sutej/atheris-hub/master

# Configure environment credentials
cp ../.env.example .env
nano .env   # Set AUTH_PASS and SESSION_SECRET

# Stop legacy dashboard if binding port 3000
docker stop homepage 2>/dev/null || true

# Start master container
docker compose up -d

# Verify public health endpoint
curl http://100.116.47.43:3000/api/health
```

---

## 🧹 Safe Wyse Storage Cleanup (No Volume Loss)

The Wyse eMMC storage must **NOT** be pruned using `docker system prune -a --volumes -f` as it deletes database volumes (`romm-db`, `romm-redis`, `mariadb`).

```bash
ssh sutej@100.119.157.55

# 1. Stop and remove only duplicate UI containers
docker stop atheris-webui vscode_server jupyter_lab portainer 2>/dev/null || true
docker rm atheris-webui vscode_server jupyter_lab portainer 2>/dev/null || true

# 2. Prune only dangling (unnamed) images and unused build caches
docker image prune -f
docker builder prune -f

# 3. Confirm database volumes remain intact
docker volume ls | grep -E "romm|redis|db|mariadb"
```

---

## ↺ Emergency Rollback Plan

If you need to restore the previous Homepage setup:

```bash
ssh sutej@100.116.47.43

# 1. Stop Atheris Master
cd /home/sutej/atheris-hub/master
docker compose down

# 2. Start legacy Homepage
cd /home/sutej/server-setup/homepage
docker compose up -d

# 3. Confirm Homepage is back at http://100.116.47.43:3000
```

---

## ✈️ Pre-Flight Checklist Before Departure

1. **Disable Tailscale Key Expiry**:
   - Go to [login.tailscale.com/admin/machines](https://login.tailscale.com/admin/machines).
   - Click `...` next to `optiplex` -> **Disable key expiry**.
   - Click `...` next to `sutej.fedora` (Wyse) -> **Disable key expiry**.
2. **Password & Session Security**:
   - Verify `server.py` refuses to start if `AUTH_PASS` is empty or set to `"CHANGE_ME"`.
3. **SSH Remote Keys Test**:
   - Verify non-interactive passwordless SSH access to `100.116.47.43` and `100.119.157.55` works.

---

## 📄 License

Distributed under the [MIT License](LICENSE).
