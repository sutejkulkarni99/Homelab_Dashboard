# Atheris Hub v2.0 - Unified Dual-Node Homelab Dashboard

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Compose_v2-blue.svg)](https://docs.docker.com/compose/)
[![Tailscale](https://img.shields.io/badge/Tailscale-VPN_Mesh-3A3D40.svg)](https://tailscale.com)

**Atheris Hub v2.0** is a secure, lightweight dual-machine homelab monitoring dashboard and service gateway. Designed specifically for long-distance operation across Fedora Linux nodes connected over Tailscale VPN mesh.

---

## ⚡ Key Features

- 🖥️ **Dual-Node Metrics**: CPU, RAM, Disk, Network IO, and Uptime for both OptiPlex Master & Wyse Satellite.
- 🐳 **Live Docker Status**: Every container across nodes auto-refreshed every 5 seconds via Docker sockets.
- 🚀 **Service Launcher**: Categorized cards for Media & Storage, AI & Dev Studio, Retro Gaming, and Admin tools.
- 🔍 **Interactive Search & Filter**: Instant client-side search with category tabs and keyboard shortcuts (`/` for services, `Ctrl+K` for containers).
- 🔒 **Cookie-Session Auth**: Pure Python session authentication with constant-time password verification (no popup basic auth).
- ⚡ **Zero External Dependencies**: Standard library Python backend + vanilla JS/CSS frontend with zero build step required.
- 🛡️ **Tailscale Native**: Tailscale mesh network native bindings for encrypted, private access.

---

## 📐 Architecture & Topology

```text
+-----------------------------------------------------------------+
|                       OPTIPLEX (Master)                         |
|                       100.116.47.43:3030                        |
|                                                                 |
|  +-----------------------------------------------------------+  |
|  |                  Atheris Master (Python)                  |  |
|  |  - Cookie-session login guard                             |  |
|  |  - Reads local /proc & /var/run/docker.sock               |  |
|  |  - Polls Wyse satellite agent every 5s                     |  |
|  |  - Serves static dashboard UI                              |  |
|  +-----------------------------------------------------------+  |
+-----------------------------------------------------------------+
                                │
                                │ Tailscale Encrypted Tunnel
                                ▼
+-----------------------------------------------------------------+
|                      WYSE 5070 (Satellite)                      |
|                       100.119.157.55:8001                       |
|                                                                 |
|  +-----------------------------------------------------------+  |
|  |                 Atheris Satellite (Python)                |  |
|  |  - Serves /proc metrics JSON                               |  |
|  |  - Inspects local Docker containers                        |  |
|  |  - Footprint: <15MB RAM / 0MB Disk                         |  |
|  +-----------------------------------------------------------+  |
+-----------------------------------------------------------------+
```

---

## 📁 Repository Structure

```text
.
├── master-server.py             # Python master backend (HTTP server, sessions, metrics)
├── master-docker-compose.yml    # Docker Compose setup for OptiPlex Master host
├── master-index.html            # Single-page dashboard UI (vanilla CSS & JS)
├── master-login.html            # Standalone dark-mode login interface
├── master.env.example           # Environment variable template
├── satellite-agent.py           # Lightweight Python telemetry agent for Wyse
└── satellite-docker-compose.yml # Docker Compose setup for Wyse Satellite node
```

---

## 🛠️ Requirements

- **Linux Hosts**: Fedora 40+ or Ubuntu 22.04+ with Docker Engine 20+ and Docker Compose v2.
- **Tailscale VPN**: Both nodes connected on the same Tailscale tailnet.
- **System Access**: Read-only access to `/proc` and `/var/run/docker.sock` mounted in Compose.

---

## 🚀 Quick Start

### 1. Deploy Satellite Agent on Wyse (Thin Client)
```bash
# Copy satellite files to Wyse
scp satellite-agent.py satellite-docker-compose.yml sutej@100.119.157.55:~/atheris-satellite/

# SSH into Wyse
ssh sutej@100.119.157.55 "cd ~/atheris-satellite && mv satellite-docker-compose.yml docker-compose.yml && mv satellite-agent.py agent.py && docker compose up -d"

# Verify health endpoint from OptiPlex
curl http://100.119.157.55:8001/api/health
```

### 2. Deploy Master Server on OptiPlex (Primary Server)
```bash
# Clone or copy master files on OptiPlex
mkdir -p ~/atheris-master && cd ~/atheris-master

# Configure environment variables
cp master.env.example .env
nano .env   # Set AUTH_USER, AUTH_PASS, and SESSION_SECRET

# Rename Compose file and launch container
cp master-docker-compose.yml docker-compose.yml
cp master-server.py server.py
mkdir -p html && cp master-index.html html/index.html && cp master-login.html html/login.html

docker compose up -d
```

---

## ⚙️ Configuration Reference (`.env`)

| Variable | Default | Description |
| :--- | :--- | :--- |
| `AUTH_USER` | `sutej` | Dashboard login username |
| `AUTH_PASS` | *(required)* | Dashboard login password |
| `BIND_IP` | `100.116.47.43` | IP address to bind server on |
| `PORT` | `3030` | Web server listening port |
| `SESSION_SECRET` | *(64 random chars)* | Secret key for signing sessions |
| `SESSION_EXPIRY_DAYS` | `7` | Days before cookie session expires |
| `OPTIPLEX_IP` | `100.116.47.43` | Master node Tailscale IP |
| `WYSE_IP` | `100.119.157.55` | Satellite node Tailscale IP |
| `WYSE_AGENT_PORT` | `8001` | Satellite agent port |

---

## 🔍 Troubleshooting

* **Login fails with "Invalid credentials"**:
  Verify `.env` has the correct `AUTH_USER` and `AUTH_PASS` values set without trailing quotes or spaces.
* **Metrics show em-dash (`—`)**:
  Verify `/proc` is mounted read-only (`/proc:/host/proc:ro`) in your `docker-compose.yml`.
* **Wyse node displays "OFFLINE"**:
  Test connectivity from OptiPlex using `curl http://100.119.157.55:8001/api/health`. If unreachable, inspect logs on Wyse: `docker logs atheris-satellite`.

---

## 🛡️ Security Features

- Cookie-based session tokens with `HttpOnly`, `SameSite=Strict` attributes.
- Constant-time string comparisons (`secrets.compare_digest`) against timing attacks.
- Read-only mounts for `/proc` and `/var/run/docker.sock`.
- No external CDN dependencies or public web exposure required.

---

## Quick Redeploy (One Command)

After pushing changes from AI Studio to GitHub, run this single command on **OptiPlex** to deploy to both machines:

```bash
cd /tmp && rm -rf atheris-src && git clone https://github.com/sutejkulkarni99/Homelab_Dashboard.git atheris-src && cd atheris-src && bash deploy.sh
```

**What it does:**
1. Clones the latest code from GitHub
2. Prompts for username and password
3. Backs up the current install to `~/atheris-hub.bak`
4. Installs the new master files to OptiPlex
5. Pushes the new satellite files to Wyse
6. Restarts both containers
7. Verifies health on both nodes

**Scope:** This command is tailored for the **OptiPlex + Wyse pair** with their fixed Tailscale IPs (`100.116.47.43` and `100.119.157.55`). It is not a universal installer.

### Deploy With Custom Values

```bash
cd /tmp && rm -rf atheris-src && git clone https://github.com/sutejkulkarni99/Homelab_Dashboard.git atheris-src && cd atheris-src && bash deploy.sh --user admin --pass "YourStrongPass" --port 3030
```

### Rollback After a Bad Deploy

```bash
rm -rf ~/atheris-hub && mv ~/atheris-hub.bak ~/atheris-hub
cd ~/atheris-hub/master && docker compose up -d
ssh sutej@100.119.157.55 "rm -rf ~/atheris-hub/satellite && mv ~/atheris-hub/satellite.bak ~/atheris-hub/satellite && cd ~/atheris-hub/satellite && docker compose up -d"
```
```

---

### 📝 How to Insert It

1. Open your README on GitHub
2. Click the **pencil icon** to edit
3. Scroll down and find the line that says `## License`
4. Place your cursor **just before** that line
5. Paste the block above
6. Verify there's a blank line between your new section and `## License`
7. Commit changes

The three backtick fences will render properly as separate code blocks — no formatting issues.

## 📄 License

Distributed under the [MIT License](LICENSE).
