"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           SRMP Demo Server — System Resource Monitoring Protocol             ║
║           สาธิตการทำงานของ Application-Layer Protocol (SRMP v1.0)           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  TCP Port 9001 : Command/Response Channel                                    ║
║  UDP Port 9000 : Metric Broadcast Channel (ทุก 1 วินาที)                    ║
║                                                                              ║
║  Response Format:  <STATUS_CODE> <STATUS_PHRASE> - <BODY>\n                 ║
║  UDP Format:       METRIC cpu=X% ram=X% disk=X% temp_cpu=XC ...             ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import socket
import threading
import time
import random
from datetime import datetime


# ══════════════════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════════════════

TCP_PORT         = 9001
UDP_PORT         = 9000
UDP_BROADCAST    = "<broadcast>"
METRIC_INTERVAL  = 1.0   # วินาที

# ANSI Color Codes
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
PURPLE = "\033[95m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"


# ══════════════════════════════════════════════════════════════════════════════
# Logging Helpers — พิมพ์ข้อความ Protocol อย่างสวยงาม
# ══════════════════════════════════════════════════════════════════════════════

def _timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def log_udp_send(msg: str):
    print(f"{DIM}[{_timestamp()}]{RESET} {YELLOW}[UDP-SEND >>>]{RESET} {msg}")


def log_tcp_recv(addr: tuple, msg: str):
    client_tag = f"{addr[0]}:{addr[1]}"
    print(f"{DIM}[{_timestamp()}]{RESET} {BLUE}[TCP-RECV <<< {client_tag}]{RESET}  {BOLD}{msg}{RESET}")


def log_tcp_send(addr: tuple, code: int, phrase: str, body: str):
    client_tag = f"{addr[0]}:{addr[1]}"
    color = GREEN if code == 200 else (PURPLE if code == 202 else RED)
    print(
        f"{DIM}[{_timestamp()}]{RESET} "
        f"{color}[TCP-SEND >>> {client_tag}]{RESET}  "
        f"{BOLD}{color}{code} {phrase}{RESET}"
        f"{DIM} - {body}{RESET}"
    )


def log_event(msg: str):
    print(f"{DIM}[{_timestamp()}]{RESET} {CYAN}[SERVER    ···]{RESET} {msg}")


# ══════════════════════════════════════════════════════════════════════════════
# Simulated Hardware
# ══════════════════════════════════════════════════════════════════════════════

class SimulatedHardware:
    def __init__(self):
        self._cpu      = 35.0
        self._ram      = 55.0
        self._disk     = 42.0
        self._temp_cpu = 52.0
        self._temp_gpu = 44.0
        self._net_up   = 0.05
        self._net_down = 1.20
        self._volume   = 65
        self._brightness = 80
        self._start    = time.time()
        self.processes = [
            {"pid": 1240, "name": "chrome.exe",   "cpu": 12.4, "ram": 8.2,  "ram_mb": 1344.0},
            {"pid": 4808, "name": "Code.exe",      "cpu":  8.1, "ram": 5.5,  "ram_mb":  902.1},
            {"pid": 3012, "name": "python.exe",    "cpu":  5.3, "ram": 2.1,  "ram_mb":  341.6},
            {"pid": 2340, "name": "Discord.exe",   "cpu":  3.7, "ram": 3.8,  "ram_mb":  620.4},
            {"pid": 7788, "name": "Spotify.exe",   "cpu":  2.9, "ram": 2.4,  "ram_mb":  393.0},
            {"pid": 8524, "name": "explorer.exe",  "cpu":  1.2, "ram": 0.9,  "ram_mb":  147.3},
            {"pid": 1004, "name": "svchost.exe",   "cpu":  0.8, "ram": 0.6,  "ram_mb":   98.5},
            {"pid": 9320, "name": "Taskmgr.exe",   "cpu":  0.3, "ram": 0.4,  "ram_mb":   65.2},
        ]

    def _walk(self, val, lo, hi, step=2.0):
        return round(max(lo, min(hi, val + random.uniform(-step, step))), 1)

    def tick(self):
        self._cpu      = self._walk(self._cpu,       0, 100, 3.0)
        self._ram      = self._walk(self._ram,       20,  95, 1.5)
        self._disk     = self._walk(self._disk,      30,  90, 0.5)
        self._temp_cpu = self._walk(self._temp_cpu,  40,  95, 1.5)
        self._temp_gpu = self._walk(self._temp_gpu,  35,  90, 1.0)
        self._net_up   = round(max(0, self._net_up   + random.uniform(-0.1, 0.2)), 2)
        self._net_down = round(max(0, self._net_down + random.uniform(-0.3, 0.5)), 2)
        for p in self.processes:
            p["cpu"] = round(max(0, p["cpu"] + random.uniform(-1.0, 1.0)), 1)

    @property
    def metric_packet(self) -> str:
        uptime = int(time.time() - self._start)
        return (
            f"METRIC cpu={self._cpu:.1f}% ram={self._ram:.1f}% disk={self._disk:.1f}%"
            f" temp_cpu={self._temp_cpu:.1f}C temp_gpu={self._temp_gpu:.1f}C"
            f" net_up={self._net_up:.2f}MB/s net_down={self._net_down:.2f}MB/s"
            f" net_online=1 net_ping={random.randint(8, 25)}ms uptime={uptime}s"
        )

    @property
    def temp_cpu(self): return self._temp_cpu

    def get_volume(self):     return self._volume
    def get_brightness(self): return self._brightness
    def set_volume(self, v):     self._volume = max(0, min(100, v))
    def set_brightness(self, v): self._brightness = max(0, min(100, v))

    def kill_process(self, pid) -> bool:
        for i, p in enumerate(self.processes):
            if p["pid"] == pid:
                self.processes.pop(i)
                return True
        return False

    def get_top_procs(self, limit=8, sortby="CPU") -> list:
        key = "cpu" if sortby.upper() == "CPU" else "ram"
        return sorted(self.processes, key=lambda x: x[key], reverse=True)[:limit]


hw = SimulatedHardware()
_clients: list = []
_clients_lock = threading.Lock()


# ══════════════════════════════════════════════════════════════════════════════
# Response Builder
# ══════════════════════════════════════════════════════════════════════════════

def build_response(code: int, phrase: str, body: str) -> str:
    """สร้าง SRMP Response: <STATUS_CODE> <STATUS_PHRASE> - <BODY>\n"""
    return f"{code} {phrase} - {body}\n"


def send_response(conn, addr, code, phrase, body):
    raw = build_response(code, phrase, body)
    log_tcp_send(addr, code, phrase, body)
    try:
        conn.sendall(raw.encode("utf-8"))
    except OSError:
        pass


def broadcast_alert(message: str):
    """ส่ง 202 ALERT ไปยัง Client ทุกเครื่อง (Server-Push)"""
    raw = build_response(202, "ALERT", message).encode("utf-8")
    with _clients_lock:
        for conn, addr in list(_clients):
            try:
                conn.sendall(raw)
                log_tcp_send(addr, 202, "ALERT", message)
            except OSError:
                pass


# ══════════════════════════════════════════════════════════════════════════════
# Command Dispatcher
# ══════════════════════════════════════════════════════════════════════════════

def parse_args(raw: str) -> dict:
    result = {}
    for token in raw.split():
        if "=" in token:
            k, v = token.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def dispatch(verb: str, args: dict):
    """ประมวลผล SRMP Command → คืน (code, phrase, body)"""

    if verb == "GET_TOP_PROCS":
        try:
            limit  = int(args.get("limit", 8))
            sortby = args.get("sortby", "CPU")
        except ValueError:
            return 400, "BAD_REQUEST", "INVALID_ARGS"
        procs  = hw.get_top_procs(limit, sortby)
        blocks = ",".join(
            f"{{pid:{p['pid']},name:{p['name']},cpu:{p['cpu']:.1f}%,"
            f"ram:{p['ram']:.1f}%,ram_mb:{p['ram_mb']:.1f}MB}}"
            for p in procs
        )
        return 200, "OK", f"procs=[{blocks}]"

    elif verb == "GET_SETTING":
        name = args.get("name", "")
        if name == "volume":     return 200, "OK", f"SETTING_VALUE name=volume value={hw.get_volume()}"
        elif name == "brightness": return 200, "OK", f"SETTING_VALUE name=brightness value={hw.get_brightness()}"
        else: return 404, "NOT_FOUND", f"UNKNOWN_SETTING name={name}"

    elif verb == "SET_VOL":
        try: level = max(0, min(100, int(args.get("level", ""))))
        except (TypeError, ValueError): return 400, "BAD_REQUEST", "INVALID_VOLUME"
        hw.set_volume(level)
        return 200, "OK", f"VOLUME_SET_{level}"

    elif verb == "SET_BRIGHTNESS":
        try: level = max(0, min(100, int(args.get("level", ""))))
        except (TypeError, ValueError): return 400, "BAD_REQUEST", "INVALID_BRIGHTNESS"
        hw.set_brightness(level)
        return 200, "OK", f"BRIGHTNESS_SET_{level}"

    elif verb == "SET_SETTING":
        name = args.get("name", "")
        try: level = max(0, min(100, int(args.get("value", ""))))
        except (TypeError, ValueError): return 400, "BAD_REQUEST", "INVALID_SETTING_VALUE"
        if name == "volume":       hw.set_volume(level)
        elif name == "brightness": hw.set_brightness(level)
        else: return 404, "NOT_FOUND", f"UNKNOWN_SETTING name={name}"
        return 200, "OK", "SETTING_UPDATED"

    elif verb == "KILL_PROC":
        try: pid = int(args.get("pid", ""))
        except (TypeError, ValueError): return 400, "BAD_REQUEST", "INVALID_PID"
        if hw.kill_process(pid): return 200, "OK", "PROC_KILLED"
        return 404, "NOT_FOUND", f"PROCESS_NOT_FOUND pid={pid}"

    elif verb == "SYS_POWER":
        action = args.get("action", "").upper()
        map_ = {"LOCK": "SYSTEM_LOCKED", "SHUTDOWN": "SYSTEM_SHUTDOWN", "RESTART": "SYSTEM_RESTARTING"}
        if action not in map_: return 400, "BAD_REQUEST", f"INVALID_POWER_ACTION action={action}"
        return 200, "OK", map_[action]

    else:
        return 400, "BAD_REQUEST", f"UNKNOWN_COMMAND verb={verb}"


# ══════════════════════════════════════════════════════════════════════════════
# TCP Client Thread
# ══════════════════════════════════════════════════════════════════════════════

def client_thread(conn, addr):
    log_event(f"Client เชื่อมต่อสำเร็จ ← {addr[0]}:{addr[1]}")
    with _clients_lock:
        _clients.append((conn, addr))

    buf = ""
    try:
        conn.settimeout(60)
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk.decode("utf-8", errors="replace")
            while "\n" in buf:
                nl   = buf.index("\n")
                line = buf[:nl].strip()
                buf  = buf[nl + 1:]
                if not line:
                    continue
                log_tcp_recv(addr, line)
                parts    = line.split(None, 1)
                verb     = parts[0].upper()
                args_raw = parts[1] if len(parts) > 1 else ""
                args     = parse_args(args_raw)
                try:
                    code, phrase, body = dispatch(verb, args)
                    send_response(conn, addr, code, phrase, body)
                except Exception as e:
                    send_response(conn, addr, 500, "INTERNAL_ERROR", str(e))
    except (ConnectionResetError, TimeoutError, OSError):
        pass
    finally:
        with _clients_lock:
            _clients[:] = [(c, a) for c, a in _clients if c is not conn]
        conn.close()
        log_event(f"Client ยกเลิกการเชื่อมต่อ ✕ {addr[0]}:{addr[1]}")


# ══════════════════════════════════════════════════════════════════════════════
# TCP Server Thread
# ══════════════════════════════════════════════════════════════════════════════

def tcp_server():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", TCP_PORT))
    srv.listen(8)
    log_event(f"TCP รับฟังบน Port {TCP_PORT}")
    while True:
        try:
            conn, addr = srv.accept()
            threading.Thread(target=client_thread, args=(conn, addr), daemon=True).start()
        except Exception as e:
            log_event(f"TCP error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# UDP Broadcaster Thread
# ══════════════════════════════════════════════════════════════════════════════

def udp_broadcaster():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    log_event(f"UDP Broadcast บน Port {UDP_PORT}")
    while True:
        hw.tick()
        packet = hw.metric_packet
        log_udp_send(packet)
        sock.sendto(packet.encode("utf-8"), (UDP_BROADCAST, UDP_PORT))
        if hw.temp_cpu > 85.0:
            broadcast_alert(f"HIGH_CPU_TEMP temp_cpu={hw.temp_cpu:.1f}C threshold=85.0C")
        time.sleep(METRIC_INTERVAL)


# ══════════════════════════════════════════════════════════════════════════════
# Entry Point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "═" * 68)
    print(f"  {BOLD}{CYAN}SRMP Demo Server v1.0{RESET}  —  System Resource Monitoring Protocol")
    print("═" * 68)
    print(f"  {YELLOW}Protocol:{RESET}  SRMP v1.0  (Custom Application-Layer Protocol)")
    print(f"  {YELLOW}TCP Port:{RESET}  {TCP_PORT}  →  Command & Control (Request / Response)")
    print(f"  {YELLOW}UDP Port:{RESET}  {UDP_PORT}  →  Metric Broadcast  (Server → All Clients)")
    print(f"  {YELLOW}Format:  {RESET}  <STATUS_CODE> <STATUS_PHRASE> - <BODY>\\n")
    print(f"  {YELLOW}Mode:    {RESET}  Simulated Hardware (Demo — ไม่ต้องลง psutil/WMI)")
    print("═" * 68)
    print(f"  {DIM}กด Ctrl+C เพื่อหยุด{RESET}\n")

    threading.Thread(target=tcp_server,     daemon=True).start()
    threading.Thread(target=udp_broadcaster, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n{YELLOW}[SERVER] หยุดทำงาน...{RESET}\n")
