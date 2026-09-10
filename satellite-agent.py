#!/usr/bin/env python3
"""Atheris Hub v2.0 - Satellite Agent (Wyse 5070)."""
import http.client, http.server, json, os, socket, time

PORT      = int(os.environ.get("PORT", "8001"))
BIND_IP   = os.environ.get("BIND_IP", "100.119.157.55")
NODE_NAME = os.environ.get("NODE_NAME", "Wyse 5070")

class UnixHTTP(http.client.HTTPConnection):
    def __init__(self, path, timeout=2.0):
        super().__init__("localhost", timeout=timeout)
        self._sp = path
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self._sp)

def proc(f):
    p = "/host/proc/" + f
    return p if os.path.exists(p) else "/proc/" + f

def uptime():
    try:
        with open(proc("uptime")) as f: s = float(f.readline().split()[0])
        d,h,m = int(s//86400), int((s%86400)//3600), int((s%3600)//60)
        return (f"{d}d " if d else "") + (f"{h}h " if h or d else "") + f"{m}m"
    except Exception: return None

_last_net = {"t":0,"rx":0,"tx":0}
def net_io():
    global _last_net
    try:
        rx = tx = 0
        with open(proc("net/dev")) as f:
            for line in f:
                if ":" in line:
                    iface, stats = line.split(":",1)
                    if iface.strip() == "lo": continue
                    fl = stats.split(); rx += int(fl[0]); tx += int(fl[8])
        now = time.time()
        if _last_net["t"] == 0:
            _last_net = {"t":now,"rx":rx,"tx":tx}; return None
        dt = now - _last_net["t"]; drx, dtx = rx - _last_net["rx"], tx - _last_net["tx"]
        _last_net = {"t":now,"rx":rx,"tx":tx}
        if dt <= 0 or drx < 0 or dtx < 0: return None
        return {"total_mbps": round(((drx+dtx)*8)/(dt*1e6),2),
                "rx_mbps": round((drx*8)/(dt*1e6),2),
                "tx_mbps": round((dtx*8)/(dt*1e6),2)}
    except Exception: return None

_last_cpu = {"t":0,"i":0}
def cpu():
    global _last_cpu
    try:
        with open(proc("stat")) as f: vals = [float(x) for x in f.readline().split()[1:]]
        idle = vals[3]+vals[4]; total = sum(vals)
        if _last_cpu["t"] == 0:
            _last_cpu = {"t":total,"i":idle}; return None
        dt, di = total-_last_cpu["t"], idle-_last_cpu["i"]
        _last_cpu = {"t":total,"i":idle}
        if dt <= 0: return None
        return round(max(0,min(100,(1-di/dt)*100)),1)
    except Exception: return None

def ram():
    try:
        tot = avail = 0
        with open(proc("meminfo")) as f:
            for l in f:
                if l.startswith("MemTotal:"): tot = int(l.split()[1])
                elif l.startswith("MemAvailable:"): avail = int(l.split()[1])
        if tot == 0: return None
        used = tot - avail
        return {"used_gb": round(used/1048576,2), "total_gb": round(tot/1048576,2),
                "percent": round(used/tot*100,1)}
    except Exception: return None

def disk():
    p = "/host_root" if os.path.exists("/host_root") else "/"
    try:
        st = os.statvfs(p); tot = st.f_blocks*st.f_frsize; free = st.f_bavail*st.f_frsize
        used = tot - free
        return {"used_gb": round(used/2**30,1), "total_gb": round(tot/2**30,1),
                "free_gb": round(free/2**30,1), "percent": round(used/tot*100,1),
                "warning": (used/tot) > 0.8}
    except Exception: return None

def docker_containers(sock="/var/run/docker.sock"):
    if not os.path.exists(sock): return []
    try:
        c = UnixHTTP(sock); c.request("GET","/containers/json?all=true"); r = c.getresponse()
        if r.status != 200: return []
        data = json.loads(r.read().decode())
        out = []
        for x in data:
            names = [n.lstrip("/") for n in x.get("Names",[])]
            ports = []
            for p in x.get("Ports",[]):
                if p.get("PublicPort"): ports.append(f"{p['PublicPort']}:{p['PrivatePort']}")
                elif p.get("PrivatePort"): ports.append(str(p["PrivatePort"]))
            out.append({"name": names[0] if names else "container",
                        "status": "running" if x.get("State")=="running" else x.get("State","stopped"),
                        "ports": ", ".join(ports) or "internal",
                        "image": x.get("Image","")})
        return out
    except Exception: return []

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def j(self,d,code=200):
        b = json.dumps(d).encode()
        self.send_response(code)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(b)))
        self.send_header("Connection","close")
        self.end_headers(); self.wfile.write(b)
    def do_GET(self):
        if self.path == "/api/health": return self.j({"status":"ok","node":"wyse"})
        if self.path == "/api/metrics":
            return self.j({"status":"online","node_id":"wyse","node_name":NODE_NAME,
                "role":"Satellite Agent","ip":BIND_IP,
                "specs":"Thin Client • 7.6GB RAM • 146GB eMMC",
                "cpu":{"load":cpu(),"cores":os.cpu_count() or 4},
                "ram":ram(),"disk":disk(),"net":net_io(),
                "uptime":uptime(),"containers":docker_containers()})
        self.send_error(404)

def main():
    print(f"[*] Atheris Satellite on {BIND_IP}:{PORT}")
    http.server.ThreadingHTTPServer((BIND_IP,PORT),H).serve_forever()

if __name__ == "__main__": main()
