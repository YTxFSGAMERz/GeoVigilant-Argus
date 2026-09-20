"""
GeoVigilant Argus Eye — Terminal Lifecycle Watchdog.
Cross-platform: Windows, Linux, and macOS.

Monitors the PID of the start.bat or start.sh console window.
If the user closes the window (e.g. clicks the 'X' / cross button) or the launcher exits,
this watchdog automatically triggers stop.bat (or stop.sh) to terminate all backend servers, Vite,
Tor, and Ollama processes, preventing orphaned port conflicts.
"""

import os
import sys
import time
import signal
import subprocess

try:
    import psutil
except ImportError:
    psutil = None

def get_root_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def spawn_daemon(launcher_pid):
    """Spawns this script as a fully detached background process."""
    root_dir = get_root_dir()
    script_path = os.path.abspath(__file__)
    watchdog_pid_file = os.path.join(root_dir, ".argus_watchdog.pid")

    # If an old watchdog PID exists and is running, terminate it first
    if os.path.exists(watchdog_pid_file):
        try:
            with open(watchdog_pid_file, "r") as f:
                old_wpid = int(f.read().strip())
                if psutil and psutil.pid_exists(old_wpid):
                    psutil.Process(old_wpid).kill()
                elif sys.platform != "win32":
                    try:
                        os.kill(old_wpid, signal.SIGKILL)
                    except Exception:
                        pass
        except Exception:
            pass

    if sys.platform == "win32":
        # Windows: Locate pythonw.exe if present
        py_dir = os.path.dirname(sys.executable)
        pyw_candidate = os.path.join(py_dir, "pythonw.exe")
        py_exe = pyw_candidate if os.path.exists(pyw_candidate) else sys.executable

        DETACHED_FLAGS = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        if not py_exe.lower().endswith("pythonw.exe"):
            DETACHED_FLAGS |= 0x08000000  # CREATE_NO_WINDOW

        proc = subprocess.Popen(
            [py_exe, script_path, str(launcher_pid)],
            cwd=root_dir,
            creationflags=DETACHED_FLAGS,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL
        )
    else:
        # Linux / macOS: Detached daemon via start_new_session
        py_exe = sys.executable
        proc = subprocess.Popen(
            [py_exe, script_path, str(launcher_pid)],
            cwd=root_dir,
            start_new_session=True,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL
        )

    return proc.pid

def monitor(launcher_pid):
    """Monitors the launcher process until it dies, then runs stop script."""
    root_dir = get_root_dir()
    stop_bat = os.path.join(root_dir, "stop.bat")
    stop_sh = os.path.join(root_dir, "stop.sh")
    watchdog_pid_file = os.path.join(root_dir, ".argus_watchdog.pid")

    # Record watchdog PID for lifecycle management
    try:
        with open(watchdog_pid_file, "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass

    launcher_proc = None
    if psutil:
        try:
            launcher_proc = psutil.Process(launcher_pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            launcher_proc = None

    # Poll launcher process status
    if launcher_proc:
        while True:
            try:
                if not launcher_proc.is_running() or launcher_proc.status() == psutil.STATUS_ZOMBIE:
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            except Exception:
                if not psutil.pid_exists(launcher_pid):
                    break
            time.sleep(0.4)
    else:
        # Fallback polling without psutil
        while True:
            if sys.platform == "win32":
                try:
                    out = subprocess.check_output(f'tasklist /FI "PID eq {launcher_pid}"', shell=True, text=True)
                    if str(launcher_pid) not in out:
                        break
                except Exception:
                    break
            else:
                try:
                    os.kill(launcher_pid, 0)
                except OSError:
                    break
            time.sleep(0.4)

    # Launcher terminal is closed!
    # Check if this watchdog was legitimately triggered (i.e. not killed/overwritten by manual stop)
    should_stop = True
    if os.path.exists(watchdog_pid_file):
        try:
            with open(watchdog_pid_file, "r") as f:
                saved_pid = f.read().strip()
                if saved_pid and int(saved_pid) != os.getpid():
                    should_stop = False
        except Exception:
            pass
    else:
        should_stop = False

    if should_stop:
        if sys.platform == "win32" and os.path.exists(stop_bat):
            os.system(f'start "Argus_AutoShutdown" cmd /c ""{stop_bat}" --auto-close"')
        elif os.path.exists(stop_sh):
            subprocess.run(["bash", stop_sh, "--no-pause"], cwd=root_dir)

    # Clean up watchdog PID file
    try:
        if os.path.exists(watchdog_pid_file):
            with open(watchdog_pid_file, "r") as f:
                if f.read().strip() == str(os.getpid()):
                    os.remove(watchdog_pid_file)
    except Exception:
        pass

def main():
    if len(sys.argv) < 2:
        sys.exit(1)

    arg = sys.argv[1]
    if arg == "--spawn":
        try:
            if psutil:
                parent_pid = psutil.Process().ppid()
            else:
                parent_pid = os.getppid()
            spawn_daemon(parent_pid)
        except Exception:
            pass
        sys.exit(0)

    try:
        launcher_pid = int(arg)
    except ValueError:
        sys.exit(1)

    monitor(launcher_pid)

if __name__ == "__main__":
    main()
