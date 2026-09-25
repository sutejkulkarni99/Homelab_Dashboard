# Polaris Hub

Dual-node homelab dashboard with 2FA and web SSH.

Live at `http://100.116.47.43:3030` (Tailnet-only).

Version 3.0 — FastAPI rewrite, 2026-09-25.

## Architecture

    Browser (Tailnet-only)
       |
       v  Tailscale WireGuard encryption
    polaris.service :3030  (FastAPI + uvicorn)
       |-- /              Dashboard
       |-- /projects      Task queue UI
       |-- /ssh           Web terminal
       |-- /security      Backup codes
       |-- /change-password
       |-- /setup-2fa
       |-- /api/*         JSON endpoints
       |
       |--> ttyd          :7681  (web shell)
       |--> LiteLLM       :4000  (model routing)
       |--> satellite     :8001  (Wyse metrics agent)

## Layout

    master/       FastAPI backend + HTML
    satellite/    Wyse metrics agent (Docker)
    deploy/       systemd units + watcher script
    docs/         CONTEXT, MIGRATION, SECURITY, CLAUDE
    legacy/       v2.0 (old Python stdlib version)

## Components

| Component | Port | Deployment | Purpose |
|---|---|---|---|
| polaris | 3030 | systemd user | FastAPI dashboard |
| ttyd | 7681 | systemd user | Web terminal |
| satellite-agent | 8001 | Docker (Wyse) | Metrics agent |

## Features

- Live dual-node metrics (CPU, RAM, disk, net, uptime, containers)
- Service launcher tiles with online status
- /projects — submit prompts to headless Claude Code, view results
- /ssh — full bash terminal in browser
- Argon2id password + TOTP 2FA
- 24h device trust (skip 2FA on known devices)
- 10 one-time backup codes
- Server-side sessions (revocable, file-backed, 6h expiry)
- CSRF protection + login rate limiting

## Quick Start

    git clone https://github.com/sutejkulkarni99/Homelab_Dashboard.git
    cd Homelab_Dashboard/master
    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp master.env.example .env   # edit with your values
    uvicorn app_new:app --host 0.0.0.0 --port 3030

Prerequisites: Fedora Linux (or any systemd distro), Python 3.11+, Tailscale, Docker.

First login: open /login, then /setup-2fa to enroll TOTP, then /change-password to migrate from plaintext.

## Configuration

Create master/.env (mode 600):

| Variable | Purpose | Default |
|---|---|---|
| AUTH_USER | Login username | sutej |
| PASSWORD_HASH | Argon2id hash | set via /change-password |
| TOTP_SECRET | Fernet-encrypted TOTP | set via /setup-2fa |
| SESSION_SECRET | Session signing key | random |
| CSRF_SECRET | CSRF token key | random |
| FERNET_KEY | TOTP encryption key | random |
| SESSION_EXPIRY_HOURS | Session duration | 6 |
| DEVICE_TRUST_HOURS | Trusted device window | 24 |
| LOGIN_RATE_LIMIT | Attempts per window | 20/5minutes |
| OPTIPLEX_IP | Master Tailscale IP | 100.116.47.43 |
| WYSE_IP | Satellite Tailscale IP | 100.119.157.55 |
| WYSE_AGENT_PORT | Satellite port | 8001 |
| POLARIS_PROJECTS_DIR | Task queue root | ~/Projects |

Generate secrets:

    python3 -c "import secrets; print(secrets.token_urlsafe(32))"
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

## Endpoints

Pages: / /login /setup-2fa /change-password /security /projects /ssh

APIs: /api/health /api/metrics /api/services /api/status /api/models /api/prompt /api/upload /api/history /api/result/<id> /api/login /api/logout /api/change-password /api/setup-2fa/* /api/backup-codes/* /api/forget-device

## Security

Full detail in docs/SECURITY.md. Key points:

- Tailnet-only, never exposed to public internet
- Argon2id password hashing
- TOTP secret Fernet-encrypted at rest
- Sessions + device tokens stored as SHA-256 hashes
- Password change revokes all sessions + devices
- 2FA reset revokes all devices

## Recovery

| Scenario | Path |
|---|---|
| Lost phone, have backup codes | Login with code, then /security, reset 2FA |
| Lost phone, no codes | SSH in, delete TOTP_SECRET line in .env, restart |
| Forgot password | SSH in, generate new hash, replace PASSWORD_HASH, restart |
| Compromised session | Login elsewhere, /change-password (revokes all) |

## Migration History

v2.0 to v3.0 rewrite on 2026-09-25. See docs/MIGRATION.md.

Old v2.0 code preserved in legacy/.

## License

MIT License - see [LICENSE](LICENSE) file.
