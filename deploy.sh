#!/usr/bin/env bash
set -euo pipefail

WYSE_IP="${WYSE_IP:-100.119.157.55}"
OPTIPLEX_IP="${OPTIPLEX_IP:-100.116.47.43}"
M_PORT="${POLARIS_PORT:-3030}"
S_PORT="${POLARIS_SATELLITE_PORT:-8001}"
INSTALL_DIR="${POLARIS_INSTALL_DIR:-$HOME/polaris-hub}"
BACKUP_DIR="${INSTALL_DIR}.bak"

G='\033[0;32m'; R='\033[0;31m'; Y='\033[0;33m'; C='\033[0;36m'; N='\033[0m'
info() { echo -e "${C}==>${N} $*"; }
ok()   { echo -e "${G}[OK]${N} $*"; }
warn() { echo -e "${Y}[!]${N} $*"; }
err()  { echo -e "${R}[X]${N} $*" >&2; }
die()  { err "$*"; exit 1; }

show_help() {
cat << 'HELPEOF'
Polaris Hub v2.0 - Deploy Script

USAGE: bash deploy.sh [OPTIONS]

OPTIONS:
  -u, --user <name>         Dashboard username      (default: sutej)
  -p, --pass <password>     Dashboard password      (prompted if not set)
  -P, --port <number>       Master port             (default: 3030)
  -s, --satellite-port <n>  Satellite port          (default: 8001)
  -o, --optiplex-ip <ip>    OptiPlex Tailscale IP   (default: 100.116.47.43)
  -w, --wyse-ip <ip>        Wyse Tailscale IP       (default: 100.119.157.55)
  -d, --dir <path>          Install directory       (default: ~/polaris-hub)
  -h, --help                Show this help

ENV VARS:
  POLARIS_USER, POLARIS_PASS, POLARIS_PORT,
  POLARIS_SATELLITE_PORT, OPTIPLEX_IP, WYSE_IP, POLARIS_INSTALL_DIR

EXAMPLES:
  bash deploy.sh
  bash deploy.sh --user admin --pass 'Secret123' --port 8080
  POLARIS_PASS=Secret123 bash deploy.sh
HELPEOF
exit 0
}

POLARIS_USER="${POLARIS_USER:-}"
POLARIS_PASS="${POLARIS_PASS:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -u|--user)           POLARIS_USER="$2"; shift 2 ;;
    -p|--pass)           POLARIS_PASS="$2"; shift 2 ;;
    -P|--port)           M_PORT="$2"; shift 2 ;;
    -s|--satellite-port) S_PORT="$2"; shift 2 ;;
    -o|--optiplex-ip)    OPTIPLEX_IP="$2"; shift 2 ;;
    -w|--wyse-ip)        WYSE_IP="$2"; shift 2 ;;
    -d|--dir)            INSTALL_DIR="$2"; BACKUP_DIR="${INSTALL_DIR}.bak"; shift 2 ;;
    -h|--help)           show_help ;;
    *) die "Unknown option: $1 (use --help)" ;;
  esac
done

[ -f "master-server.py" ] || [ -f "master/server.py" ] || die "Run from repo root"

echo "===================================================="
echo "  Polaris Hub v2.0 - Deploy"
echo "  Master:    $OPTIPLEX_IP:$M_PORT"
echo "  Satellite: $WYSE_IP:$S_PORT"
echo "  Install:   $INSTALL_DIR"
echo "===================================================="
echo ""

if [ -z "$POLARIS_USER" ]; then
  read -p "Dashboard username [sutej]: " POLARIS_USER < /dev/tty
  POLARIS_USER=${POLARIS_USER:-sutej}
fi
if [ -z "$POLARIS_PASS" ]; then
  read -sp "Dashboard password: " POLARIS_PASS < /dev/tty; echo ""
  read -sp "Confirm password:   " POLARIS_PASS2 < /dev/tty; echo ""
  [ "$POLARIS_PASS" != "$POLARIS_PASS2" ] && die "Passwords do not match"
fi
[ -z "$POLARIS_PASS" ] && die "Password cannot be empty"

info "Pre-flight checks..."
for cmd in docker curl scp ssh openssl git; do
  command -v "$cmd" >/dev/null || die "$cmd is not installed"
done
docker compose version >/dev/null 2>&1 || die "docker compose v2 not available"
ok "All tools present"

find_file() { find . -type f -name "$1" -not -path './.git/*' | head -1; }
MSERVER=$(find_file "master-server.py"); [ -z "$MSERVER" ] && MSERVER=$(find_file "server.py")
SAGENT=$(find_file "satellite-agent.py"); [ -z "$SAGENT" ] && SAGENT=$(find_file "agent.py")
MINDEX=$(find_file "master-index.html");  [ -z "$MINDEX" ]  && MINDEX=$(find_file "index.html")
MLOGIN=$(find_file "master-login.html");  [ -z "$MLOGIN" ]  && MLOGIN=$(find_file "login.html")
MCOMPOSE=$(find_file "master-docker-compose.yml"); [ -z "$MCOMPOSE" ] && MCOMPOSE=$(find_file "docker-compose.yml")
SCOMPOSE=$(find_file "satellite-docker-compose.yml")

echo ""
info "Files in repo:"
printf "    %-26s -> %s\n" "master-server.py"      "${MSERVER:-MISSING}"
printf "    %-26s -> %s\n" "master-index.html"     "${MINDEX:-MISSING}"
printf "    %-26s -> %s\n" "master-login.html"     "${MLOGIN:-MISSING}"
printf "    %-26s -> %s\n" "master-docker-compose" "${MCOMPOSE:-none}"
printf "    %-26s -> %s\n" "satellite-agent.py"    "${SAGENT:-MISSING}"
printf "    %-26s -> %s\n" "satellite-compose"     "${SCOMPOSE:-none}"
echo ""

[ -z "$MSERVER" ] && die "master-server.py missing"
[ -z "$SAGENT" ]  && die "satellite-agent.py missing"
[ -z "$MINDEX" ]  && die "master-index.html missing"
[ -z "$MLOGIN" ]  && die "master-login.html missing"

if [ -d "$INSTALL_DIR" ]; then
  info "Backing up $INSTALL_DIR -> $BACKUP_DIR ..."
  rm -rf "$BACKUP_DIR"; cp -r "$INSTALL_DIR" "$BACKUP_DIR"
  ok "Backup created"
fi

info "Installing master files..."
mkdir -p "$INSTALL_DIR/master/html"
cp "$MSERVER"  "$INSTALL_DIR/master/server.py"
cp "$MINDEX"   "$INSTALL_DIR/master/html/index.html"
cp "$MLOGIN"   "$INSTALL_DIR/master/html/login.html"
[ -f "manifest.json" ] && cp manifest.json "$INSTALL_DIR/master/html/manifest.json"
[ -f "sw.js" ]          && cp sw.js          "$INSTALL_DIR/master/html/sw.js"
cp *.png *.ico "$INSTALL_DIR/master/html/" 2>/dev/null || true
[ -n "$MCOMPOSE" ] && cp "$MCOMPOSE" "$INSTALL_DIR/master/docker-compose.yml"
sed -i 's|os\.environ\.get("AUTH_PASS"[^)]*)|os.environ.get("AUTH_PASS", "")|g' "$INSTALL_DIR/master/server.py"
sed -i 's|\.env\.example|.env|g' "$INSTALL_DIR/master/server.py"
sed -i 's|"dell1564"|""|g' "$INSTALL_DIR/master/server.py"
ok "Master installed + patched"

info "Writing .env (mode 600)..."
SECRET=$(openssl rand -hex 32)
cat > "$INSTALL_DIR/master/.env" << ENVEOF
AUTH_USER=${POLARIS_USER}
AUTH_PASS=${POLARIS_PASS}
BIND_IP=${OPTIPLEX_IP}
PORT=${M_PORT}
SESSION_SECRET=${SECRET}
SESSION_EXPIRY_DAYS=7
COOKIE_SECURE=false
OPTIPLEX_IP=${OPTIPLEX_IP}
WYSE_IP=${WYSE_IP}
WYSE_AGENT_PORT=${S_PORT}
ENVEOF
chmod 600 "$INSTALL_DIR/master/.env"
ok ".env written"

info "Pushing satellite to Wyse..."
ssh "sutej@${WYSE_IP}" "rm -rf ~/polaris-hub/satellite.bak; cp -r ~/polaris-hub/satellite ~/polaris-hub/satellite.bak 2>/dev/null || true; mkdir -p ~/polaris-hub/satellite"
scp -q "$SAGENT" "sutej@${WYSE_IP}:~/polaris-hub/satellite/agent.py"
[ -n "$SCOMPOSE" ] && scp -q "$SCOMPOSE" "sutej@${WYSE_IP}:~/polaris-hub/satellite/docker-compose.yml"
ok "Satellite pushed"

info "Cleaning up old atheris containers..."
docker rm -f atheris-master 2>/dev/null || true
ssh "sutej@${WYSE_IP}" "docker rm -f atheris-satellite 2>/dev/null || true"

info "Restarting Polaris Master..."
cd "$INSTALL_DIR/master"
docker compose down 2>/dev/null || true
docker compose up -d

info "Restarting Polaris Satellite..."
ssh "sutej@${WYSE_IP}" "cd ~/polaris-hub/satellite && docker compose down 2>/dev/null || true; docker compose up -d"

sleep 5
echo ""
echo "===================================================="
echo "  Verification"
echo "===================================================="
docker ps --filter name=polaris --format "table {{.Names}}\t{{.Status}}"
ssh "sutej@${WYSE_IP}" "docker ps --filter name=polaris --format 'table {{.Names}}\t{{.Status}}'"
echo ""
MH=$(curl -s --max-time 5 "http://${OPTIPLEX_IP}:${M_PORT}/api/health" || echo FAILED)
SH=$(curl -s --max-time 5 "http://${WYSE_IP}:${S_PORT}/api/health" || echo FAILED)
echo "  Master:    $MH"
echo "  Satellite: $SH"
echo ""

if [[ "$MH" == *ok* ]] && [[ "$SH" == *ok* ]]; then
  echo "===================================================="
  ok "DEPLOYMENT SUCCESSFUL"
  echo "   URL:      http://${OPTIPLEX_IP}:${M_PORT}"
  echo "   Username: ${POLARIS_USER}"
  echo "   Rollback: rm -rf $INSTALL_DIR && mv $BACKUP_DIR $INSTALL_DIR"
  echo "===================================================="
else
  err "DEPLOYMENT INCOMPLETE"
  docker logs polaris-master --tail 20 2>&1
  exit 1
fi
