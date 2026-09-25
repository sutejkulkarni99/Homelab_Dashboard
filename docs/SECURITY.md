# Security Architecture

## Authentication

Two independent factors required for fresh login on untrusted devices:

1. Password, hashed with Argon2id (time_cost=3, memory_cost=64MB, parallelism=4)
2. TOTP 2FA, 6-digit codes from any standard authenticator app

## Session Management

| Aspect | Design |
|---|---|
| Token | 32-byte random, URL-safe |
| Server storage | SHA-256 hash in .sessions.json (mode 600) |
| Client storage | HttpOnly cookie polaris_session |
| Expiry | SESSION_EXPIRY_HOURS (default 6h) |
| Invalidation | Password change revokes all sessions |
| Persistence | Survives service restart |

Session token never stored in plaintext on server. A .sessions.json leak does not expose working cookies.

## Device Trust

After successful 2FA login, users may trust the device for DEVICE_TRUST_HOURS (default 24h).

| Aspect | Design |
|---|---|
| Token | 32-byte random |
| Server storage | SHA-256 hash in .devices.json (mode 600) |
| Client storage | HttpOnly cookie device_token |
| Behaviour | Trusted device skips 2FA (password only) |
| Revocation | Password change, 2FA reset, or /api/forget-device |
| Persistence | Survives logout (that is the point) |

Tradeoff: on a trusted device, an attacker with the password could log in without 2FA. Mitigated by 24h max window and revocable on password change.

## Backup Codes

10 one-time recovery codes for when the authenticator is unavailable.

| Aspect | Design |
|---|---|
| Format | XXXX-XXXX (no confusing chars: 0/O, 1/I excluded) |
| Storage | Argon2id hash in .backup_codes.json (mode 600) |
| Use | Type in 2FA field at login instead of TOTP |
| Consumption | Marked used after use, cannot be reused |
| Regeneration | Invalidates all previous, requires password |
| Exhaustion recovery | SSH in, delete TOTP_SECRET line in .env, restart |

## CSRF Protection

Double-submit token pattern:

- On login, server sets cookie csrf_token (non-HttpOnly, JS-readable)
- Frontend sends value in header X-CSRF-Token on every POST/PUT/DELETE
- Server compares to session stored token
- Token HMAC-signed with CSRF_SECRET

## Rate Limiting

| Endpoint | Default | Scope |
|---|---|---|
| /api/login | 20/5minutes | Per IP |
| /api/setup-2fa/init | 20/5minutes | Per IP |

Configurable via LOGIN_RATE_LIMIT. Errors return HTTP 429.

## Encryption at Rest

| Item | Method |
|---|---|
| Password | Argon2id (one-way) |
| TOTP secret | Fernet (AES-128-CBC + HMAC-SHA256), key in FERNET_KEY |
| Session tokens | SHA-256 hash of 32-byte random value |
| Device tokens | SHA-256 hash of 32-byte random value |
| Backup codes | Argon2id hash of 8-char code |
| CSRF tokens | HMAC-SHA256 signed |

## File Permissions

All sensitive files mode 600 (owner read/write only):

- master/.env
- master/.sessions.json
- master/.devices.json
- master/.backup_codes.json

## Network Exposure

Polaris is Tailnet-only:

- Binds to Tailscale IP 100.116.47.43 on port 3030
- Reachable only from devices on the same Tailnet
- Never exposed to public internet
- Transport encryption via Tailscale WireGuard (AES-256-GCM)

Why not HTTPS on top of Tailscale? Traffic never leaves the WireGuard tunnel. HTTPS would encrypt an already-encrypted stream. Also, /ssh embeds an HTTP iframe, and browsers block HTTP iframes inside HTTPS pages. Adding HTTPS would break the SSH embed.

Public services (Nextcloud, Jellyfin, Cockpit) do run HTTPS via nginx-proxy + Let's Encrypt because they are internet-exposed.

## Threat Model

| Threat | Mitigation |
|---|---|
| Password brute force | Argon2id + rate limiting |
| Credential stuffing | TOTP 2FA required |
| Session hijack (network) | Tailscale WireGuard |
| Session hijack (XSS) | HttpOnly cookies, minimal inline JS |
| CSRF | Double-submit tokens |
| Stolen laptop (unlocked) | 6h session expiry limits window |
| Lost phone | Backup codes for recovery |
| Compromised server | TOTP encrypted, sessions/devices revocable |

Out of scope: physical attacks, Python package supply chain, side channels.

## Recovery Scenarios

Lost phone, backup codes available:

1. Login with username + password + one backup code
2. /security, reset 2FA, scan new QR
3. Regenerate backup codes

Lost phone, no backup codes:

1. SSH into OptiPlex
2. sed -i '/^TOTP_SECRET=/d' ~/polaris-hub/master/.env
3. systemctl --user restart polaris.service
4. Login with password, /setup-2fa

Forgot password:

1. SSH in
2. Generate new hash with: ~/polaris-hub/master/.venv-staging/bin/python3 -c "from argon2 import PasswordHasher; print('PASSWORD_HASH=' + PasswordHasher().hash('NewPass123'))"
3. Replace PASSWORD_HASH= line in .env
4. systemctl --user restart polaris.service

Compromised session:

1. Login elsewhere (or SSH in)
2. /change-password, enter current + new
3. All sessions + device tokens revoked automatically

All secrets compromised:

1. Rotate SESSION_SECRET, CSRF_SECRET, FERNET_KEY in .env
2. Change password at /change-password
3. Reset 2FA at /setup-2fa
4. Regenerate backup codes at /security
5. systemctl --user restart polaris.service

## Dependencies

Pinned in master/requirements.txt. No known CVEs at time of writing.
