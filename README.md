# Atheris Hub v2.0  Unified dual-node homelab dashboard. Monitors two Fedora machines over Tailscale, aggregates metrics and Docker container status, and links to all your services behind a custom login page.  ## Features  - **Dual-node metrics**: CPU, RAM, Disk, Network IO, Uptime for both machines - **Live Docker status**: Every container, auto-refreshed every 5 seconds - **Service launcher**: Grid of clickable cards for all your web tools - **Custom login page**: Cookie session auth, no Basic Auth popup - **Zero dependencies**: Pure Python stdlib + vanilla JS, no build step - **Tailscale-native**: Binds to Tailscale IP only, no public exposure  ## Architecture  +-----------------------------------------+ | OptiPlex (Master) | | 100.116.47.43:3030 | | +---------------------------------+ | | | Atheris Master (Python) | | | | - Cookie-session login | | | | - Reads local /proc | | | | - Reads /var/run/docker.sock | | | | - Polls Wyse agent every 5s | | | +---------------------------------+ | +------------------+----------------------+ | Tailscale mesh v +-----------------------------------------+ | Wyse 5070 (Satellite) | | 100.119.157.55:8001 | | +---------------------------------+ | | | Atheris Satellite (Python) | | | | - Serves /proc metrics JSON | | | | - Docker container inspector | | | +---------------------------------+ | +-----------------------------------------+ text   ## Requirements  - Two Linux hosts (Fedora 44 tested) with:   - Docker Engine 20+ with Compose v2   - Tailscale installed and connected   - SSH between them for the satellite push - On the master: `git`, `curl`, `scp`, `ssh`, `openssl`  ## Quick Start  ```bash git clone https://github.com/sutejkulkarni99/Homelab_Dashboard.git ~/atheris-src cd ~/atheris-src bash deploy.sh  The script prompts for username and password, then deploys everything. Custom Configuration Change Username, Password, Port  Interactive (prompts): bash  bash deploy.sh  Via CLI flags: bash  bash deploy.sh --user admin --pass "MySecretPass123!" --port 8080  Via environment variables: bash  ATHERIS_USER=admin ATHERIS_PASS="MySecretPass123!" ATHERIS_PORT=8080 bash deploy.sh  Mixed (flags override env vars): bash  ATHERIS_USER=admin bash deploy.sh --port 8080  All Available Options Flag	Env Var	Default	Description -u, --user	ATHERIS_USER	sutej	Dashboard username -p, --pass	ATHERIS_PASS	(prompted)	Dashboard password -P, --port	ATHERIS_PORT	3030	Master port -s, --satellite-port	ATHERIS_SATELLITE_PORT	8001	Satellite agent port -o, --optiplex-ip	OPTIPLEX_IP	100.116.47.43	Master Tailscale IP -w, --wyse-ip	WYSE_IP	100.119.157.55	Satellite Tailscale IP -d, --dir	ATHERIS_INSTALL_DIR	~/atheris-hub	Install directory -h, --help	—	—	Show help Examples  Random strong password: bash  ATHERIS_PASS="$(openssl rand -base64 24)" bash deploy.sh  Custom IPs: bash  bash deploy.sh --optiplex-ip 100.64.0.10 --wyse-ip 100.64.0.20  Custom install directory: bash  bash deploy.sh --dir /opt/atheris  Rollback  Every deploy backs up the previous install to ~/atheris-hub.bak: bash  rm -rf ~/atheris-hub && mv ~/atheris-hub.bak ~/atheris-hub cd ~/atheris-hub/master && docker compose up -d  Troubleshooting  Login fails with "Invalid credentials"      Verify .env has correct AUTH_USER and AUTH_PASS      Check docker logs atheris-master for startup errors  All metrics show em-dash (—)      Container can't read /host/proc. Verify compose has - /proc:/host/proc:ro      Test: docker exec atheris-master ls /host/proc/stat  Wyse shows "OFFLINE"      Test from OptiPlex: curl http://100.119.157.55:8001/api/health      If it fails: SSH to Wyse, check docker logs atheris-satellite  Port already in use      Change master port: bash deploy.sh --port 3031  Security      Cookie sessions with HttpOnly, SameSite=Strict, 7-day expiry      Master binds to Tailscale IP only (not 0.0.0.0)      /proc and /var/run/docker.sock mounted read-only      All traffic stays on your Tailscale mesh      .env is chmod 600, not committed to git      Session secret generated fresh on every deploy  License  MIT# Atheris Hub v2.0 - Unified Dual-Node Homelab Dashboard

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
