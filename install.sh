#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MASTER_DIR="$SCRIPT_DIR/master"
VENV_DIR="$MASTER_DIR/.venv-staging"
ENV_FILE="$MASTER_DIR/.env"
SYSD_DIR="$HOME/.config/systemd/user"

echo "=== Polaris Hub installer ==="
echo "Install dir: $SCRIPT_DIR"
echo ""

command -v python3 >/dev/null || { echo "ERROR: python3 not found"; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' || { echo "ERROR: Python 3.11+ required"; exit 1; }
command -v systemctl >/dev/null || { echo "ERROR: systemctl not found"; exit 1; }

echo "--- 1. Python venv ---"
if [ -d "$VENV_DIR" ]; then
    echo "  venv exists"
else
    python3 -m venv "$VENV_DIR"
    echo "  created: $VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$MASTER_DIR/requirements.txt"
echo "  dependencies installed"

echo "--- 2. Configuration ---"
if [ -f "$ENV_FILE" ]; then
    echo "  .env exists, keeping"
else
    cp "$MASTER_DIR/master.env.example" "$ENV_FILE"
    SESSION_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    CSRF_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    FERNET_KEY=$("$VENV_DIR/bin/python" -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    sed -i "s|^SESSION_SECRET=.*|SESSION_SECRET=$SESSION_SECRET|" "$ENV_FILE"
    sed -i "s|^CSRF_SECRET=.*|CSRF_SECRET=$CSRF_SECRET|" "$ENV_FILE"
    sed -i "s|^FERNET_KEY=.*|FERNET_KEY=$FERNET_KEY|" "$ENV_FILE"
    read -p "  Username for login [sutej]: " INPUT_USER
    INPUT_USER=${INPUT_USER:-sutej}
    sed -i "s|^AUTH_USER=.*|AUTH_USER=$INPUT_USER|" "$ENV_FILE"
    echo "  generated secrets, wrote $ENV_FILE"
fi
chmod 600 "$ENV_FILE"

echo "--- 3. systemd units ---"
mkdir -p "$SYSD_DIR"
sed "s|%INSTALL_DIR%|$SCRIPT_DIR|g" "$SCRIPT_DIR/deploy/systemd/polaris.service" > "$SYSD_DIR/polaris.service"
sed "s|%INSTALL_DIR%|$SCRIPT_DIR|g" "$SCRIPT_DIR/deploy/systemd/ttyd.service" > "$SYSD_DIR/ttyd.service"
echo "  installed units"
systemctl --user daemon-reload
systemctl --user enable polaris.service
echo "  enabled polaris.service"

echo "--- 4. ttyd ---"
if command -v ttyd >/dev/null 2>&1; then
    systemctl --user enable ttyd.service
    echo "  ttyd found, enabled"
else
    echo "  ttyd NOT installed. Install via:"
    echo "    sudo dnf install -y ttyd"
fi

echo "--- 5. Start ---"
systemctl --user restart polaris.service
sleep 5
echo "  polaris.service: $(systemctl --user is-active polaris.service)"

echo ""
echo "=== Install complete ==="
PORT=$(grep '^PORT=' "$ENV_FILE" | cut -d= -f2)
USER=$(grep '^AUTH_USER=' "$ENV_FILE" | cut -d= -f2)
PASS=$(grep '^AUTH_PASS=' "$ENV_FILE" | cut -d= -f2)
echo "  Login: http://<tailscale-ip>:${PORT}/login"
echo "  User:  $USER"
echo "  Pass:  $PASS (change at /change-password after first login)"
