# Migration Journal — v2.0 to v3.0

Date: 2026-09-25

FastAPI rewrite with 2FA, session persistence, device trust, backup codes, web SSH, and task queue UI. Zero data loss, two rollback paths preserved.

## What Changed

| Layer | v2.0 | v3.0 |
|---|---|---|
| Backend | Python stdlib http.server | FastAPI + uvicorn |
| Deployment | Docker container | systemd user service |
| Password | Plaintext in .env | Argon2id hash |
| 2FA | None | TOTP + device trust + backup codes |
| Sessions | In-memory, wiped on restart | File-backed, revocable, 6h expiry |
| CSRF | None | Double-submit tokens |
| Rate limiting | None | 20 login attempts / 5 min |
| Web SSH | None | /ssh iframe to ttyd |
| Task queue | Manual file drops | /projects UI with history |

Old code preserved in legacy/.

## Architecture Notes

- New service name: polaris.service (replaces polaris-master Docker container and intermediate polaris-staging.service)
- ttyd runs as ttyd.service on port 7681 with basic auth
- Watcher (deploy/run-prompt.sh) rewritten: polling instead of inotifywait (CIFS-friendly), captures prompt text into history.jsonl, writes .status.json on state transitions

## Key Errors and Fixes

### Routes not registering

Routes defined below `if __name__ == '__main__': uvicorn.run(...)` never ran because uvicorn.run() blocks forever. Moved all routes above the __main__ guard.

### Deadlock in backup code verification

verify_backup_code() held BACKUP_LOCK and called _save_backup_codes(), which tried to acquire the same lock. threading.Lock is not reentrant. Switched BACKUP_LOCK, DEVICES_LOCK, and SESSIONS_LOCK to threading.RLock.

### NameError: LOGIN_RATE_LIMIT

@limiter.limit(LOGIN_RATE_LIMIT) decorator evaluated at import time before LOGIN_RATE_LIMIT was defined. Moved the variable definition above the decorator usage.

### Logout button did nothing on dashboard

Frontend called POST /api/logout but endpoint only accepted GET (405 swallowed by try/catch). Then redirected to / (auth-protected) which bounced back. Made endpoint accept both GET and POST, changed JS redirect to /login.

### Docker build network failures

Build containers could not reach Debian mirrors or PyPI behind CGNAT + Tailscale. Skipped Docker for staging, used native Python venv.

### Trust-device checkbox missing from login

Regex patch targeted a block with different whitespace than expected. Rewrote login.html from scratch.

### /api/metrics returned 401 after login

Sessions were stored in memory, wiped on every service restart during development. Added file-backed session persistence (.sessions.json) loaded on startup and saved on every change.

### Metrics import error: OPTIPLEX_IP

Original server.py defined config constants above SERVICES = [. Extraction script only grabbed from SERVICES downward. Added the missing constants at top of metrics_helpers.py.

### Service rename during cutover

Cutover renamed polaris-staging.service to polaris.service. Use polaris.service going forward.

## Rollback Procedures

Full reset to pre-FastAPI state:

    bash /mnt/HomeLab_Share/_restore-points/20260925-123116-pre-fastapi/RESTORE.sh

Rollback cutover only (FastAPI back to old Docker Polaris):

    bash /home/sutej/server-setup/_backups/20260925-153923-pre-cutover/rollback-to-old-polaris.sh

## Lessons Learned

1. Thread locks are subtle. threading.Lock deadlocks when a locked function calls another function that re-acquires the lock. Use RLock for any lock that may be held across such calls.

2. Python decorators evaluate at import time. Variables referenced in a decorator argument must be defined before the decorator.

3. Route order matters. All routes before app.mount() and before the __main__ block.

4. Docker builds behind CGNAT are unreliable. Native venv is faster to iterate on.

5. Session persistence matters. In-memory sessions cause confusing re-login experiences during development.

6. Test each security layer in isolation. Backup codes, device trust, and TOTP all behave differently.
