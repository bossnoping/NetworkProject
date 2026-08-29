"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          SRMP Demo Client — System Resource Monitoring Protocol              ║
║          สาธิตการส่ง Request และรับ Response ตาม SRMP v1.0                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  TCP Port 9001 : ส่ง Command และรับ Response                                ║
║  UDP Port 9000 : รับ Metric Broadcast จาก Server                            ║
║                                                                              ║
║  Usage:                                                                      ║
║    python srmp_demo_client.py                         # localhost            ║
║    python srmp_demo_client.py 192.168.1.100           # remote host         ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import socket
import threading
import sys
import time
from datetime import datetime

# ── ตั้งค่า Host / Port ──────────────────────────────────────────────────────
SERVER_HOST  = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
TCP_PORT     = 9001
UDP_PORT     = 9000

# ANSI Colors
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
# Logging Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def log_send(cmd: str):
    """พิมพ์ Request ที่ Client ส่งออก"""
    print(f"{DIM}[{_ts()}]{RESET} {BLUE}[CLIENT-SEND >>>]{RESET}  {BOLD}{cmd}{RESET}")


def log_recv(raw: str):
    """พิมพ์ Response ที่ Client ได้รับ — พร้อม parse Status Code / Phrase / Body"""
    raw = raw.strip()
    try:
        # Format: <CODE> <PHRASE> - <BODY>
        code_str, rest = raw.split(" ", 1)
        phrase, body   = rest.split(" - ", 1)
        code = int(code_str)
        color = GREEN if code == 200 else (PURPLE if code == 202 else RED)
        print(
            f"{DIM}[{_ts()}]{RESET} "
            f"{color}[CLIENT-RECV <<<]{RESET}  "
            f"{BOLD}{color}STATUS CODE: {code}  |  PHRASE: {phrase}{RESET}\n"
            f"             {DIM}Body: {body}{RESET}"
        )
    except Exception:
        # ถ้า parse ไม่ได้ พิมพ์ตรงๆ
        print(f"{DIM}[{_ts()}]{RESET} {PURPLE}[CLIENT-RECV <<<]{RESET}  {raw}")


def log_udp(raw: str):
    """พิมพ์ UDP Metric Packet ที่ได้รับจาก Server"""
    print(f"{DIM}[{_ts()}]{RESET} {YELLOW}[UDP-RECV   <<<]{RESET}  {DIM}{raw}{RESET}")


def log_info(msg: str):
    print(f"{DIM}[{_ts()}]{RESET} {CYAN}[CLIENT     ···]{RESET} {msg}")


def log_error(msg: str):
    print(f"{DIM}[{_ts()}]{RESET} {RED}[ERROR      !!!]{RESET} {msg}")


def divider(label: str = ""):
    line = "─" * 68
    if label:
        pad  = (68 - len(label) - 2) // 2
        line = "─" * pad + f" {label} " + "─" * (68 - pad - len(label) - 2)
    print(f"\n{DIM}{line}{RESET}")


# ══════════════════════════════════════════════════════════════════════════════
# UDP Listener Thread — รับ Metric Broadcast ในเบื้องหลัง
# ══════════════════════════════════════════════════════════════════════════════

_udp_running = False
_udp_count   = 0
_udp_limit   = 3  # แสดงแค่ N แรก เพื่อไม่ให้ log ท่วม


def udp_listener():
    global _udp_running, _udp_count
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(2)
    try:
        sock.bind(("0.0.0.0", UDP_PORT))
    except OSError as e:
        log_error(f"UDP bind ไม่ได้: {e}")
        return

    log_info(f"UDP Listener เปิดรับบน Port {UDP_PORT}")
    _udp_running = True

    while _udp_running:
        try:
            data, addr = sock.recvfrom(4096)
            msg = data.decode("utf-8", errors="replace")
            _udp_count += 1
            if _udp_count <= _udp_limit:
                log_udp(msg)
            elif _udp_count == _udp_limit + 1:
                print(f"  {DIM}... (ซ่อน UDP packets ที่เหลือ เพื่อความสะอาดของ log){RESET}")
        except socket.timeout:
            continue
        except OSError:
            break
    sock.close()


# ══════════════════════════════════════════════════════════════════════════════
# TCP Client — ส่ง SRMP Command และรับ Response
# ══════════════════════════════════════════════════════════════════════════════

class SRMPClient:
    def __init__(self, host: str, port: int):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(10)
        self._sock.connect((host, port))
        self._buf  = ""

    def send(self, command: str) -> str:
        """ส่ง Command (TCP) และรอรับ Response 1 บรรทัด"""
        log_send(command)
        self._sock.sendall((command + "\n").encode("utf-8"))
        return self._recv_line()

    def _recv_line(self) -> str:
        """รับข้อความ 1 บรรทัดจาก buffer"""
        while "\n" not in self._buf:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ConnectionError("Connection closed by server")
            self._buf += chunk.decode("utf-8", errors="replace")
        nl           = self._buf.index("\n")
        line         = self._buf[:nl]
        self._buf    = self._buf[nl + 1:]
        return line

    def close(self):
        self._sock.close()


# ══════════════════════════════════════════════════════════════════════════════
# Demo Scenario — แสดงการสื่อสารทุก Command ของ SRMP Protocol
# ══════════════════════════════════════════════════════════════════════════════

def run_demo(client: SRMPClient):
    """
    สาธิต SRMP Request–Response ทุกประเภท
    พิมพ์ทั้ง Command ที่ส่ง (Request) และ Response (Code + Phrase + Body)
    """

    # ───────────────────────────────────────────────────────────────────
    # 1. GET_TOP_PROCS
    # ───────────────────────────────────────────────────────────────────
    divider("1. GET_TOP_PROCS — ดูกระบวนการที่ใช้ CPU/RAM สูงสุด")
    resp = client.send("GET_TOP_PROCS limit=5 sortby=CPU")
    log_recv(resp)
    time.sleep(0.3)

    resp = client.send("GET_TOP_PROCS limit=3 sortby=RAM")
    log_recv(resp)
    time.sleep(0.3)

    # ───────────────────────────────────────────────────────────────────
    # 2. GET_SETTING
    # ───────────────────────────────────────────────────────────────────
    divider("2. GET_SETTING — อ่านค่าระบบ")
    resp = client.send("GET_SETTING name=volume")
    log_recv(resp)
    time.sleep(0.3)

    resp = client.send("GET_SETTING name=brightness")
    log_recv(resp)
    time.sleep(0.3)

    # GET_SETTING ด้วย name ที่ไม่รู้จัก → 404 NOT_FOUND
    resp = client.send("GET_SETTING name=unknown_sensor")
    log_recv(resp)
    time.sleep(0.3)

    # ───────────────────────────────────────────────────────────────────
    # 3. SET_VOL
    # ───────────────────────────────────────────────────────────────────
    divider("3. SET_VOL — ตั้งค่า Volume")
    resp = client.send("SET_VOL level=70")
    log_recv(resp)
    time.sleep(0.3)

    # SET_VOL ด้วย argument ไม่ถูกต้อง → 400 BAD_REQUEST
    resp = client.send("SET_VOL level=abc")
    log_recv(resp)
    time.sleep(0.3)

    # ───────────────────────────────────────────────────────────────────
    # 4. SET_BRIGHTNESS
    # ───────────────────────────────────────────────────────────────────
    divider("4. SET_BRIGHTNESS — ตั้งค่าความสว่างหน้าจอ")
    resp = client.send("SET_BRIGHTNESS level=60")
    log_recv(resp)
    time.sleep(0.3)

    # ───────────────────────────────────────────────────────────────────
    # 5. SET_SETTING (generic)
    # ───────────────────────────────────────────────────────────────────
    divider("5. SET_SETTING — ตั้งค่าด้วย Generic Command")
    resp = client.send("SET_SETTING name=volume value=55")
    log_recv(resp)
    time.sleep(0.3)

    resp = client.send("SET_SETTING name=brightness value=90")
    log_recv(resp)
    time.sleep(0.3)

    # ───────────────────────────────────────────────────────────────────
    # 6. KILL_PROC
    # ───────────────────────────────────────────────────────────────────
    divider("6. KILL_PROC — ยุติกระบวนการ")
    # ยุติ process ที่มีอยู่
    resp = client.send("KILL_PROC pid=7788")
    log_recv(resp)
    time.sleep(0.3)

    # ยุติ process ที่ไม่มีอยู่ → 404 NOT_FOUND
    resp = client.send("KILL_PROC pid=9999")
    log_recv(resp)
    time.sleep(0.3)

    # ───────────────────────────────────────────────────────────────────
    # 7. SYS_POWER
    # ───────────────────────────────────────────────────────────────────
    divider("7. SYS_POWER — ควบคุมพลังงานระบบ")
    resp = client.send("SYS_POWER action=LOCK")
    log_recv(resp)
    time.sleep(0.3)

    # action ไม่ถูกต้อง → 400 BAD_REQUEST
    resp = client.send("SYS_POWER action=SLEEP")
    log_recv(resp)
    time.sleep(0.3)

    # ───────────────────────────────────────────────────────────────────
    # 8. คำสั่งที่ไม่รู้จัก → 400 BAD_REQUEST
    # ───────────────────────────────────────────────────────────────────
    divider("8. คำสั่งไม่ถูกต้อง — Error Handling")
    resp = client.send("PING")
    log_recv(resp)
    time.sleep(0.3)

    resp = client.send("INVALID_COMMAND foo=bar")
    log_recv(resp)


# ══════════════════════════════════════════════════════════════════════════════
# Entry Point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "═" * 68)
    print(f"  {BOLD}{CYAN}SRMP Demo Client v1.0{RESET}  —  System Resource Monitoring Protocol")
    print("═" * 68)
    print(f"  {YELLOW}Server:  {RESET}  {SERVER_HOST}:{TCP_PORT}")
    print(f"  {YELLOW}Protocol:{RESET}  SRMP v1.0  (Custom Application-Layer Protocol)")
    print(f"  {YELLOW}Transport:{RESET} TCP (Command/Response)  +  UDP (Metric Broadcast)")
    print(f"  {YELLOW}Notation: {RESET} CLIENT-SEND = Request ส่งออก  |  CLIENT-RECV = Response ที่รับ")
    print("═" * 68)

    # ── เริ่ม UDP Listener ──────────────────────────────────────────────
    divider("UDP Metric Broadcast — รับข้อมูล Real-Time จาก Server")
    udp_thread = threading.Thread(target=udp_listener, daemon=True)
    udp_thread.start()
    time.sleep(3.5)  # รอรับ UDP แสดงตัวอย่าง 3 วินาที

    # ── เชื่อมต่อ TCP ──────────────────────────────────────────────────
    divider("TCP Request-Response — ส่งคำสั่งและรับผลลัพธ์")
    try:
        log_info(f"กำลังเชื่อมต่อ TCP → {SERVER_HOST}:{TCP_PORT}")
        client = SRMPClient(SERVER_HOST, TCP_PORT)
        log_info(f"เชื่อมต่อสำเร็จ ✓")

        run_demo(client)

    except ConnectionRefusedError:
        log_error(f"ไม่สามารถเชื่อมต่อได้ — กรุณาเปิด srmp_demo_server.py ก่อน")
        sys.exit(1)
    except Exception as e:
        log_error(f"เกิดข้อผิดพลาด: {e}")
        sys.exit(1)
    finally:
        try:
            client.close()
        except Exception:
            pass

    # ── สรุปผล ──────────────────────────────────────────────────────────
    _udp_running = False

    divider()
    print(f"\n  {GREEN}{BOLD}✓ Demo เสร็จสิ้น{RESET}")
    print(f"  {DIM}สรุป SRMP Status Codes ที่ใช้ใน Protocol:{RESET}")
    print(f"    {GREEN}200 OK{RESET}            — คำสั่งสำเร็จ")
    print(f"    {PURPLE}202 ALERT{RESET}         — การแจ้งเตือนจาก Server (Push Notification)")
    print(f"    {RED}400 BAD_REQUEST{RESET}   — คำสั่งหรือ argument ไม่ถูกต้อง")
    print(f"    {RED}404 NOT_FOUND{RESET}     — ไม่พบทรัพยากรที่ร้องขอ (process / setting)")
    print(f"    {RED}500 INTERNAL_ERROR{RESET} — เกิดข้อผิดพลาดภายใน Server")
    print()
