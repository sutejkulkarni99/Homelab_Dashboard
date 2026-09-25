#!/usr/bin/env python3
"""Polaris Hub v2 - FastAPI with 2FA + Web SSH. Secure by default."""
import os, pathlib, json, time, secrets, hmac, hashlib, base64, threading, re
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Response, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

import pyotp, qrcode, io
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from cryptography.fernet import Fernet, InvalidToken
import httpx

BASE = pathlib.Path(__file__).parent
for ef in [BASE / '.env', BASE / 'polaris.env', BASE / 'master.env']:
    if ef.exists():
        for line in ef.read_text().splitlines():
            line = line.strip()
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

HTML = BASE / 'html'
PROJ = pathlib.Path(os.environ.get('POLARIS_PROJECTS_DIR', str(pathlib.Path.home() / 'Projects')))
SESSION_SECRET = os.environ.get('SESSION_SECRET', secrets.token_urlsafe(32))
CSRF_SECRET = os.environ.get('CSRF_SECRET', secrets.token_urlsafe(32)).encode()
FERNET_KEY = os.environ.get('FERNET_KEY', Fernet.generate_key().decode()).encode()
SESSION_EXPIRY = int(os.environ.get("SESSION_EXPIRY_HOURS", "6")) * 3600
LOGIN_RATE_LIMIT = os.environ.get("LOGIN_RATE_LIMIT", "20/5minutes")
DEVICE_TRUST_HOURS = int(os.environ.get("DEVICE_TRUST_HOURS", "24"))
DEVICES_FILE = BASE / ".devices.json"
BACKUP_CODES_FILE = BASE / ".backup_codes.json"

fernet = Fernet(FERNET_KEY)
ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

@app.exception_handler(RateLimitExceeded)
def rate_limit_handler(request, exc):
    return JSONResponse({'ok': False, 'error': 'too many attempts'}, status_code=429)

SESSIONS = {}
SESSIONS_LOCK = threading.RLock()
TOTP_REPLAY = {}
SESSIONS_FILE = BASE / '.sessions.json'


def _load_sessions():
    if not SESSIONS_FILE.exists():
        return
    try:
        data = json.loads(SESSIONS_FILE.read_text())
        now = time.time()
        with SESSIONS_LOCK:
            for tok_hash, sess in data.items():
                if sess.get('expires', 0) > now:
                    SESSIONS[tok_hash] = sess
        print(f"Loaded {len(SESSIONS)} active session(s) from disk")
    except Exception as e:
        print(f"Session load failed: {e}")


# ═══ Device trust store ═══
DEVICES = {}
DEVICES_LOCK = threading.RLock()


def _load_devices():
    if not DEVICES_FILE.exists():
        return
    try:
        data = json.loads(DEVICES_FILE.read_text())
        now = time.time()
        with DEVICES_LOCK:
            for h, d in data.items():
                if d.get('expires', 0) > now:
                    DEVICES[h] = d
        print(f"Loaded {len(DEVICES)} trusted device(s) from disk")
    except Exception as e:
        print(f"Devices load failed: {e}")


def _save_devices():
    try:
        with DEVICES_LOCK:
            data = {h: d for h, d in DEVICES.items() if d.get('expires', 0) > time.time()}
        DEVICES_FILE.write_text(json.dumps(data))
        os.chmod(DEVICES_FILE, 0o600)
    except Exception as e:
        print(f"Devices save failed: {e}")


def create_device_token(username):
    raw = secrets.token_urlsafe(32)
    h = _hash_token(raw)
    with DEVICES_LOCK:
        DEVICES[h] = {'username': username, 'expires': time.time() + DEVICE_TRUST_HOURS * 3600}
    _save_devices()
    return raw


def verify_device_token(request, username):
    raw = request.cookies.get('device_token', '')
    if not raw:
        return False
    h = _hash_token(raw)
    with DEVICES_LOCK:
        d = DEVICES.get(h)
        if not d or d.get('username') != username or d.get('expires', 0) < time.time():
            if h in DEVICES:
                del DEVICES[h]
                _save_devices()
            return False
    return True


def revoke_device_token(request):
    raw = request.cookies.get('device_token', '')
    if not raw:
        return
    h = _hash_token(raw)
    with DEVICES_LOCK:
        DEVICES.pop(h, None)
    _save_devices()


# ═══ Backup codes ═══
BACKUP_CODES = {}          # username -> {"codes": [{"hash": ..., "used": bool}, ...]}
BACKUP_LOCK = threading.RLock()


def _load_backup_codes():
    if not BACKUP_CODES_FILE.exists():
        return
    try:
        data = json.loads(BACKUP_CODES_FILE.read_text())
        with BACKUP_LOCK:
            BACKUP_CODES.update(data)
        print(f"Loaded backup codes for {len(data)} user(s)")
    except Exception as e:
        print(f"Backup codes load failed: {e}")


def _save_backup_codes():
    try:
        with BACKUP_LOCK:
            BACKUP_CODES_FILE.write_text(json.dumps(BACKUP_CODES))
        os.chmod(BACKUP_CODES_FILE, 0o600)
    except Exception as e:
        print(f"Backup codes save failed: {e}")


def _gen_code():
    """Generate one human-friendly code like XXXX-XXXX."""
    import string
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # no confusing chars
    raw = ''.join(secrets.choice(alphabet) for _ in range(8))
    return f'{raw[:4]}-{raw[4:]}'


def generate_backup_codes(username, count=10):
    """Generate fresh codes. Replaces any existing. Returns plaintext list."""
    plaintext = [_gen_code() for _ in range(count)]
    hashed = [{'hash': ph.hash(c), 'used': False} for c in plaintext]
    with BACKUP_LOCK:
        BACKUP_CODES[username] = {'codes': hashed, 'generated': time.time()}
    _save_backup_codes()
    print(f"[auth] Generated {count} backup codes for {username}")
    return plaintext


def remaining_backup_codes(username):
    with BACKUP_LOCK:
        entry = BACKUP_CODES.get(username)
        if not entry:
            return 0
        return sum(1 for x in entry['codes'] if not x['used'])


def verify_backup_code(username, code):
    """Try to consume a backup code. Returns True if valid."""
    code = code.strip().upper().replace(' ', '')
    # Normalize: insert hyphen if missing
    if '-' not in code and len(code) == 8:
        code = code[:4] + '-' + code[4:]
    with BACKUP_LOCK:
        entry = BACKUP_CODES.get(username)
        if not entry:
            return False
        for slot in entry['codes']:
            if slot['used']:
                continue
            try:
                ph.verify(slot['hash'], code)
                slot['used'] = True
                _save_backup_codes()
                print(f"[auth] Backup code used for {username}")
                return True
            except Exception:
                continue
    return False


_load_backup_codes()


_load_devices()

def _save_sessions():
    """Persist sessions to disk. Caller holds the lock or is single-threaded."""
    try:
        with SESSIONS_LOCK:
            data = {h: s for h, s in SESSIONS.items()
                    if not h.startswith('setup:') and s.get('expires', 0) > time.time()}
        SESSIONS_FILE.write_text(json.dumps(data))
        os.chmod(SESSIONS_FILE, 0o600)
    except Exception as e:
        print(f"Session save failed: {e}")


_load_sessions()

def _hash_token(tok):
    return hashlib.sha256(tok.encode()).hexdigest()

def create_session(username):
    raw = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    with SESSIONS_LOCK:
        SESSIONS[_hash_token(raw)] = {'username': username, 'expires': time.time() + SESSION_EXPIRY, 'csrf': csrf}
    _save_sessions()
    return raw, csrf

def get_session(request):
    tok = request.cookies.get('polaris_session')
    if not tok: return None
    h = _hash_token(tok)
    with SESSIONS_LOCK:
        sess = SESSIONS.get(h)
        if not sess: return None
        if sess['expires'] < time.time():
            del SESSIONS[h]; return None
        return sess

def require_session(request):
    s = get_session(request)
    if not s: raise HTTPException(status_code=401, detail='Unauthorized')
    return s

def require_csrf(request, sess):
    hdr = request.headers.get('X-CSRF-Token', '')
    if not hdr or not hmac.compare_digest(hdr, sess['csrf']):
        raise HTTPException(status_code=403, detail='CSRF invalid')

def get_password_hash(): return os.environ.get('PASSWORD_HASH', '')

def set_password_hash(h):
    p = BASE / '.env'
    c = p.read_text()
    if 'PASSWORD_HASH=' in c:
        c = re.sub(r'^PASSWORD_HASH=.*$', f'PASSWORD_HASH={h}', c, flags=re.MULTILINE)
    else:
        c = c.rstrip() + f'\nPASSWORD_HASH={h}\n'
    p.write_text(c)
    os.environ['PASSWORD_HASH'] = h

def get_totp_secret():
    enc = os.environ.get('TOTP_SECRET', '')
    if not enc: return None
    try: return fernet.decrypt(enc.encode()).decode()
    except InvalidToken: return None

def set_totp_secret(s):
    enc = fernet.encrypt(s.encode()).decode()
    p = BASE / '.env'
    c = p.read_text()
    if 'TOTP_SECRET=' in c:
        c = re.sub(r'^TOTP_SECRET=.*$', f'TOTP_SECRET={enc}', c, flags=re.MULTILINE)
    else:
        c = c.rstrip() + f'\nTOTP_SECRET={enc}\n'
    p.write_text(c)
    os.environ['TOTP_SECRET'] = enc

def totp_is_enabled(): return bool(get_totp_secret())

def verify_totp(username, code):
    secret = get_totp_secret()
    if not secret: return False
    totp = pyotp.TOTP(secret)
    now_step = int(time.time() // 30)
    if TOTP_REPLAY.get(username, 0) >= now_step: return False
    if not totp.verify(code, valid_window=1): return False
    TOTP_REPLAY[username] = now_step
    return True

def verify_password(password):
    h = get_password_hash()
    if h:
        try: ph.verify(h, password); return True
        except (VerifyMismatchError, InvalidHashError): return False
    legacy = os.environ.get('AUTH_PASS', '')
    return bool(legacy) and hmac.compare_digest(password, legacy)

def sign_csrf(raw):
    sig = hmac.new(CSRF_SECRET, raw.encode(), hashlib.sha256).hexdigest()[:16]
    return f'{raw}.{sig}'

@app.get('/login', response_class=HTMLResponse)
def login_page():
    return HTMLResponse((HTML / 'login.html').read_text())

@app.post('/api/login')
@limiter.limit(LOGIN_RATE_LIMIT)
async def api_login(request: Request):
    try: data = await request.json()
    except Exception: return JSONResponse({'ok': False, 'error': 'bad json'}, status_code=400)
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    if not hmac.compare_digest(username, os.environ.get('AUTH_USER', '')) or not verify_password(password):
        return JSONResponse({'ok': False, 'error': 'invalid credentials'}, status_code=401)
    if not totp_is_enabled():
        return JSONResponse({'ok': False, 'needs_totp_setup': True, 'setup_url': '/setup-2fa'}, status_code=200)

    # Trusted-device path: skip TOTP if device cookie is valid
    if verify_device_token(request, username):
        raw, csrf = create_session(username)
        r = JSONResponse({'ok': True, 'status': 'ok', 'redirect': '/', 'csrf': csrf, 'trusted_device': True})
        r.set_cookie('polaris_session', raw, max_age=SESSION_EXPIRY, httponly=True, secure=False, samesite='strict', path='/')
        r.set_cookie('csrf_token', csrf, max_age=SESSION_EXPIRY, httponly=False, secure=False, samesite='strict', path='/')
        return r

    code = (data.get('totp') or '').strip()
    if not code:
        return JSONResponse({'ok': False, 'needs_totp': True}, status_code=200)
    # Try TOTP first, then backup code
    totp_ok = verify_totp(username, code)
    backup_ok = False
    if not totp_ok:
        # Backup codes look like XXXX-XXXX or XXXXXXXX
        normalized = code.upper().replace(' ', '')
        if re.match(r'^[A-Z0-9]{4}-?[A-Z0-9]{4}$', normalized):
            backup_ok = verify_backup_code(username, normalized)
    if not totp_ok and not backup_ok:
        return JSONResponse({'ok': False, 'error': 'invalid 2FA code or backup code'}, status_code=401)

    raw, csrf = create_session(username)
    r = JSONResponse({'ok': True, 'status': 'ok', 'redirect': '/', 'csrf': csrf})
    r.set_cookie('polaris_session', raw, max_age=SESSION_EXPIRY, httponly=True, secure=False, samesite='strict', path='/')
    r.set_cookie('csrf_token', csrf, max_age=SESSION_EXPIRY, httponly=False, secure=False, samesite='strict', path='/')

    # Issue device token if user asked to trust this device
    if data.get('trust_device'):
        dev_raw = create_device_token(username)
        r.set_cookie('device_token', dev_raw, max_age=DEVICE_TRUST_HOURS * 3600, httponly=True, secure=False, samesite='strict', path='/')
        print(f"[auth] Device trust granted for {username} ({DEVICE_TRUST_HOURS}h)")

    return r


@app.get('/setup-2fa', response_class=HTMLResponse)
def setup_2fa_page():
    p = HTML / 'setup-2fa.html'
    if p.exists(): return HTMLResponse(p.read_text())
    return HTMLResponse('<h1>setup-2fa.html missing</h1>', status_code=500)

@app.post('/api/setup-2fa/init')
@limiter.limit(LOGIN_RATE_LIMIT)
async def api_setup_2fa_init(request: Request):
    try: data = await request.json()
    except Exception: return JSONResponse({'ok': False, 'error': 'bad json'}, status_code=400)
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    if not hmac.compare_digest(username, os.environ.get('AUTH_USER', '')) or not verify_password(password):
        return JSONResponse({'ok': False, 'error': 'invalid credentials'}, status_code=401)
    if totp_is_enabled():
        return JSONResponse({'ok': False, 'error': 'already configured'}, status_code=400)
    secret = pyotp.random_base32()
    uri = pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name='Polaris Hub')
    img = qrcode.make(uri)
    buf = io.BytesIO(); img.save(buf, format='PNG')
    png_b64 = base64.b64encode(buf.getvalue()).decode()
    token = secrets.token_urlsafe(24)
    SESSIONS[f'setup:{token}'] = {'secret': secret, 'expires': time.time() + 600}
    return {'ok': True, 'setup_token': token, 'qr_png_b64': png_b64, 'secret_manual': secret}

@app.post('/api/setup-2fa/confirm')
async def api_setup_2fa_confirm(request: Request):
    try: data = await request.json()
    except Exception: return JSONResponse({'ok': False, 'error': 'bad json'}, status_code=400)
    token = data.get('setup_token', '')
    code = (data.get('code') or '').strip()
    entry = SESSIONS.get(f'setup:{token}')
    if not entry or entry['expires'] < time.time():
        return JSONResponse({'ok': False, 'error': 'setup expired'}, status_code=400)
    if not pyotp.TOTP(entry['secret']).verify(code, valid_window=1):
        return JSONResponse({'ok': False, 'error': 'invalid code'}, status_code=401)
    set_totp_secret(entry['secret'])
    del SESSIONS[f'setup:{token}']
    return {'ok': True, 'message': '2FA enabled'}

@app.post('/api/forget-device')
async def api_forget_device(request: Request):
    sess = require_session(request)
    require_csrf(request, sess)
    revoke_device_token(request)
    r = JSONResponse({'ok': True, 'message': 'Device trust revoked'})
    r.delete_cookie('device_token')
    return r


@app.get('/logout')
def logout(request: Request):
    tok = request.cookies.get('polaris_session')
    if tok:
        with SESSIONS_LOCK: SESSIONS.pop(_hash_token(tok), None)
        _save_sessions()
    r = RedirectResponse('/login', status_code=303)
    r.delete_cookie('polaris_session'); r.delete_cookie('csrf_token')
    return r

@app.api_route('/api/logout', methods=['GET', 'POST'])
def api_logout(request: Request):
    tok = request.cookies.get('polaris_session')
    if tok:
        with SESSIONS_LOCK: SESSIONS.pop(_hash_token(tok), None)
        _save_sessions()
    r = JSONResponse({'ok': True, 'status': 'ok'})
    r.delete_cookie('polaris_session'); r.delete_cookie('csrf_token')
    return r

@app.get('/', response_class=HTMLResponse)
def home(request: Request):
    if not get_session(request): return RedirectResponse('/login')
    return HTMLResponse((HTML / 'index.html').read_text())

@app.get('/projects', response_class=HTMLResponse)
def projects(request: Request):
    if not get_session(request): return RedirectResponse('/login')
    return HTMLResponse((HTML / 'projects.html').read_text())

@app.get('/ssh', response_class=HTMLResponse)
def ssh_page(request: Request):
    if not get_session(request): return RedirectResponse('/login')
    return HTMLResponse((HTML / 'ssh.html').read_text())

@app.get('/api/health')
def health():
    return {'ok': True, 'mode': 'fastapi', '2fa_enabled': totp_is_enabled()}

@app.get('/api/services')
def api_services():
    from metrics_helpers import SERVICES
    return SERVICES

@app.get('/api/status')
def api_status():
    s = PROJ / '.status.json'
    if s.exists(): return JSONResponse(json.loads(s.read_text()))
    return JSONResponse({'state': 'unknown'})

@app.get('/api/metrics')
def api_metrics(request: Request):
    if not get_session(request): return JSONResponse({'error': 'unauthorized'}, status_code=401)
    from metrics_helpers import (SERVICES, SERVICE_HEALTH, HEALTH_LOCK,
                                  cpu, ram, disk, net_io, uptime,
                                  docker_containers, wyse_metrics, OPTIPLEX_IP)
    with HEALTH_LOCK: h = dict(SERVICE_HEALTH)
    services = [{**s, 'online': h.get(s['id'], False)} for s in SERVICES]
    opt = {'status': 'online', 'node_id': 'optiplex', 'node_name': 'OptiPlex 7070',
           'role': 'Master Host', 'ip': OPTIPLEX_IP,
           'specs': 'Intel i7 - 16GB RAM - 1.8TB SSD',
           'cpu': {'load': cpu(), 'cores': os.cpu_count() or 4},
           'ram': ram(), 'disk': disk(), 'net': net_io(),
           'uptime': uptime(), 'containers': docker_containers()}
    return {'timestamp': int(time.time()), 'nodes': [opt, wyse_metrics()], 'services': services}

@app.get('/api/models')
def api_models(request: Request):
    if not get_session(request): return JSONResponse({'error': 'unauthorized'}, status_code=401)
    allowed = {'fast','medium','coding','coding-cohere','strong','strong-mistral','mistral-nim','ultra','critical'}
    try:
        r = httpx.get('http://127.0.0.1:4000/v1/models',
                      headers={'Authorization': 'Bearer sk-litellm-local'}, timeout=5)
        ids = [m['id'] for m in r.json().get('data', [])]
        if ids: return {'models': sorted(ids)}
    except Exception: pass
    return {'models': sorted(allowed), 'fallback': True}

def _sanitize(name):
    return (re.sub(r'[^a-zA-Z0-9_-]', '-', str(name))[:64].strip('-') or 'task')

@app.post('/api/prompt')
async def api_prompt(request: Request):
    sess = require_session(request); require_csrf(request, sess)
    data = await request.json()
    text = (data.get('prompt') or '').strip()
    model = (data.get('model') or 'fast').strip()
    allowed = {'fast','medium','coding','coding-cohere','strong','strong-mistral','mistral-nim','ultra','critical'}
    if not text or len(text) > 100000:
        return JSONResponse({'ok': False, 'error': 'bad prompt'}, status_code=400)
    if model not in allowed:
        return JSONResponse({'ok': False, 'error': 'unknown model'}, status_code=400)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    slug = _sanitize(text.split('\n')[0][:40])
    task_id = f'{stamp}-{slug}'
    (PROJ / 'inbox').mkdir(parents=True, exist_ok=True)
    (PROJ / 'inbox' / f'{task_id}.md').write_text(f'<!-- model: {model} -->\n{text}\n')
    return {'ok': True, 'task_id': task_id}

@app.post('/api/upload')
async def api_upload(request: Request, file: UploadFile = File(...)):
    sess = require_session(request); require_csrf(request, sess)
    if not file.filename or not file.filename.endswith('.md'):
        return JSONResponse({'ok': False, 'error': 'only .md'}, status_code=400)
    content = (await file.read()).decode('utf-8', errors='replace')
    if len(content) > 1000000:
        return JSONResponse({'ok': False, 'error': 'too large'}, status_code=413)
    if not content.lstrip().startswith('<!-- model:'):
        content = '<!-- model: fast -->\n' + content
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    task_id = f'{stamp}-{_sanitize(file.filename[:-3])}'
    (PROJ / 'inbox').mkdir(parents=True, exist_ok=True)
    (PROJ / 'inbox' / f'{task_id}.md').write_text(content)
    return {'ok': True, 'task_id': task_id}

@app.get('/api/history')
def api_history(request: Request):
    if not get_session(request): return JSONResponse({'error': 'unauthorized'}, status_code=401)
    hist = PROJ / 'history.jsonl'; outbox = PROJ / 'outbox'
    items = []
    if hist.exists():
        for line in hist.read_text().splitlines():
            try:
                d = json.loads(line)
                rf = d.get('result_file')
                preview = ''
                if rf and (outbox / rf).exists():
                    preview = (outbox / rf).read_text(errors='replace')[:4000]
                items.append({**d, 'preview': preview})
            except Exception: pass
    items.reverse()
    return {'items': items[:50]}

@app.get('/api/result/{task_id}')
def api_result(task_id: str, request: Request):
    if not get_session(request): return JSONResponse({'error': 'unauthorized'}, status_code=401)
    safe = _sanitize(task_id)
    p = PROJ / 'outbox' / f'{safe}-result.txt'
    if p.exists(): return {'ok': True, 'content': p.read_text(errors='replace')}
    return JSONResponse({'ok': False, 'error': 'not found'}, status_code=404)


@app.get('/change-password', response_class=HTMLResponse)
def change_password_page(request: Request):
    if not get_session(request):
        return RedirectResponse('/login')
    p = HTML / 'change-password.html'
    if p.exists():
        return HTMLResponse(p.read_text())
    return HTMLResponse('<h1>change-password.html missing</h1>', status_code=500)


@app.post('/api/change-password')
async def api_change_password(request: Request):
    sess = require_session(request)
    require_csrf(request, sess)
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({'ok': False, 'error': 'bad json'}, status_code=400)
    old = data.get('old_password') or ''
    new = data.get('new_password') or ''
    confirm = data.get('confirm_password') or ''
    if not verify_password(old):
        return JSONResponse({'ok': False, 'error': 'current password is wrong'}, status_code=401)
    if len(new) < 12:
        return JSONResponse({'ok': False, 'error': 'new password must be >= 12 characters'}, status_code=400)
    if new != confirm:
        return JSONResponse({'ok': False, 'error': 'passwords do not match'}, status_code=400)
    if new == old:
        return JSONResponse({'ok': False, 'error': 'new password must differ from old'}, status_code=400)
    # Hash and save
    set_password_hash(ph.hash(new))
    # Remove legacy AUTH_PASS from .env
    p = BASE / '.env'
    ec = p.read_text()
    ec = re.sub(r'^AUTH_PASS=.*\n?', '', ec, flags=re.MULTILINE)
    p.write_text(ec)
    os.chmod(p, 0o600)
    os.environ.pop('AUTH_PASS', None)
    # Invalidate all sessions + device tokens for this user
    with SESSIONS_LOCK:
        for h in list(SESSIONS.keys()):
            if isinstance(SESSIONS[h], dict) and SESSIONS[h].get('username') == sess['username']:
                del SESSIONS[h]
    _save_sessions()
    with DEVICES_LOCK:
        for h in list(DEVICES.keys()):
            if isinstance(DEVICES[h], dict) and DEVICES[h].get('username') == sess['username']:
                del DEVICES[h]
    _save_devices()
    print(f"[auth] Password changed for {sess['username']}, all sessions and devices revoked")
    return {'ok': True, 'message': 'Password changed. Please sign in again.', 'redirect': '/login'}



@app.get('/security', response_class=HTMLResponse)
def security_page(request: Request):
    if not get_session(request):
        return RedirectResponse('/login')
    p = HTML / 'security.html'
    if p.exists():
        return HTMLResponse(p.read_text())
    return HTMLResponse('<h1>security.html missing</h1>', status_code=500)


@app.get('/api/backup-codes/status')
def api_backup_codes_status(request: Request):
    sess = require_session(request)
    return {'ok': True, 'remaining': remaining_backup_codes(sess['username']), 'total': 10}


@app.post('/api/backup-codes/generate')
async def api_backup_codes_generate(request: Request):
    sess = require_session(request)
    require_csrf(request, sess)
    try:
        data = await request.json()
    except Exception:
        data = {}
    password = data.get('password') or ''
    if not verify_password(password):
        return JSONResponse({'ok': False, 'error': 'password is wrong'}, status_code=401)
    codes = generate_backup_codes(sess['username'], count=10)
    return {'ok': True, 'codes': codes}


app.mount('/static', StaticFiles(directory=str(HTML)), name='static')

def _refresh_loop():
    from metrics_helpers import refresh_health
    refresh_health()
threading.Thread(target=_refresh_loop, daemon=True).start()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('POLARIS_PORT', 3030)))
