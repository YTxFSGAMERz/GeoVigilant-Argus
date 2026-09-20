"""
GeoVigilant Argus Eye - Service Stopper (Cross-Platform: Windows, Linux, macOS)
Safely stops Python app.py, Node Vite development processes, Tor, and Ollama.
"""
import os
import sys
import signal
import subprocess

try:
    import psutil
except ImportError:
    psutil = None

def kill_process_on_port(port):
    killed = False

    # Method 1: Cross-platform psutil
    if psutil:
        try:
            for conn in psutil.net_connections(kind='inet'):
                if conn.status == psutil.CONN_LISTEN and conn.laddr and conn.laddr.port == port:
                    if conn.pid and conn.pid != os.getpid():
                        try:
                            p = psutil.Process(conn.pid)
                            proc_name = p.name()
                            p.kill()
                            print(f"    [x] Terminated process ({proc_name} PID {conn.pid}) listening on port {port}")
                            killed = True
                        except Exception:
                            pass
        except Exception:
            pass

    # Method 2: Platform-specific fallbacks
    if sys.platform == "win32":
        try:
            out = subprocess.check_output(f'netstat -ano | findstr ":{port}"', shell=True, text=True, stderr=subprocess.DEVNULL)
            pids = set()
            for line in out.strip().splitlines():
                if "LISTENING" in line:
                    parts = line.strip().split()
                    if parts:
                        pid = parts[-1]
                        if pid.isdigit() and int(pid) != os.getpid():
                            pids.add(int(pid))
            for pid in pids:
                try:
                    subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    print(f"    [x] Terminated process (PID {pid}) listening on port {port}")
                    killed = True
                except Exception:
                    pass
        except Exception:
            pass
    else:
        # Linux / macOS fallback using lsof or fuser
        try:
            cmd = f"lsof -ti :{port} 2>/dev/null | xargs kill -9 2>/dev/null"
            subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            cmd_fuser = f"fuser -k {port}/tcp 2>/dev/null"
            subprocess.run(cmd_fuser, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            killed = True
        except Exception:
            pass

    return killed

def kill_by_commandline():
    # Method 1: psutil commandline inspect
    if psutil:
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = " ".join(proc.info['cmdline'] or [])
                    if "app.py" in cmdline and proc.pid != os.getpid():
                        proc.kill()
                    elif "vite" in cmdline and proc.pid != os.getpid():
                        proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass

    # Method 2: Platform-specific fallbacks
    if sys.platform == "win32":
        try:
            ps_cmd = 'Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like "*app.py*" -and $_.ProcessId -ne ' + str(os.getpid()) + ' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }'
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
    else:
        try:
            subprocess.run(["pkill", "-9", "-f", "app.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

def main():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 60)
    print("  🛑 TERMINATING GEOVIGILANT ARGUS EYE SERVICES...")
    print("=" * 60)

    # 1. Clean up known PID file if present
    pid_file = os.path.join(root_dir, ".argus_pids.txt")
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                for line in f:
                    pid = line.strip()
                    if pid.isdigit() and int(pid) != os.getpid():
                        if sys.platform == "win32":
                            subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        else:
                            try:
                                os.kill(int(pid), signal.SIGKILL)
                            except Exception:
                                pass
            os.remove(pid_file)
            print("    [x] Cleaned up saved session PIDs.")
        except Exception:
            pass

    # Disarm / terminate watchdog daemon so it doesn't trigger a duplicate stop loop
    watchdog_pid_file = os.path.join(root_dir, ".argus_watchdog.pid")
    if os.path.exists(watchdog_pid_file):
        try:
            with open(watchdog_pid_file, "r") as f:
                wpid = f.read().strip()
                if wpid.isdigit() and int(wpid) != os.getpid():
                    if sys.platform == "win32":
                        subprocess.run(f"taskkill /F /PID {wpid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    else:
                        try:
                            os.kill(int(wpid), signal.SIGKILL)
                        except Exception:
                            pass
            os.remove(watchdog_pid_file)
            print("    [x] Disarmed terminal close watchdog.")
        except Exception:
            pass

    # 2. Release Port 5000 (Flask Backend)
    k5000 = kill_process_on_port(5000)
    
    # 3. Release Port 5173 (Vite Dev Server)
    k5173 = kill_process_on_port(5173)

    # 4. Release Port 9050 (Tor SOCKS5 Proxy)
    k9050 = kill_process_on_port(9050)
    if sys.platform == "win32":
        subprocess.run("taskkill /F /IM tor.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run(["pkill", "-9", "-x", "tor"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 5. Command line match for app.py
    kill_by_commandline()

    # 6. Windows-only: Terminate labeled server console windows (do not kill current stopper console)
    if sys.platform == "win32":
        for target in [
            "GeoVigilant_Argus_Backend*",
            "GeoVigilant_Argus_Vite*",
            "GeoVigilant_Argus_Ollama*",
            "GeoVigilant_Argus_Tor*",
            "GeoVigilant_Argus_Watchdog*"
        ]:
            subprocess.run(f'taskkill /FI "WINDOWTITLE eq {target}" /F /T', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print("\n[+] All GeoVigilant Argus services stopped successfully.")
    print("=" * 60)

if __name__ == "__main__":
    main()
