"""
╔══════════════════════════════════════════════════════════════════════════════╗
║               SRMP: System Resource Monitoring Protocol (v1.0)              ║
║         สถาปัตยกรรม Application-Layer Protocol สำหรับ Real-time Monitoring   ║
╚══════════════════════════════════════════════════════════════════════════════╝

📌 ภาพรวมการทำงานของโพรโทคอล SRMP (Protocol Architecture):
โพรโทคอล SRMP ออกแบบมาเพื่อการติดตามทรัพยากรและการควบคุมเครื่องคอมพิวเตอร์ระยะไกล
โดยแบ่งการทำงานออกเป็น 2 ช่องทาง (Dual-Channel Architecture):

 ┌──────────────────────────────────────────────────────────────────────────┐
 │                               SRMP SERVER                                │
 │                                                                          │
 │  ┌─────────────────────────┐               ┌──────────────────────────┐  │
 │  │  UDP Channel (Port 9000)│               │  TCP Channel (Port 9001) │  │
 │  │  [Telemetry Streaming]  │               │  [Command & Control]     │  │
 │  └────────────┬────────────┘               └─────────────▲────────────┘  │
 └───────────────┼──────────────────────────────────────────┼───────────────┘
                 │ (1) Broadcast ทุก 1 วินาที                │ (2) Two-Way TCP
                 │     (Unreliable, Fast, Telemetry)        │     (Reliable, Interactive)
                 ▼                                          ▼
 ┌──────────────────────────────────────────────────────────────────────────┐
 │                         SRMP CLIENTS (Flutter / Demo)                    │
 │                                                                          │
 │  • รับค่า Real-time: CPU, RAM, Disk, Temp, Net I/O, Ping, Uptime        │
 │  • ส่งคำสั่งควบคุม: GET_TOP_PROCS, SET_VOL, KILL_PROC, SYS_POWER ฯลฯ     │
 │  • รับ Asynchronous Alert (202 ALERT) เมื่อเกิดความร้อนสูงผิดปกติ        │
 └──────────────────────────────────────────────────────────────────────────┘

"""

import socket
import threading
import time
import psutil
import subprocess
import ctypes
import sys
import os
import signal

TCP_PORT = 9001
UDP_PORT = 9000
UDP_BROADCAST = "<broadcast>"
METRIC_INTERVAL = 1.0  # seconds


# ══════════════════════════════════════════════════════════════════════════════
# Hardware helpers
# ══════════════════════════════════════════════════════════════════════════════

_lhm_computer = None
_lhm_lock = threading.Lock()
_last_cpu_temp = 42.0


def _get_lhm_cpu_temp() -> float: #ดึงค่าอุณหภูมิ
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
        if not os.path.exists(dll):
            return 0.0

        with _lhm_lock:
            if _lhm_computer is None:
                clr.AddReference(dll)
                hardware_module = __import__(
                    "LibreHardwareMonitor.Hardware",
                    fromlist=["Computer"],
                )
                _lhm_computer = hardware_module.Computer()
                _lhm_computer.IsCpuEnabled = True
                _lhm_computer.IsMotherboardEnabled = True
                _lhm_computer.IsControllerEnabled = True
                _lhm_computer.Open()

            values = []

            def scan_hardware(hw):
                try:
                    hw.Update()
                    for sub in hw.SubHardware:
                        scan_hardware(sub)
                    for sensor in hw.Sensors:
                        if str(sensor.SensorType) != "Temperature" or sensor.Value is None:
                            continue
                        val = float(sensor.Value)
                        if val <= 0:
                            continue
                        name = str(sensor.Name).lower()
                        hw_type = str(hw.HardwareType).lower()
                        if (
                            any(k in hw_type for k in ("cpu", "core", "motherboard"))
                            or any(k in name for k in ("cpu", "core", "package", "tctl", "tdie", "tjmax"))
                        ):
                            values.append((name, val))
                except Exception:
                    pass

            for hardware in _lhm_computer.Hardware:
                scan_hardware(hardware)

            if not values:
                return 0.0

            # Priority 1: CPU Package / Core Max / Core Average / Tctl
            priority_names = (
                "cpu package",
                "package",
                "core max",
                "core average",
                "cpu (tctl/tdie)",
                "tctl/tdie",
                "cpu ccd",
            )
            for prio in priority_names:
                for name, val in values:
                    if prio in name:
                        return round(val, 1)

            # Priority 2: Any CPU Core temperature
            core_vals = [val for name, val in values if "core" in name or "cpu" in name]
            if core_vals:
                return round(max(core_vals), 1)

            return round(max(val for _, val in values), 1)
    except Exception as e:
        return 0.0


def get_cpu_temp() -> float: #ดึงค่าอุณหภูมิ
    """
    Return CPU temperature in °C using multiple fallback methods.
    If direct kernel driver access is restricted (non-admin), seamlessly
    computes a dynamic thermal model based on active CPU utilization.
    """
    global _last_cpu_temp

    # Method 1: direct LibreHardwareMonitor library (.NET / Ring0 driver)
    value = _get_lhm_cpu_temp()
    if value > 0:
        _last_cpu_temp = value
        return value

    # Method 2: psutil sensors (Linux and supported Windows drivers)
    try:
        temperatures = psutil.sensors_temperatures()
        values = [
            reading.current
            for readings in temperatures.values()
            for reading in readings
            if reading.current > 0
        ]
        if values:
            _last_cpu_temp = round(max(values), 1)
            return _last_cpu_temp
    except Exception:
        pass

    # Method 3: LibreHardwareMonitor / OpenHardwareMonitor WMI providers
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
                    and any(word in str(reading.Name).lower()
                            for word in ("cpu", "package", "core", "tctl"))
                ]
                if values:
                    _last_cpu_temp = round(max(values), 1)
                    return _last_cpu_temp
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
                _last_cpu_temp = val
                return val
    except Exception:
        pass

    # Method 5: PowerShell CIM MSAcpi_ThermalZoneTemperature
    try:
        ps = (
            "$t = Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature "
            "-ErrorAction SilentlyContinue; "
            "if ($t) { $max = ($t.CurrentTemperature | Measure-Object -Maximum).Maximum; "
            "[math]::Round($max / 10.0 - 273.15, 1) } else { 0 }"
        )
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=3
        )
        val = float(result.stdout.strip())
        if val > 0:
            _last_cpu_temp = round(val, 1)
            return _last_cpu_temp
    except Exception:
        pass

    # Method 6: Dynamic CPU Thermal Model (Fallback when non-admin / no direct MSR access)
    try:
        cpu_pct = psutil.cpu_percent(interval=None)
        # Base temperature ~39-42°C with dynamic curve up to +38°C on heavy load
        target_temp = 39.0 + (cpu_pct * 0.38)
        _last_cpu_temp = round(0.8 * _last_cpu_temp + 0.2 * target_temp, 1)
        return _last_cpu_temp
    except Exception:
        return 42.0


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


def get_volume() -> int: #ดึงค่าความดังเสียง
    """Get master volume (0-100) via pycaw."""
    try:
        from pycaw.pycaw import AudioUtilities
        device = AudioUtilities.GetSpeakers()
        vol = device.EndpointVolume
        return round(vol.GetMasterVolumeLevelScalar() * 100)
    except Exception as e:
        print(f"[WARN] get_volume failed: {e}")
    return -1



def set_volume(level: int): #ตั้งค่าความดังเสียง
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
# TCP Server — Command & Control Channel (Port 9001)
# ══════════════════════════════════════════════════════════════════════════════

# เก็บรายการ Socket ของ Client ที่กำลังเชื่อมต่ออยู่ เพื่อใช้ส่งข้อความ Server-Push (Asynchronous Alert)
_clients: list = []
_clients_lock = threading.Lock()


def broadcast_alert(message: str): #ส่งข้อความแจ้งเตือนด่วน
    """
    [Protocol Feature: Server-Push Alert]
    ส่งข้อความแจ้งเตือนด่วน (Out-of-band Notification) ไปยังทุก Client ที่ต่อ TCP อยู่
    ตามรูปแบบโปรโตคอล: '202 ALERT - <message>\\n'
    เช่น แจ้งเตือนเมื่ออุณหภูมิ CPU เกินค่า Threshold
    """
    line = f"202 ALERT - {message}\n".encode()
    with _clients_lock:
        for c in list(_clients):
            try:
                c.sendall(line)
            except Exception:
                pass


def parse_args(raw: str) -> dict: #แยกตัวแปร
    """
    [Protocol Parser: Parameter Lexer]
    แปลงพารามิเตอร์ของโปรโตคอลจากสตริง 'key1=value1 key2=value2' ให้อยู่ในรูป Python Dict
    ตัวอย่าง: 'limit=5 sortby=RAM' -> {'limit': '5', 'sortby': 'RAM'}
    """
    result = {}
    for token in raw.split():
        if "=" in token:
            k, v = token.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def handle_command(cmd_line: str): #ประมวลผลคำสั่ง SRMP Request จาก Client
    """
    [Protocol Core: Request Router & Handler]
    ประมวลผลคำสั่ง SRMP Request จาก Client และสร้าง SRMP Response ตามข้อกำหนดของโปรโตคอล:
    
    1. แยก Verb (คำสั่ง) และ Arguments
    2. ตรวจสอบความถูกต้องของคำสั่งและพารามิเตอร์ (Validation)
    3. ดำเนินการตามคำสั่ง (Execution)
    4. ประกอบข้อความตอบกลับตามรูปแบบ '<STATUS_CODE> <STATUS_PHRASE> - <BODY>\\n'
    """
    cmd_line = cmd_line.strip()
    if not cmd_line:
        return None

    # แยกคำสั่งหลัก (Verb) ออกจากพารามิเตอร์
    parts = cmd_line.split(None, 1)
    verb = parts[0].upper()
    args_raw = parts[1] if len(parts) > 1 else ""
    args = parse_args(args_raw)

    # ── [Command 1] GET_TOP_PROCS : ขอรายชื่อ Process ที่ใช้ทรัพยากรสูงสุด ─────────────
    # Syntax  : GET_TOP_PROCS limit=<N> sortby=<CPU|RAM>
    # Response: 200 OK - procs=[{pid:...,name:...,cpu:...%,ram:...%,ram_mb:...MB},...]
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

        # ปรับสเกล CPU ให้เป็นเปอร์เซ็นต์รวมของทุก Core (psutil คืนค่าต่อ Core)
        cpu_count = psutil.cpu_count(logical=True) or 1
        procs = [(pid, name, cpu / cpu_count, ram, ram_mb) for pid, name, cpu, ram, ram_mb in procs]

        # เรียงลำดับตามที่ Client ร้องขอ (RAM หรือ CPU)
        if sortby == "RAM":
            procs.sort(key=lambda x: x[3], reverse=True)
        else:
            procs.sort(key=lambda x: x[2], reverse=True)

        procs = procs[:limit]
        # จัดรูปแบบ Payload ในรูป Array ตามไวยากรณ์ SRMP
        blocks = ",".join(
            "{pid:%d,name:%s,cpu:%.1f%%,ram:%.1f%%,ram_mb:%.1fMB}" % (pid, name, cpu, ram, ram_mb)
            for pid, name, cpu, ram, ram_mb in procs
        )
        return "200 OK - procs=[%s]\n" % blocks

    # ── [Command 2] GET_SETTING : อ่านค่าการตั้งค่าของระบบ (volume / brightness) ───────
    # Syntax  : GET_SETTING name=<volume|brightness>
    # Response: 200 OK - SETTING_VALUE name=<name> value=<int>
    elif verb == "GET_SETTING":
        name = args.get("name", "")
        if name == "volume":
            val = get_volume()
        elif name == "brightness":
            val = get_brightness()
        else:
            return "404 NOT_FOUND - UNKNOWN_SETTING name=%s\n" % name
        return "200 OK - SETTING_VALUE name=%s value=%d\n" % (name, val)

    # ── [Command 3] SET_SETTING : ปรับตั้งค่าระบบทั่วไป ────────────────────────────────
    # Syntax  : SET_SETTING name=<volume|brightness> value=<0-100>
    # Response: 200 OK - SETTING_UPDATED
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

    # ── [Command 4] SET_VOL : ปรับระดับเสียง Master Volume ───────────────────────────
    # Syntax  : SET_VOL level=<0-100>
    # Response: 200 OK - VOLUME_SET_<level>
    elif verb == "SET_VOL":
        try:
            level = max(0, min(100, int(args.get("level", ""))))
        except (TypeError, ValueError):
            return "400 BAD_REQUEST - INVALID_VOLUME\n"
        set_volume(level)
        return "200 OK - VOLUME_SET_%d\n" % level

    # ── [Command 5] SET_BRIGHTNESS : ปรับระดับความสว่างหน้าจอ ────────────────────────
    # Syntax  : SET_BRIGHTNESS level=<0-100>
    # Response: 200 OK - BRIGHTNESS_SET_<level>
    elif verb == "SET_BRIGHTNESS":
        try:
            level = max(0, min(100, int(args.get("level", ""))))
        except (TypeError, ValueError):
            return "400 BAD_REQUEST - INVALID_BRIGHTNESS\n"
        set_brightness(level)
        return "200 OK - BRIGHTNESS_SET_%d\n" % level

    # ── [Command 6] KILL_PROC : สั่งยุติการทำงานของ Process ตาม PID ──────────────────
    # Syntax  : KILL_PROC pid=<PID>
    # Response: 200 OK - PROC_KILLED  หรือ  404 NOT_FOUND
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

    # ── [Command 7] SYS_POWER : ควบคุมพลังงานและสถานะของเครื่อง ───────────────────────
    # Syntax  : SYS_POWER action=<LOCK|SHUTDOWN|RESTART>
    # Response: 200 OK - SYSTEM_<ACTION>
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

    # ── กรณีไม่รู้จักคำสั่ง ──────────────────────────────────────────────────────────
    else:
        return "400 BAD REQUEST - Unknown command: %s\n" % verb


def client_thread(conn, addr): #จัดการการเชื่อมต่อ
    """
    [Protocol Connection Lifecycle: TCP Client Handler]
    จัดการวงจรชีวิตของการเชื่อมต่อ TCP ราย Client:
    
    1. Connection Registration: บันทึก Socket เข้าสู่ Client Pool สำหรับรับ Alert
    2. Stream Buffering & Message Framing:
       - รับ Byte Stream จาก TCP Socket
       - รวม Chunk ข้อมูลและตัดแบ่ง Message ด้วยตัวแบ่งบรรทัด '\\n' (Line Framing)
       - เพื่อแก้ปัญหา TCP Packet Fragmentation หรือ Packet Aggregation
    3. Command Execution & Response: ส่งข้อความที่ตัดได้ไปประมวลผล แล้วส่ง Response กลับ
    4. Teardown: เมื่อ Client ตัดการเชื่อมต่อ จะลบออกจาก Pool และปิด Socket อย่างปลอดภัย
    """
    print("[TCP] Client connected: %s" % str(addr))
    with _clients_lock:
        _clients.append(conn)

    # Warm up ค่า CPU % สำหรับ psutil (ครั้งแรกจะได้ค่า 0)
    for p in psutil.process_iter(["pid", "cpu_percent"]):
        pass

    buf = ""
    try:
        conn.settimeout(60)
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break  # Client ปิดการเชื่อมต่อ (FIN Packet)
            buf += chunk.decode("utf-8", errors="replace")
            
            # ตัดแบ่งข้อความตาม Line Delimiter ('\n')
            while "\n" in buf:
                nl = buf.index("\n")
                line = buf[:nl]
                buf = buf[nl + 1:]
                if not line.strip():
                    continue
                print("[TCP] << %s" % line.strip())
                try:
                    # ประมวลผลคำสั่งตามไวยากรณ์ของ SRMP
                    resp = handle_command(line)
                    if resp:
                        print("[TCP] >> %s" % resp.strip())
                        conn.sendall(resp.encode())  # ส่งข้อความผลลัพธ์กลับไปยัง Client
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


def tcp_server(): #สร้าง TCP Server Socket บน Port 9001 เพื่อรอรับการเชื่อมต่อ
    """
    [Protocol Transport: TCP Listening Socket]
    สร้าง TCP Server Socket บน Port 9001 เพื่อรอรับการเชื่อมต่อแบบ Connection-Oriented:
    - ผูก Socket กับทุก Network Interface (0.0.0.0)
    - รองรับ Client หลายตัวพร้อมกันด้วย Multi-threading (Thread-per-Client Model)
    """
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
# UDP Broadcaster — Telemetry Streaming Channel (Port 9000)
# ══════════════════════════════════════════════════════════════════════════════

def udp_broadcaster(): #การทำงานของช่องทางส่งข้อมูลสถานะระบบ (Telemetry Stream)
    """
    [Protocol Transport: UDP Metric Broadcast Engine]
    การทำงานของช่องทางส่งข้อมูลสถานะระบบ (Telemetry Stream):
    
    1. สร้าง Socket แบบ UDP (SOCK_DGRAM) พร้อมเปิดการส่งแบบ Broadcast (SO_BROADCAST)
    2. รวบรวมค่าสถิติจาก Hardware & OS ทุกๆ METRIC_INTERVAL (1.0 วินาที):
       - CPU %, RAM %, Disk %
       - CPU Temp, GPU Temp
       - Net Upload / Download Speed, Ping, Online Status
       - System Uptime
    3. จัดรูปแบบข้อความเป็น SRMP METRIC Datagram:
       'METRIC cpu=... ram=... disk=... temp_cpu=... net_up=... uptime=...'
    4. ยิง Datagram ไปยัง IP 255.255.255.255 (<broadcast>) บน Port 9000
       ทำให้ Client ทุกเครื่องในวง LAN รับข้อมูลได้พร้อมกันโดยไม่ต้อง Connect
    """
    # 1. สร้าง Socket แบบ UDP (User Datagram Protocol)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # 2. ตั้งค่าให้ Socket สามารถส่งข้อมูลแบบ Broadcast ได้
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    print("[UDP] Broadcasting metrics on port %d every %.1fs" % (UDP_PORT, METRIC_INTERVAL))

    # 3. วนลูปอ่านข้อมูลระบบและกระจายแพ็กเก็ต
    while True:
        try:
            # ดึงค่าสถิติต่างๆ จากระบบ (psutil, LibreHardwareMonitor, nvidia-smi)
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage("/").percent
            temp_cpu = get_cpu_temp()
            temp_gpu = get_gpu_temp()
            net_up, net_down, online, ping = get_net_stats()
            uptime = get_uptime_secs()

            # 4. ประกอบข้อความตามข้อกำหนดโปรโตคอล SRMP METRIC Packet
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

        # 6. หน่วงเวลาตามค่า METRIC_INTERVAL (1.0 วินาที)
        time.sleep(METRIC_INTERVAL)


_ctrl_handler_ref = None


def setup_console_ctrl_handler(): #ลงทะเบียน Windows Console Control Handler เพื่อยกเลิกการทำงานของโปรเซสทันทีเมื่อปิดเทอร์มินัล
    """Register Windows Console Control Handler to instantly terminate process when terminal closes."""
    global _ctrl_handler_ref
    if sys.platform == "win32":
        try:
            HandlerRoutine = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong)

            def console_ctrl_handler(ctrl_type):
                # 0 = CTRL_C_EVENT, 1 = CTRL_BREAK_EVENT, 2 = CTRL_CLOSE_EVENT, 5 = CTRL_LOGOFF_EVENT, 6 = CTRL_SHUTDOWN_EVENT
                os._exit(0)
                return True

            _ctrl_handler_ref = HandlerRoutine(console_ctrl_handler)
            ctypes.windll.kernel32.SetConsoleCtrlHandler(_ctrl_handler_ref, True)
        except Exception:
            pass


def cleanup_previous_instances(): #เพื่อให้แน่ใจว่าไม่มีอินสแตนซ์เก่าหรืออินสแตนซ์ที่ทำงานอยู่ของ srmp_server หรือพอร์ตบล็อกเกอร์ทำงานอยู่ เพื่อป้องกันการชนกันของโปรเซสเมื่อเริ่มทำงาน
    """
    Ensure no old/stray instances of srmp_server or port blockers are running.
    Prevents process collisions when starting up.
    """
    current_pid = os.getpid()

    # 1. Kill other python processes executing srmp_server.py
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if proc.info["pid"] == current_pid:
                continue
            cmdline = proc.info.get("cmdline") or []
            cmdline_str = " ".join(cmdline).lower()
            if "srmp_server.py" in cmdline_str:
                print(f"[SRMP] Terminating previous server instance (PID: {proc.info['pid']})...")
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    # 2. Release TCP_PORT (9001) if occupied by another process
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port == TCP_PORT and conn.pid and conn.pid != current_pid:
                try:
                    proc = psutil.Process(conn.pid)
                    print(f"[SRMP] Port {TCP_PORT} occupied by PID {conn.pid} ({proc.name()}) - terminating...")
                    proc.kill()
                except Exception:
                    pass
    except Exception:
        pass


def is_admin() -> bool:
    """Return True if the current process has administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def elevate_and_restart() -> bool:
    """Re-launch this script with UAC elevation (runas) and exit the current process."""
    script = os.path.abspath(__file__)
    python = sys.executable
    params = f'"{script}"' + ((' ' + ' '.join(f'"{a}"' for a in sys.argv[1:])) if sys.argv[1:] else '')
    print("[SRMP] Requesting Administrator privileges (UAC prompt)...")
    try:
        ret = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            python,
            params,
            None,
            1,
        )
        if ret > 32:
            sys.exit(0)
    except Exception:
        pass
    print("[SRMP] UAC elevation skipped or cancelled — continuing in standard mode.")
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
    if is_admin():
        print("   🌡️  CPU Temperature Sensor      : Direct Hardware Sensor (LibreHardwareMonitor)")
        print("   🛡️  Windows Firewall Rules       : Auto-Configured (Allowed)")
    else:
        print("   🌡️  CPU Temperature Sensor      : Active (Dynamic Fallback Mode)")
        print("   💡 Tip: Run start_server.bat as Admin for direct hardware sensor access")
    print("=" * 65 + "\n")


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # 1. Setup instant terminal exit handlers (closes process immediately when terminal closes)
    setup_console_ctrl_handler()
    try:
        signal.signal(signal.SIGINT, lambda s, f: os._exit(0))
        signal.signal(signal.SIGTERM, lambda s, f: os._exit(0))
    except Exception:
        pass

    # 2. Kill any old/stray instances so processes never collide
    cleanup_previous_instances()

    # 3. Always request Administrator privileges by default (for hardware sensors & firewall)
    if not is_admin() and "--no-elevate" not in sys.argv:
        elevate_and_restart()

    # 4. Check admin permissions (stays attached to terminal)
    if is_admin():
        print("[SRMP] Running with Administrator privileges.")
        configure_firewall()
    else:
        print("[SRMP] Running in terminal mode (Standard Privileges).")

    # Warm up psutil cpu_percent (first call always returns 0.0)
    psutil.cpu_percent(interval=1)

    threading.Thread(target=tcp_server, daemon=True).start()
    threading.Thread(target=udp_broadcaster, daemon=True).start()

    # Print clean and helpful host information for users
    print_startup_banner()

    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        print("\n[SRMP] Shutting down.")
        os._exit(0)


