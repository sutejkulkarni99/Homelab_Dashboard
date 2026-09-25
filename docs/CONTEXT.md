# Homelab System Context — Canonical Reference

This file is the source of truth for what runs where. Claude MUST read this before creating any new service, opening any port, or editing any system file. Claude MUST propose updates after successful service deployment, with user confirmation before writing.

---

## Update Rules (for Claude)

1. **Read this file first** on any task involving: new services, ports, docker, systemd, firewall, network, storage.
2. **Never write this file without user confirmation.** Always show a diff/proposal first.
3. **Update the Change Log** at the end with every approved change.
4. **Bump "Last updated"** whenever the file changes.
5. **Do not delete entries.** If a service is retired, mark it `(retired YYYY-MM-DD)` and move it to the bottom of its section.
6. **Port allocation:** before proposing a new port, check the Listening Ports section. Never reuse an active port.

---

## Quick Reference

**Tailscale IPs:**
- OptiPlex: `100.116.47.43`
- Wyse: `100.119.157.55`
- Windows laptop: `100.68.73.17`

**Public URLs (DuckDNS):**
- `sutej.duckdns.org` → Nextcloud
- `sutej-jellyfin.duckdns.org` → Jellyfin
- `cockpit-sutej.duckdns.org` → Cockpit

**Service layout convention:**
- **Polaris dashboard:** `~/polaris-hub/master/` (separate compose stack, NOT in `~/server-setup/`)
- Systemd user services: `~/.config/systemd/user/*.service`
- Docker compose stacks: `~/server-setup/<service>/`
- Project workspaces: `~/Projects/`
- Persistent data: `/mnt/HomeLab_Share/` or service-specific volumes

**Port allocation strategy:**
- `1024-2999` — reserved (system)
- `3000-4999` — user apps and dashboards
- `5000-7999` — APIs and backend services
- `8000-8999` — dev tools, management UIs
- `9000-9999` — infrastructure (portainer, etc.)
- `10000-19999` — experimental / temporary

---

## Off-Limits (Claude must NOT touch)

- `~/.ssh/` — SSH keys
- `/etc/ssh/sshd_config` — SSH daemon
- `/etc/fstab` — mount table
- `/etc/sudoers` — sudo config
- `~/.bashrc` — shell config (ask first)
- Firewall default policies (`iptables -P INPUT`)
- Any systemd *system* service (only user services)
- `/mnt/HomeLab_Share/BAQQ PCBs/` — production KiCad data (read-only for Claude)

---

## Current Services

*(auto-populated from snapshot below; curated purposes added manually)*

### LiteLLM Proxy
- Port: `4000`
- Type: systemd user service (`litellm-proxy.service`)
- Purpose: Unified LLM router (7 model aliases, 5 providers)
- Config: `~/.litellm/config.yaml`, keys in `~/.litellm/.env`
- Depends on: network only

### Jarvis Watcher
- Type: systemd user service (`jarvis-watcher.service`)
- Purpose: Autonomous prompt queue processor
- Watches: `~/Projects/inbox/`, writes to `~/Projects/outbox/`
- Model: reads `<!-- model: X -->` directive from file head
- Depends on: LiteLLM (localhost:4000)

### KiCad MCP Servers
- Ports: `3334` (kicad-mcp-pro), `8090` (mcp-proxy aggregation)
- Type: systemd user services
- Purpose: KiCad tooling for Claude Code
- Depends on: `kicad-cli` (native Fedora install)

---

## Storage Layout

*(populated from snapshot; document what lives where)*

---

## Conventions

- **New services start here:** propose a docker-compose or systemd unit, place files in `~/server-setup/<name>/` or `~/.config/systemd/user/`
- **Volumes:** data lives in named docker volumes or `/mnt/HomeLab_Share/<service>/`
- **Logging:** services write to journald (systemd) or `~/Projects/logs/` (custom)
- **Environment files:** secrets in `.env` files with mode `600`, never committed
- **Ports:** bind to `0.0.0.0` for Tailscale-reachable services; use `127.0.0.1` for local-only
- **Firewall:** prefer Tailscale-only exposure; public services go through nginx-proxy at `80/443`

---

## Firewall Fix — Public Traffic to nginx-proxy (2026-09-19)

### Root Cause
firewalld's `FORWARD` chain has a default **policy DROP**. Public traffic destined for nginx-proxy (ports 80, 81, 443 on `enp4s0`) was being dropped in `FORWARD` before it ever reached the `DOCKER-USER` chain. Both chains require explicit rules to allow the traffic through.

### The Fix
1. **FORWARD chain** — added `ACCEPT` rule for interface `enp4s0` to destination ports 80, 81, 443 (TCP)
2. **DOCKER-USER chain** — added matching `RETURN` rule for the same interface/ports so Docker's internal filtering passes the traffic

### Persistence
Rules are re-applied at boot by `/usr/local/bin/docker-user-rules.sh` via systemd service `docker-user-rules.service`.

### ⚠️ Critical Warning
If **either** chain loses its rule, **DuckDNS URLs stop working** while **Tailscale access continues to work** (because Tailscale traffic bypasses the public interface path).

### Verification Commands
```bash
# Check FORWARD chain (should show ACCEPT for enp4s0 dports 80,81,443)
sudo iptables -L FORWARD -n | head -3

# Check DOCKER-USER chain (should show RETURN for enp4s0 dports 80,81,443)
sudo iptables -L DOCKER-USER -n
```

---

## Firewall Fix — Public Traffic to nginx-proxy (2026-09-19)

### Root Cause
firewalld's `FORWARD` chain has a default **policy DROP**. Public traffic destined for nginx-proxy (ports 80, 81, 443 on `enp4s0`) was being dropped in `FORWARD` before it ever reached the `DOCKER-USER` chain. Both chains require explicit rules to allow the traffic through.

### The Fix
1. **FORWARD chain** — added `ACCEPT` rule for interface `enp4s0` to destination ports 80, 81, 443 (TCP)
2. **DOCKER-USER chain** — added matching `RETURN` rule for the same interface/ports so Docker's internal filtering passes the traffic

### Persistence
Rules are re-applied at boot by `/usr/local/bin/docker-user-rules.sh` via systemd service `docker-user-rules.service`.

### ⚠️ Critical Warning
If **either** chain loses its rule, **DuckDNS URLs stop working** while **Tailscale access continues to work** (because Tailscale traffic bypasses the public interface path).

### Verification Commands
```bash
# Check FORWARD chain (should show ACCEPT for enp4s0 dports 80,81,443)
sudo iptables -L FORWARD -n | head -3

# Check DOCKER-USER chain (should show RETURN for enp4s0 dports 80,81,443)
sudo iptables -L DOCKER-USER -n
```

---

### Immich
- Port: `3000`
- Type: docker compose stack (`~/server-setup/immich/`)
- Purpose: Self-hosted photo backup
- Compose: `~/server-setup/immich/docker-compose.yml`
- Library: `~/server-setup/immich/library/`
- DB: vectorchord postgres image (required for smart search)
- No ML container (no GPU on OptiPlex)
- Depends on: network only

---


### Polaris Hub (FastAPI — production)

- Port: `3030`
- Service: `polaris.service` (systemd user)
- Code: `~/polaris-hub/master/app_new.py` (FastAPI)
- HTML: `~/polaris-hub/master/html/`
- venv: `~/polaris-hub/master/.venv-staging/`
- Session: `SESSION_EXPIRY_HOURS` in `.env` (default 6), file-backed in `.sessions.json`
- Device trust: `DEVICE_TRUST_HOURS` in `.env` (default 24), file-backed in `.devices.json`
- 2FA: TOTP via Microsoft Authenticator (`pyotp`)
- Password: Argon2id hash in `.env` (`PASSWORD_HASH`) or legacy plaintext (`AUTH_PASS`)
- Rate limit: `LOGIN_RATE_LIMIT` in `.env` (default 20/5min per IP)
- CSRF: double-submit token, required on all POSTs

**Routes:** `/`, `/login`, `/setup-2fa`, `/projects`, `/ssh`, `/api/*`

**Old Docker Polaris:** container `polaris-master` stopped. `server.py` kept as reference.

**Pre-cutover backup:** `/home/sutej/server-setup/_backups/20260925-153923-pre-cutover`
**Rollback:** `/home/sutej/server-setup/_backups/20260925-153923-pre-cutover/rollback-to-old-polaris.sh`
**Pre-FastAPI restore:** `/mnt/HomeLab_Share/_restore-points/20260925-123116-pre-fastapi/`

### Listening Ports
```
0.0.0.0:11434 
0.0.0.0:139 
0.0.0.0:22 
0.0.0.0:3001 
0.0.0.0:3334 users:(("kicad-mcp-pro",pid=3468076,fd=9))
0.0.0.0:443 
0.0.0.0:445 
0.0.0.0:5355 
0.0.0.0:80 
0.0.0.0:8000 
0.0.0.0:8070 
0.0.0.0:8080 
0.0.0.0:8096 
0.0.0.0:81 
0.0.0.0:8443 
0.0.0.0:8888 
0.0.0.0:8920 
0.0.0.0:9000 
0.0.0.0:9443 
100.116.47.43:3030 
100.116.47.43:55475 
[::]:11434 
127.0.0.1:4000 users:(("litellm",pid=1727857,fd=14))
127.0.0.1:4330 
127.0.0.1:44321 
127.0.0.1:631 
127.0.0.53%lo:53 
127.0.0.54:53 
[::]:139 
[::1]:4330 
[::1]:44321 
[::1]:631 
*:1716 users:(("kdeconnectd",pid=17336,fd=17))
[::]:22 
[::]:3001 
[::]:443 
[::]:445 
[::]:5355 
[::]:80 
[::]:8080 
*:8090 users:(("mcp-proxy",pid=3582474,fd=10))
[::]:8096 
[::]:81 
[::]:8443 
[::]:8888 
[::]:8920 
[::]:9000 
*:9090 
[::]:9443 
[fd7a:115c:a1e0::a39:2f2c]:54147 
```

### Docker Containers
```
NAMES            PORTS                                                                                                                                                                                STATUS
polaris-master                                                                                                                                                                                        Up 5 days
jupyter          0.0.0.0:8888->8888/tcp, [::]:8888->8888/tcp                                                                                                                                          Up 5 days (healthy)
vscode           0.0.0.0:8443->8443/tcp, [::]:8443->8443/tcp                                                                                                                                          Up 2 days
stirling-pdf     0.0.0.0:8070->8080/tcp                                                                                                                                                               Up 5 days (healthy)
nginx-proxy      0.0.0.0:80-81->80-81/tcp, [::]:80-81->80-81/tcp, 0.0.0.0:443->443/tcp, [::]:443->443/tcp                                                                                             Up 5 days
duckdns                                                                                                                                                                                               Up 5 days
autoapply        0.0.0.0:8000->3000/tcp                                                                                                                                                               Up 5 days
open-webui       0.0.0.0:3001->8080/tcp, [::]:3001->8080/tcp                                                                                                                                          Up 5 days (healthy)
ollama-coder     0.0.0.0:11434->11434/tcp, [::]:11434->11434/tcp                                                                                                                                      Up 5 days
jupyter-lab                                                                                                                                                                                           Up 5 days (healthy)
code-server                                                                                                                                                                                           Up 5 days
nextcloud        0.0.0.0:8080->80/tcp, [::]:8080->80/tcp                                                                                                                                              Up 5 days
jellyfin         0.0.0.0:1900->1900/udp, [::]:1900->1900/udp, 0.0.0.0:8096->8096/tcp, [::]:8096->8096/tcp, 0.0.0.0:7359->7359/udp, [::]:7359->7359/udp, 0.0.0.0:8920->8920/tcp, [::]:8920->8920/tcp   Up 5 days (healthy)
nginx-db         3306/tcp                                                                                                                                                                             Up 5 days
portainer        0.0.0.0:9000->9000/tcp, [::]:9000->9000/tcp, 8000/tcp, 0.0.0.0:9443->9443/tcp, [::]:9443->9443/tcp                                                                                   Up 5 days
```

### Systemd User Services (running)
```
akonadi_control.service
app-geoclue\x2ddemo\x2dagent@autostart.service
app-org.freedesktop.problems.applet@autostart.service
app-org.kde.discover.notifier@autostart.service
app-org.kde.kalendarac@autostart.service
app-org.kde.kdeconnect.daemon@autostart.service
app-org.kde.xwaylandvideobridge@autostart.service
app-sealertauto@autostart.service
at-spi-dbus-bus.service
dbus-:1.2-org.freedesktop.impl.portal.desktop.kwallet@0.service
dbus-:1.2-org.kde.kwalletd6@0.service
dbus-:1.33-org.a11y.atspi.Registry@0.service
dbus-broker.service
dconf.service
drkonqi-coredump-launcher@10-12618-2823635_2831016-0.service
drkonqi-coredump-launcher@11-12620-2828441_2821088-0.service
drkonqi-coredump-launcher@12-12621-2832005_2839253-0.service
drkonqi-coredump-launcher@13-16659-2872123_2862665-0.service
drkonqi-coredump-launcher@14-8753-1811148_5995686-0.service
drkonqi-coredump-launcher@8-12617-2813826_2805074-0.service
drkonqi-coredump-launcher@9-4527-2814445_2808307-0.service
jarvis-watcher.service
kde-baloo.service
kicad-mcp.service
kunifiedpush-distributor.service
litellm-proxy.service
mcp-proxy.service
obex.service
pipewire-pulse.service
pipewire.service
plasma-gmenudbusmenuproxy.service
plasma-kaccess.service
plasma-kactivitymanagerd.service
plasma-kded6.service
plasma-ksmserver.service
plasma-kwin_wayland.service
plasma-plasmashell.service
plasma-polkit-agent.service
plasma-powerdevil.service
plasma-xdg-desktop-portal-kde.service
plasma-xembedsniproxy.service
run-p17553-i30843.service
ssh-agent.service
uresourced.service
wireplumber.service
xdg-desktop-portal-gtk.service
xdg-desktop-portal.service
xdg-document-portal.service
xdg-permission-store.service
```

### Systemd User Services (enabled, all states)
```
dbus-broker.service
jarvis-watcher.service
kicad-mcp.service
litellm-proxy.service
mcp-proxy.service
obex.service
systemd-tmpfiles-setup.service
wireplumber.service
xdg-user-dirs.service
```

### Tailscale Status
```
100.116.47.43   ip-100-64-90-163  kulkarnisutej99@  linux    -                                                             
100.68.73.17    desktop-au92m8q   kulkarnisutej99@  windows  active; relay "fra", tx 12894724 rx 2385364                   
100.105.18.22   laptop-anmg7k6r   kulkarnisutej99@  windows  offline, last seen 25d ago                                    
100.117.42.25   predator          kulkarnisutej99@  windows  offline, last seen 4d ago                                     
100.119.157.55  sutej             kulkarnisutej99@  linux    active; direct 185.17.205.25:59373, tx 422462516 rx 34311036  
100.119.151.30  sutejs-s24        kulkarnisutej99@  android  offline, last seen 18h ago                                    
100.114.49.9    sutejs-tab-s8     kulkarnisutej99@  android  offline, last seen 6h ago                                     
```

### Tailscale IPs
```
100.116.47.43
```

### Top-level Directories
```
drwxr-xr-x. 1 sutej sutej       3194 Sep 19 18:54 .
drwxr-xr-x. 1 root  root          10 Jul  5 23:48 ..
drwxr-xr-x. 1 sutej sutej         52 Aug 31 16:36 asset_extractor
drwxr-xr-x. 1 sutej sutej        450 Aug 28 20:21 AutoApplyAI
drwx------. 1 sutej sutej       1382 Sep 19 16:34 .cache
drwxr-xr-x. 1 sutej sutej          0 Aug 27 18:34 cd
drwxr-xr-x. 1 sutej sutej        358 Sep 19 18:01 .claude
drwxr-xr-x. 1 sutej sutej       2524 Sep 17 17:10 .config
drwxr-xr-x. 1 sutej sutej         22 Oct 28  2025 .dbus
drwxr-xr-x. 1 sutej sutej         40 Jul  7 00:02 Desktop
drwx------. 1 sutej sutej         66 Aug 27 14:35 .docker
drwxr-xr-x. 1 sutej sutej         58 Jul  7 00:21 docker
drwxr-xr-x. 1 sutej sutej         78 Aug 27 18:35 Documents
drwxr-xr-x. 1 sutej sutej        216 Aug 27 18:37 Downloads
drwx------. 1 sutej sutej        104 Oct 28  2025 .gnupg
drwxr-xr-x. 1 sutej sutej         12 Sep 17 16:53 go
drwxr-xr-x. 1 sutej sutej         52 Aug 27 14:31 gui_auto_capture
drwxr-xr-x. 1 sutej sutej         18 Aug 27 18:37 homelab
drwxrwxrwx. 1 sutej sutej         30 Jul 22  2025 .ipython
drwxrwxrwx. 1 sutej sutej          0 Jul  5 01:03 KiCAD
drwxr-xr-x. 1 sutej sutej         22 Sep 17 17:48 .kicad_mcp
drwxr-xr-x. 1 sutej sutej        354 Sep 17 16:53 kicad-mcp
drwxr-xr-x. 1 sutej sutej        128 Sep 19 17:52 .litellm
drwxrwxrwx. 1 sutej sutej         32 Jul 22  2025 .local
drwxrwxrwx. 1 sutej sutej        174 Oct 30  2025 .MathWorks
drwxrwxrwx. 1 sutej sutej         34 Oct 30  2025 .matlab
drwxrwxrwx. 1 sutej sutej         56 Jul  6 23:12 .MATLABConnector
drwxrwxrwx. 1 sutej sutej         48 May 22  2025 .mozilla
drwxrwxrwx. 1 sutej sutej          0 Jul  5 01:03 Music
drwxrwxrwx. 1 sutej sutej          0 Jul  5 01:03 NextCloud
drwxr-xr-x. 1 sutej sutej         20 Sep  1 15:49 nginx-auto
drwxrwxrwx. 1 sutej sutej          0 Jul  5 01:03 photoframe
drwxrwxrwx. 1 sutej sutej         22 Jul  6 19:56 Pictures
drwxrwxrwx. 1 sutej sutej         10 Oct 30  2025 .pki
drwxr-xr-x. 1 sutej sutej         12 Sep 10 17:55 polaris-hub
drwxr-xr-x. 1 sutej sutej         12 Sep 10 19:31 polaris-hub.bak
drwxr-xr-x. 1 sutej sutej        284 Sep 19 18:09 Projects
drwxrwxrwx. 1 sutej sutej          0 Jul  5 01:03 Public
drwxr-xr-x. 1 sutej docker       556 Sep 17 01:21 server-setup
drwxrwxrwx. 1 sutej sutej          0 Jul  5 01:03 shared_code
drwx------. 1 sutej sutej        140 Sep 19 16:27 .ssh
drwxr-xr-x. 1 root  root          44 Sep  9 16:55 stirling
drwxr-xr-x. 1 sutej sutej         84 Sep 19 18:54 system
drwxrwxrwx. 1 sutej sutej          0 Jul  5 01:03 Templates
drwxr-xr-x. 1 sutej sutej          0 Aug 27 18:34 unzip
drwxrwxrwx. 1 sutej sutej          6 May 22  2025 .var
drwxr-xr-x. 1 sutej sutej         90 Jul 13 23:40 .venv
drwxrwxrwx. 1 sutej sutej          0 Jul  5 01:03 Videos
drwxrwxrwx. 1 sutej sutej          0 Jul  5 01:03 VirtualBox VMs
drwxrwxrwx. 1 sutej sutej          0 Jul  5 01:03 .vnc
drwxrwxrwx. 1 sutej sutej          0 Jul  5 01:03 Webpages
drwxr-xr-x. 1 sutej sutej         48 Sep 10 18:36 workspace
---
total 32
drwxr-xr-x. 1 sutej docker  556 Sep 17 01:21 .
drwxr-xr-x. 1 sutej sutej  3194 Sep 19 18:54 ..
-rw-r--r--. 1 sutej sutej   326 Jul  6 21:28 docker-compose-cockpit.yml
-rw-r--r--. 1 sutej docker 3262 Sep 10 19:01 docker-compose.yml
-rw-r--r--. 1 sutej sutej  3359 Jul 14 00:24 docker-compose.yml.bak
-rw-r--r--. 1 sutej sutej  3452 Sep 10 18:26 docker-compose.yml.bak.20260910_182635
-rw-r--r--. 1 sutej sutej  3555 Sep 10 19:01 docker-compose.yml.bak.20260910_190112
-rw-r--r--. 1 sutej sutej  3262 Sep 10 19:01 docker-compose.yml.bak.20260910_190138
-rw-r--r--. 1 sutej sutej  3262 Sep 10 19:01 docker-compose.yml.bak.20260910_190143
-rw-r--r--. 1 sutej sutej   283 Jul 14 00:51 Dockerfile.vscode
drwxr-xr-x. 1 sutej sutej    12 Jul  7 09:48 homepage
drwxr-xr-x. 1 root  root     22 Jul  6 19:13 jellyfin
drwxr-xr-x. 1 sutej sutej   156 Sep 10 18:27 jupyter
drwxr-xr-x. 1 root  root      8 Jul  6 20:59 nextcloud
drwxr-xr-x. 1 root  root     62 Jul  6 20:50 nginx
drwxr-xr-x. 1 sutej sutej    12 Jul  7 09:48 vscode
---
total 44
drwxr-xr-x. 1 sutej sutej   284 Sep 19 18:09 .
drwxr-xr-x. 1 sutej sutej  3194 Sep 19 18:54 ..
drwxr-xr-x. 1 sutej sutej   454 Sep 19 18:09 archive
drwxr-xr-x. 1 sutej sutej    38 Sep 17 17:16 .claude
-rw-r--r--. 1 sutej sutej  1605 Sep 19 18:55 CLAUDE.md
-rwxr-xr-x. 1 sutej sutej 13736 Sep 19 18:09 eng-test-bqueue
-rw-r--r--. 1 sutej sutej  4376 Sep 19 18:09 eng-test-bqueue.c
-rw-r--r--. 1 sutej sutej   698 Sep 18 15:36 fibonacci.py
-rw-r--r--. 1 sutej sutej  1151 Sep 18 15:36 fibonacci.txt
drwxr-xr-x. 1 sutej sutej    24 Sep 19 18:09 inbox
drwxr-xr-x. 1 sutej sutej   524 Sep 19 03:01 LAB-HP-41000-Controller
drwxr-xr-x. 1 sutej sutej   118 Sep 19 18:07 logs
drwxr-xr-x. 1 sutej sutej   326 Sep 19 18:07 outbox
-rwxr-xr-x. 1 sutej sutej   699 Sep 19 18:07 run-prompt.sh
-rw-r--r--. 1 sutej sutej  1233 Sep 19 18:09 watcher.log
```

### Disk Usage
```
Filesystem              Size  Used Avail Use% Mounted on
/dev/sdb3               1.9T  139G  1.7T   8% /
/dev/sdb3               1.9T  139G  1.7T   8% /home
/dev/sda1               932G  889G   44G  96% /mnt/driveA
/dev/sdb3               1.9T  139G  1.7T   8% /
/dev/sdb3               1.9T  139G  1.7T   8% /
//100.119.157.55/sutej  146G   99G   48G  68% /mnt/wyse
```

### Firewall (firewalld)
```
FedoraWorkstation (default, active)
  target: default
  ingress-priority: 0
  egress-priority: 0
  icmp-block-inversion: no
  interfaces: enp4s0
  sources: 
  services: dhcpv6-client http https samba samba-client ssh
  ports: 80/tcp 443/tcp 81/tcp
  protocols: 
  forward: yes
  masquerade: no
  forward-ports: 
  source-ports: 
  icmp-blocks: 
  rich rules: 
```
