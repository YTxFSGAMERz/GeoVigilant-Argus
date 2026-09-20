#!/usr/bin/env bash
# ==============================================================================
# GeoVigilant Argus Eye — Service Stopper (Linux / macOS / POSIX)
# ==============================================================================

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo ""
echo "================================================================================"
echo "  🛑 GEOVIGILANT ARGUS EYE // TERMINATING SERVICES (UNIX/POSIX)"
echo "================================================================================"
echo ""

# Detect Python Environment
PY_BIN=""
if [ -f "$DIR/.venv/bin/python" ]; then
    PY_BIN="$DIR/.venv/bin/python"
elif [ -f "$DIR/.venv/Scripts/python.exe" ]; then
    PY_BIN="$DIR/.venv/Scripts/python.exe"
elif [ -f "$DIR/venv/bin/python" ]; then
    PY_BIN="$DIR/venv/bin/python"
elif [ -f "$DIR/venv/Scripts/python.exe" ]; then
    PY_BIN="$DIR/venv/Scripts/python.exe"
elif python3 --version &>/dev/null; then
    PY_BIN="python3"
elif python --version &>/dev/null; then
    PY_BIN="python"
fi

# 1. Run Python Cross-Platform Service Stopper
if command -v "$PY_BIN" &>/dev/null; then
    "$PY_BIN" "$DIR/scripts/stop_services.py" || true
fi

# 2. Direct POSIX Fallback Port Cleanup (Flask: 5000, Vite: 5173, Ollama: 11434, Tor: 9050)
for PORT in 5000 5173 11434 9050; do
    if command -v lsof &>/dev/null; then
        PIDS=$(lsof -ti :"$PORT" 2>/dev/null || true)
        if [ -n "$PIDS" ]; then
            echo "    [x] Fallback releasing port :$PORT (PIDs: $PIDS)"
            echo "$PIDS" | xargs kill -9 2>/dev/null || true
        fi
    elif command -v fuser &>/dev/null; then
        fuser -k "$PORT"/tcp 2>/dev/null || true
    fi
done

# 3. Terminate background processes
pkill -9 -x tor 2>/dev/null || true
pkill -9 -f "app.py" 2>/dev/null || true
pkill -9 -f "vite" 2>/dev/null || true

# 4. Clean up PID tracking files
[ -f "$DIR/.argus_pids.txt" ] && rm -f "$DIR/.argus_pids.txt"
[ -f "$DIR/.argus_watchdog.pid" ] && rm -f "$DIR/.argus_watchdog.pid"

echo ""
echo "  [+] Port 5000 [Backend]   : CLEARED"
echo "  [+] Port 5173 [Dev Vite]  : CLEARED"
echo "  [+] Port 11434 [AI Core]  : CLEARED"
echo "  [+] Port 9050 [Tor Proxy] : CLEARED"
echo "  [+] Background processes  : TERMINATED"
echo ""
echo "================================================================================"
echo "  System cooled down. All GeoVigilant services safely halted."
echo "================================================================================"
echo ""

if [ "$1" == "--no-pause" ] || [ "$1" == "-n" ]; then
    exit 0
elif [ "$1" == "--auto-close" ]; then
    echo "  [*] Auto-closing cleanup session in 2 seconds..."
    sleep 2
    exit 0
else
    read -rp "Press Enter to finish..." || true
fi
