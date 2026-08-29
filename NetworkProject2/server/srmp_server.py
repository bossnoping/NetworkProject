"""
SRMP Server — System Resource Monitoring Protocol
==================================================
TCP port 9001 : command/response channel
UDP port 9000 : broadcast metric packets (every 1 second)

Supported TCP commands:
  GET_TOP_PROCS limit=N sortby=CPU|RAM
  GET_SETTING   name=volume|brightness
  SET_VOL       level=N
  SET_BRIGHTNESS level=N
    SET_SETTING   name=volume|brightness value=N
    KILL_PROC     pid=N
  SYS_POWER     action=LOCK|SHUTDOWN|RESTART

Response format:
  <code> <PHRASE> - <body>\n

UDP packet format:
  METRIC cpu=X% ram=X% disk=X% temp_cpu=XC temp_gpu=XC
         net_up=XMB/s net_down=XMB/s net_online=1 net_ping=Xms uptime=Xs
"""

import socket
import threading
import time
import psutil
import subprocess
import ctypes
import sys
import os

TCP_PORT = 9001
UDP_PORT = 9000
UDP_BROADCAST = "<broadcast>"
METRIC_INTERVAL = 1.0  # seconds


# ══════════════════════════════════════════════════════════════════════════════
# Hardware helpers
# ══════════════════════════════════════════════════════════════════════════════

_lhm_computer = None
_lhm_lock = threading.Lock()


def _get_lhm_cpu_temp() -> float:
    """Read CPU temperatures directly from the bundled LHM .NET library."""
    global _lhm_computer
    try:
        import clr

        dll = os.path.join(
            os.path.dirname(__file__),
            "lhm",
            "LibreHardwareMonitor",
            "LibreHardwareMonitorLib.dll",
        )
        with _lhm_lock:
            if _lhm_computer is None:
                clr.AddReference(dll)
                hardware_module = __import__(
                    "LibreHardwareMonitor.Hardware",
                    fromlist=["Computer"],
                )
                _lhm_computer = hardware_module.Computer()
                _lhm_computer.IsCpuEnabled = True
                _lhm_computer.Open()

            values = []
            for hardware in _lhm_computer.Hardware:
                if str(hardware.HardwareType) != "Cpu":
                    continue
                hardware.Update()
                for sensor in hardware.Sensors:
                    if str(sensor.SensorType) != "Temperature":
                        continue
                    if sensor.Value is None:
                        continue
                    name = str(sensor.Name).lower()
                    if "cpu package" in name or name == "core max":
                        values.append(float(sensor.Value))
            return round(max(values), 1) if values else 0.0
    except Exception as e:
        print(f"[WARN] LibreHardwareMonitor CPU temperature failed: {e}")
        return 0.0


def get_cpu_temp() -> float:
    """Return CPU temperature in °C using multiple fallback methods."""
    # Method 1: direct LibreHardwareMonitor library (Windows).
    value = _get_lhm_cpu_temp()
    if value > 0:
        return value

    # Method 2: psutil sensors (Linux and hardware-monitoring providers).
    try:
        temperatures = psutil.sensors_temperatures()
        values = [
            reading.current
            for readings in temperatures.values()
            for reading in readings
            if reading.current > 0
        ]
        if values:
            return round(max(values), 1)
    except Exception:
        pass

    # Method 3: LibreHardwareMonitor/OpenHardwareMonitor WMI providers.
    try:
        import wmi
        for namespace in ("root\\LibreHardwareMonitor", "root\\OpenHardwareMonitor"):
            try:
                monitor = wmi.WMI(namespace=namespace)
                readings = monitor.Sensor(SensorType="Temperature")
                values = [
                    float(reading.Value)
                    for reading in readings
                    if reading.Value is not None
                    and float(reading.Value) > 0
                    and any(word in reading.Name.lower()
                            for word in ("cpu", "package", "core"))
                ]
                if values:
                    return round(max(values), 1)
            except Exception:
                continue
    except Exception:
        pass

    # Method 4: WMI MSAcpi_ThermalZoneTemperature
    try:
        import wmi
        w = wmi.WMI(namespace="root\\wmi")
        temps = w.MSAcpi_ThermalZoneTemperature()
        values = [
            round((temp.CurrentTemperature / 10.0) - 273.15, 1)
            for temp in temps
            if temp.CurrentTemperature > 0
        ]
        if values:
            val = max(values)
            if val > 0:
                return val
    except Exception:
        pass

    # Method 5: PowerShell CIM (works on most modern Windows systems)
    try:
        ps = (
            "$t = Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature "
            "-ErrorAction SilentlyContinue; "
            "if ($t) { $max = ($t.CurrentTemperature | Measure-Object -Maximum).Maximum; "
            "[math]::Round($max / 10.0 - 273.15, 1) } else { 0 }"
        )
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=4
        )
        val = float(result.stdout.strip())
        if val > 0:
            return round(val, 1)
    except Exception:
        pass

    return 0.0


def get_gpu_temp() -> float:
    """Return GPU temperature in °C via nvidia-smi, or 0.0."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2
        )
        val = result.stdout.strip()
        if val.isdigit():
            return float(val)
    except Exception:
        pass
    return 0.0


def get_net_stats():
    """Return (upload_MBs, download_MBs, online, ping_ms)."""
    try:
        counters1 = psutil.net_io_counters()
        time.sleep(0.5)
        counters2 = psutil.net_io_counters()
        up = max(0.0, (counters2.bytes_sent - counters1.bytes_sent) / 0.5 / 1_048_576)
        down = max(0.0, (counters2.bytes_recv - counters1.bytes_recv) / 0.5 / 1_048_576)
    except Exception:
        up, down = 0.0, 0.0

    # Check connectivity
    online = False
    ping_ms = 0
    try:
        result = subprocess.run(
            ["ping", "-n", "1", "-w", "1000", "8.8.8.8"],
            capture_output=True, text=True, timeout=3
        )
        if "TTL=" in result.stdout or "ttl=" in result.stdout:
            online = True
            import re
            m = re.search(r"Average\s*=\s*(\d+)ms", result.stdout)
            if not m:
                m = re.search(r"time[=<](\d+)ms", result.stdout)
            if m:
                ping_ms = int(m.group(1))
    except Exception:
        pass

    return round(up, 2), round(down, 2), online, ping_ms


def get_uptime_secs() -> int:
    return int(time.time() - psutil.boot_time())


def get_volume() -> int:
    """Get master volume (0-100) via pycaw."""
    try:
        from pycaw.pycaw import AudioUtilities
        device = AudioUtilities.GetSpeakers()
        vol = device.EndpointVolume
        return round(vol.GetMasterVolumeLevelScalar() * 100)
    except Exception as e:
        print(f"[WARN] get_volume failed: {e}")
    return -1



def set_volume(level: int):
    """Set master volume (0-100) via pycaw."""
    try:
        from pycaw.pycaw import AudioUtilities
        device = AudioUtilities.GetSpeakers()
        vol = device.EndpointVolume
        vol.SetMasterVolumeLevelScalar(level / 100.0, None)
        print(f"[VOL] Set to {level}%")
        return
    except Exception as e:
        print(f"[WARN] set_volume failed: {e}")


    # Method 2: PowerShell via nircmd or audio API
    try:
        scalar = level / 100.0
        ps = (
            f"$obj = New-Object -ComObject WScript.Shell; "
            f"[void][System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); "
            f"$vol = [math]::Round({level} / 100 * 65535); "
            f"$wshShell = New-Object -ComObject WScript.Shell"
        )
        subprocess.run(
            ["powershell", "-NonInteractive", "-Command",
             f"$audio = New-Object -ComObject WScript.Shell; "
             f"1..50 | ForEach-Object {{ $audio.SendKeys([char]174) }}; "
             f"1..{level // 2} | ForEach-Object {{ $audio.SendKeys([char]175) }}"],
            capture_output=True, timeout=5
        )
        print(f"[VOL] Set to ~{level}% via PowerShell keystrokes")
    except Exception as e:
        print(f"[WARN] set_volume PowerShell fallback failed: {e}")


def get_brightness() -> int:
    """Get screen brightness (0-100). Tries WMI then PowerShell."""
    # Method 1: WMI WmiMonitorBrightness
    try:
        import wmi
        w = wmi.WMI(namespace="root\\wmi")
        monitors = w.WmiMonitorBrightness()
        if monitors:
            return int(monitors[0].CurrentBrightness)
    except Exception as e:
        print(f"[WARN] WMI get_brightness failed: {e}")

    # Method 2: PowerShell Get-CimInstance
    try:
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-Command",
             "(Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightness "
             "-ErrorAction SilentlyContinue | Select-Object -First 1).CurrentBrightness"],
            capture_output=True, text=True, timeout=4
        )
        val = result.stdout.strip()
        if val and val.isdigit():
            return int(val)
    except Exception as e:
        print(f"[WARN] PowerShell get_brightness failed: {e}")

    return -1


def set_brightness(level: int):
    """Set screen brightness (0-100). Tries WMI then PowerShell."""
    # Method 1: WMI WmiMonitorBrightnessMethods
    try:
        import wmi
        w = wmi.WMI(namespace="root\\wmi")
        methods = w.WmiMonitorBrightnessMethods()
        if methods:
            methods[0].WmiSetBrightness(level, 0)
            print(f"[BRIGHTNESS] Set to {level}% via WMI")
            return
    except Exception as e:
        print(f"[WARN] WMI set_brightness failed: {e}")

    # Method 2: PowerShell Set-CimInstance
    try:
        subprocess.run(
            ["powershell", "-NonInteractive", "-Command",
             f"(Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightnessMethods "
             f"-ErrorAction SilentlyContinue | Select-Object -First 1)"
             f".WmiSetBrightness({level}, 0)"],
            capture_output=True, timeout=5
        )
        print(f"[BRIGHTNESS] Set to {level}% via PowerShell")
    except Exception as e:
        print(f"[WARN] PowerShell set_brightness failed: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TCP Server
# ══════════════════════════════════════════════════════════════════════════════

_clients: list = []
_clients_lock = threading.Lock()


def broadcast_alert(message: str):
    """Push a 202 ALERT to all connected clients."""
    line = f"202 ALERT - {message}\n".encode()
    with _clients_lock:
        for c in list(_clients):
            try:
                c.sendall(line)
            except Exception:
                pass


def parse_args(raw: str) -> dict:
    """Parse 'key=value key2=value2' into a dict."""
    result = {}
    for token in raw.split():
        if "=" in token:
            k, v = token.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def handle_command(cmd_line: str):
    """Process a single SRMP command. Returns response string or None."""
    cmd_line = cmd_line.strip()
    if not cmd_line:
        return None

    parts = cmd_line.split(None, 1)
    verb = parts[0].upper()
    args_raw = parts[1] if len(parts) > 1 else ""
    args = parse_args(args_raw)

    # ── GET_TOP_PROCS ──────────────────────────────────────────────────────
    if verb == "GET_TOP_PROCS":
        limit = int(args.get("limit", 8))
        sortby = args.get("sortby", "CPU").upper()

        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "memory_info"]):
            try:
                info = p.info
                pid = info["pid"]
                name = info["name"] or "unknown"
                if pid <= 0 or "idle" in name.lower():
                    continue
                cpu = info["cpu_percent"] or 0.0
                ram = info["memory_percent"] or 0.0
                ram_mb = (info["memory_info"].rss / 1_048_576) if info["memory_info"] else 0.0
                procs.append((pid, name, cpu, ram, ram_mb))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Normalize CPU (psutil returns per-core %)
        cpu_count = psutil.cpu_count(logical=True) or 1
        procs = [(pid, name, cpu / cpu_count, ram, ram_mb) for pid, name, cpu, ram, ram_mb in procs]

        if sortby == "RAM":
            procs.sort(key=lambda x: x[3], reverse=True)
        else:
            procs.sort(key=lambda x: x[2], reverse=True)

        procs = procs[:limit]
        blocks = ",".join(
            "{pid:%d,name:%s,cpu:%.1f%%,ram:%.1f%%,ram_mb:%.1fMB}" % (pid, name, cpu, ram, ram_mb)
            for pid, name, cpu, ram, ram_mb in procs
        )
        return "200 OK - procs=[%s]\n" % blocks

    # ── GET_SETTING ────────────────────────────────────────────────────────
    elif verb == "GET_SETTING":
        name = args.get("name", "")
        if name == "volume":
            val = get_volume()
        elif name == "brightness":
            val = get_brightness()
        else:
            return "404 NOT_FOUND - UNKNOWN_SETTING name=%s\n" % name
        return "200 OK - SETTING_VALUE name=%s value=%d\n" % (name, val)

    # ── SET_SETTING ───────────────────────────────────────────────────────
    elif verb == "SET_SETTING":
        name = args.get("name", "")
        try:
            level = max(0, min(100, int(args.get("value", ""))))
        except (TypeError, ValueError):
            return "400 BAD_REQUEST - INVALID_SETTING_VALUE\n"

        if name == "volume":
            set_volume(level)
        elif name == "brightness":
            set_brightness(level)
        else:
            return "404 NOT_FOUND - SETTING_NOT_FOUND\n"
        return "200 OK - SETTING_UPDATED\n"

    # ── SET_VOL ────────────────────────────────────────────────────────────
    elif verb == "SET_VOL":
        try:
            level = max(0, min(100, int(args.get("level", ""))))
        except (TypeError, ValueError):
            return "400 BAD_REQUEST - INVALID_VOLUME\n"
        set_volume(level)
        return "200 OK - VOLUME_SET_%d\n" % level

    # ── SET_BRIGHTNESS ─────────────────────────────────────────────────────
    elif verb == "SET_BRIGHTNESS":
        try:
            level = max(0, min(100, int(args.get("level", ""))))
        except (TypeError, ValueError):
            return "400 BAD_REQUEST - INVALID_BRIGHTNESS\n"
        set_brightness(level)
        return "200 OK - BRIGHTNESS_SET_%d\n" % level

    # ── KILL_PROC ──────────────────────────────────────────────────────────
    elif verb == "KILL_PROC":
        try:
            pid = int(args.get("pid", ""))
        except (TypeError, ValueError):
            return "400 BAD_REQUEST - INVALID_PID\n"

        for p in psutil.process_iter(["pid"]):
            try:
                if p.info["pid"] == pid:
                    p.kill()
                    return "200 OK - PROC_KILLED\n"
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return "404 NOT_FOUND\n"

    # ── SYS_POWER ─────────────────────────────────────────────────────────
    elif verb == "SYS_POWER":
        action = args.get("action", "").upper()
        if action == "LOCK":
            ctypes.windll.user32.LockWorkStation()
            return "200 OK - SYSTEM_LOCKED\n"
        elif action == "SHUTDOWN":
            subprocess.Popen(["shutdown", "/s", "/t", "5"])
            return "200 OK - SYSTEM_SHUTDOWN\n"
        elif action == "RESTART":
            subprocess.Popen(["shutdown", "/r", "/t", "5"])
            return "200 OK - SYSTEM_RESTARTING\n"
        else:
            return "400 BAD_REQUEST - INVALID_POWER_ACTION\n"

    else:
        return "400 BAD REQUEST - Unknown command: %s\n" % verb


def client_thread(conn, addr):
    print("[TCP] Client connected: %s" % str(addr))
    with _clients_lock:
        _clients.append(conn)

    # Warm up psutil cpu_percent (first call always returns 0)
    for p in psutil.process_iter(["pid", "cpu_percent"]):
        pass

    buf = ""
    try:
        conn.settimeout(60)
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk.decode("utf-8", errors="replace")
            while "\n" in buf:
                nl = buf.index("\n")
                line = buf[:nl]
                buf = buf[nl + 1:]
                if not line.strip():
                    continue
                print("[TCP] << %s" % line.strip())
                try:
                    resp = handle_command(line)
                    if resp:
                        print("[TCP] >> %s" % resp.strip())
                        conn.sendall(resp.encode())
                except Exception as e:
                    err = "500 INTERNAL ERROR - %s\n" % e
                    conn.sendall(err.encode())
    except (ConnectionResetError, TimeoutError, OSError):
        pass
    finally:
        with _clients_lock:
            if conn in _clients:
                _clients.remove(conn)
        conn.close()
        print("[TCP] Client disconnected: %s" % str(addr))


def tcp_server():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", TCP_PORT))
    srv.listen(8)
    print("[TCP] Listening on port %d" % TCP_PORT)
    while True:
        try:
            conn, addr = srv.accept()
            t = threading.Thread(target=client_thread, args=(conn, addr), daemon=True)
            t.start()
        except Exception as e:
            print("[TCP] Accept error: %s" % e)


# ══════════════════════════════════════════════════════════════════════════════
# UDP Broadcaster
# ══════════════════════════════════════════════════════════════════════════════

def udp_broadcaster():
    # 1. สร้าง Socket แบบ UDP (User Datagram Protocol)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # 2. ตั้งค่าให้ Socket สามารถส่งข้อมูลแบบ Broadcast ได้ (Broadcast คือการส่งข้อมูลให้ทุกเครื่องในวง Network)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    print("[UDP] Broadcasting metrics on port %d every %.1fs" % (UDP_PORT, METRIC_INTERVAL))

    # 3. ดึงค่าสถิติต่างๆ จากระบบ (psutil, LibreHardwareMonitor, nvidia-smi)
    while True:
        try:
            # psutil: ดึงค่า CPU, RAM, Disk
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage("/").percent
            temp_cpu = get_cpu_temp()
            temp_gpu = get_gpu_temp()
            net_up, net_down, online, ping = get_net_stats()
            uptime = get_uptime_secs()
            # 4. ประกอบข้อความตามข้อกำหนดโปรโตคอล SRMP METRIC
            packet = (
                "METRIC cpu=%.1f%% ram=%.1f%% disk=%.1f%%"
                " temp_cpu=%.1fC temp_gpu=%.1fC"
                " net_up=%.2fMB/s net_down=%.2fMB/s"
                " net_online=%s net_ping=%dms"
                " uptime=%ds"
            ) % (
                cpu, ram, disk,
                temp_cpu, temp_gpu,
                net_up, net_down,
                "1" if online else "0", ping,
                uptime,
            )
            # 5. ส่งแพ็กเก็ตไปยังที่อยู่ Broadcast บน Port 9000
            sock.sendto(packet.encode(), (UDP_BROADCAST, UDP_PORT))
            print("[UDP] %s" % packet)
        except Exception as e:
            print("[UDP] Error: %s" % e)
        # 6. หน่วงเวลาตามค่า METRIC_INTERVAL (ค่าเริ่มต้นคือ 1.0 วินาที) เพื่อไม่ให้ส่งข้อมูลถี่เกินไป
        time.sleep(METRIC_INTERVAL)


def is_admin() -> bool:
    """Return True if the current process has administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def elevate_and_restart() -> bool:
    """
    Re-launch this script with UAC elevation (runas) and exit the current process.
    Returns True if elevation was successfully triggered (caller should exit).
    Returns False if UAC could not be shown (non-interactive context) — caller should continue.
    """
    script = os.path.abspath(__file__)
    python = sys.executable
    params = f'"{script}"' + ((' ' + ' '.join(f'"{a}"' for a in sys.argv[1:])) if sys.argv[1:] else '')
    print("[SRMP] Not running as admin. Requesting elevation...")
    ret = ctypes.windll.shell32.ShellExecuteW(
        None,       # hwnd
        "runas",    # verb  — triggers UAC prompt
        python,     # file
        params,     # parameters
        None,       # working directory (inherit)
        1,          # SW_SHOWNORMAL
    )
    if ret > 32:
        # UAC prompt shown, elevated process is launching — exit this one
        sys.exit(0)
    else:
        # code 5 = ERROR_ACCESS_DENIED (non-interactive / no desktop)
        # Fall through and run without elevation rather than crash
        print(f"[SRMP] UAC elevation not available (code {ret}) — continuing without admin privileges.")
        print("[SRMP] TIP: Right-click your terminal and choose 'Run as Administrator' for full access.")
        return False


def get_host_network_info():
    """Retrieve all local IPv4 addresses and MAC addresses of network adapters."""
    adapters = []
    try:
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        for iface_name, iface_addrs in addrs.items():
            stat = stats.get(iface_name)
            if stat and not stat.isup:
                continue
            ipv4 = None
            mac = None
            for addr in iface_addrs:
                if addr.family == socket.AF_INET:
                    if not addr.address.startswith("127."):
                        ipv4 = addr.address
                elif addr.family == psutil.AF_LINK or getattr(addr, 'family', None) == -1:
                    mac = addr.address
            if ipv4:
                adapters.append((iface_name, ipv4, mac or "N/A"))
    except Exception:
        pass
    if not adapters:
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            if not ip.startswith("127."):
                adapters.append(("Default Adapter", ip, "N/A"))
        except Exception:
            pass
    return adapters


def configure_firewall():
    """Automatically configure Windows Firewall to allow SRMP TCP 9001 and UDP 9000."""
    try:
        # Check and add TCP port 9001
        subprocess.run(
            ["netsh", "advfirewall", "firewall", "add", "rule",
             "name=SRMP_Server_TCP_9001", "dir=in", "action=allow",
             "protocol=TCP", "localport=9001", "profile=any"],
            capture_output=True, text=True, timeout=5
        )
        # Check and add UDP port 9000
        subprocess.run(
            ["netsh", "advfirewall", "firewall", "add", "rule",
             "name=SRMP_Server_UDP_9000", "dir=in", "action=allow",
             "protocol=UDP", "localport=9000", "profile=any"],
            capture_output=True, text=True, timeout=5
        )
    except Exception as e:
        print(f"[FIREWALL] Notice: {e}")


def print_startup_banner():
    hostname = socket.gethostname()
    adapters = get_host_network_info()

    print("\n" + "=" * 65)
    print(f"   🚀 SRMP SERVER RUNNING  |  Host: {hostname}")
    print("=" * 65)
    print("   📍 กรอก IP Address ต่อไปนี้ในแอปพลิเคชันเพื่อเชื่อมต่อ:")
    if adapters:
        for idx, (iface, ip, mac) in enumerate(adapters, 1):
            print(f"      [{idx}] {ip:<15} ({iface})")
            if mac != "N/A":
                print(f"          └─ MAC Address: {mac} (ใช้สำหรับ Wake-on-LAN)")
    else:
        print("      (ตรวจไม่พบ IP ในวงเครือข่าย กรุณาตรวจสอบการเชื่อมต่อ Wi-Fi/LAN)")

    print("-" * 65)
    print(f"   📡 TCP Port (Command & Control) : {TCP_PORT}")
    print(f"   📻 UDP Port (Metric Streaming)  : {UDP_PORT} (Broadcast ทุก {METRIC_INTERVAL}s)")
    print("   🛡️  Windows Firewall Rules       : Auto-Configured (Allowed)")
    print("=" * 65 + "\n")


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # ── Ensure we are running as Administrator ──────────────────────────────
    if not is_admin():
        elevate_and_restart()

    print("[SRMP] Running as Administrator.")

    # Configure firewall rules automatically for new PCs
    configure_firewall()

    # Warm up psutil cpu_percent (first call always returns 0.0)
    psutil.cpu_percent(interval=1)

    threading.Thread(target=tcp_server, daemon=True).start()
    threading.Thread(target=udp_broadcaster, daemon=True).start()

    # Print clean and helpful host information for users
    print_startup_banner()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SRMP] Shutting down.")


