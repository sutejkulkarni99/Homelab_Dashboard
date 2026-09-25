# Deployment Guide

Rebuild Polaris Hub on a fresh machine in ~10 minutes.

## Prerequisites

- Python 3.11+
- systemd (user services)
- git
- Tailscale
- ttyd (optional, for /ssh page)

## Quick Install

    git clone https://github.com/sutejkulkarni99/Homelab_Dashboard.git
    cd Homelab_Dashboard
    bash install.sh

The installer handles:
1. Python venv at master/.venv-staging/
2. Dependency install from requirements.txt
3. Secret generation (SESSION_SECRET, CSRF_SECRET, FERNET_KEY)
4. .env file creation (mode 600)
5. systemd user unit installation
6. Service start

## Manual Install

If install.sh fails:

    git clone https://github.com/sutejkulkarni99/Homelab_Dashboard.git
    cd Homelab_Dashboard
    python3 -m venv master/.venv-staging
    master/.venv-staging/bin/pip install --upgrade pip
    master/.venv-staging/bin/pip install -r master/requirements.txt
    cp master/master.env.example master/.env
    chmod 600 master/.env

Edit master/.env. Generate secrets:

    python3 -c "import secrets; print(secrets.token_urlsafe(32))"
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

Install systemd units:

    mkdir -p ~/.config/systemd/user
    sed "s|%INSTALL_DIR%|$(pwd)|g" deploy/systemd/polaris.service > ~/.config/systemd/user/polaris.service
    sed "s|%INSTALL_DIR%|$(pwd)|g" deploy/systemd/ttyd.service > ~/.config/systemd/user/ttyd.service
    systemctl --user daemon-reload
    systemctl --user enable --now polaris.service

## First Login

1. Open http://<tailscale-ip>:3030/login
2. Login with AUTH_USER and AUTH_PASS from .env
3. Redirected to /setup-2fa
4. Scan QR with Microsoft Authenticator
5. Enter 6-digit code
6. Login again with password + 2FA code
7. Go to /change-password
8. Set real password (migrates to Argon2id)
9. Remove AUTH_PASS line from .env
10. systemctl --user restart polaris.service

## Optional: ttyd

For the /ssh page:

    sudo dnf install -y ttyd
    systemctl --user enable --now ttyd.service

Or download binary:
    https://github.com/tsl0922/ttyd/releases

Place at /usr/local/bin/ttyd, chmod +x.

## Optional: Satellite Agent

On the Wyse machine:

    git clone https://github.com/sutejkulkarni99/Homelab_Dashboard.git
    cd Homelab_Dashboard/satellite
    docker compose up -d

Verify: curl http://<wyse-ip>:8001/api/metrics

## Optional: LiteLLM

/api/models proxies to LiteLLM at LITELLM_URL (default http://127.0.0.1:4000).

If not running, /api/models returns a fallback list. /projects still works.

Install LiteLLM separately: https://github.com/BerriAI/litellm

## Optional: Task Queue Watcher

/projects writes to POLARIS_PROJECTS_DIR/inbox/. To auto-execute:

    mkdir -p ~/.config/systemd/user
    cat > ~/.config/systemd/user/jarvis-watcher.service << 'UNIT'
    [Unit]
    Description=Jarvis Prompt Queue Watcher
    After=network.target

    [Service]
    Type=simple
    ExecStart=%h/Projects/run-prompt.sh
    Restart=always

    [Install]
    WantedBy=default.target
    UNIT
    cp deploy/run-prompt.sh ~/Projects/run-prompt.sh
    chmod +x ~/Projects/run-prompt.sh
    systemctl --user daemon-reload
    systemctl --user enable --now jarvis-watcher.service

Requires Claude Code CLI, authenticated separately.

## Firewall / Tailscale

Polaris binds to BIND_IP from .env. Restrict access via Tailscale.

Ports used: 3030 (Polaris), 7681 (ttyd) or Unix socket /tmp/ttyd.sock.

## Verify

    systemctl --user is-active polaris.service
    curl http://127.0.0.1:3030/api/health
    ls -la master/.env master/.sessions.json master/.devices.json master/.backup_codes.json

All four files should be mode 600.

## Troubleshooting

Service crash-loops:
    journalctl --user -u polaris.service -n 30 --no-pager

Login fails:
    Check AUTH_USER and AUTH_PASS in .env

/api/metrics returns 401:
    Session expired. Log out and back in.

/ssh iframe blank:
    ttyd not installed or not running.
    systemctl --user status ttyd

Session lost after restart:
    Check master/.sessions.json is writable by the service user.

## External Dependencies (not included)

- LiteLLM (model routing)
- KiCad MCP servers
- Samba shares
- nginx-proxy + DuckDNS
- Claude Code CLI
