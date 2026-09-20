#!/usr/bin/env bash
# ==============================================================================
# GeoVigilant Argus Eye — Tactical Mission Launcher (Linux / macOS / POSIX)
# Classification: TOP SECRET // SI-TK // NOFORN
# ==============================================================================

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# ==============================================================================
# Terminal Signal Trap (Auto-triggers stop.sh on Window Close or Signal)
# SIGHUP is sent when the terminal emulator window is closed ([X] cross button)
# ==============================================================================
CLEANED_UP=0
cleanup() {
    if [ "$CLEANED_UP" -eq 1 ]; then
        return
    fi
    CLEANED_UP=1
    trap - EXIT SIGHUP SIGINT SIGTERM
    echo ""
    echo "================================================================================"
    echo "  🛑 TERMINAL CLOSURE DETECTED — INITIATING AUTOMATIC SHUTDOWN"
    echo "================================================================================"
    if [ -f "$DIR/stop.sh" ]; then
        bash "$DIR/stop.sh" --no-pause 2>/dev/null || true
    fi
}
trap cleanup SIGHUP SIGINT SIGTERM

# ==============================================================================
# 1. Python & Virtual Environment Auto-Detection
# ==============================================================================
PY_BIN=""
if [ -f "$DIR/.venv/bin/python" ]; then
    PY_BIN="$DIR/.venv/bin/python"
    source "$DIR/.venv/bin/activate" 2>/dev/null || true
elif [ -f "$DIR/.venv/Scripts/python.exe" ]; then
    PY_BIN="$DIR/.venv/Scripts/python.exe"
    source "$DIR/.venv/Scripts/activate" 2>/dev/null || true
elif [ -f "$DIR/venv/bin/python" ]; then
    PY_BIN="$DIR/venv/bin/python"
    source "$DIR/venv/bin/activate" 2>/dev/null || true
elif [ -f "$DIR/venv/Scripts/python.exe" ]; then
    PY_BIN="$DIR/venv/Scripts/python.exe"
    source "$DIR/venv/Scripts/activate" 2>/dev/null || true
elif python3 --version &>/dev/null; then
    PY_BIN="python3"
elif python --version &>/dev/null; then
    PY_BIN="python"
else
    echo ""
    echo "================================================================================"
    echo "  [!] CRITICAL ERROR: Python is not detected in your PATH."
    echo "      Please install Python 3.10+ (python3) to proceed."
    echo "================================================================================"
    echo ""
    exit 1
fi

# Quick exit for help or stop before arming watchdog
if [ "$1" == "--help" ] || [ "$1" == "-h" ] || [ "$1" == "-?" ]; then
    SHOW_HELP_ONLY=1
elif [ "$1" == "--stop" ] || [ "$1" == "--end" ] || [ "$1" == "-k" ] || [ "$1" == "8" ]; then
    trap - EXIT SIGHUP SIGINT SIGTERM
    exec "$DIR/stop.sh" "$@"
fi

# Arm background watchdog process for dual-layer window closure protection
if [ -z "$SHOW_HELP_ONLY" ]; then
    "$PY_BIN" "$DIR/scripts/watchdog.py" --spawn >/dev/null 2>&1 || true
fi

# ==============================================================================
# 2. Requirements & Resources Pre-Flight Check (Auto-Installs Missing Items)
# ==============================================================================
if [ -z "$SHOW_HELP_ONLY" ]; then
    "$PY_BIN" "$DIR/scripts/verify_and_install_resources.py" || {
        echo ""
        echo "[!] WARNING: Pre-flight check encountered non-fatal notices."
        echo ""
    }
fi

# ==============================================================================
# Helper Functions
# ==============================================================================
is_port_listening() {
    local port="$1"
    if command -v lsof &>/dev/null; then
        lsof -i :"$port" -sTCP:LISTEN &>/dev/null
    elif command -v nc &>/dev/null; then
        nc -z 127.0.0.1 "$port" &>/dev/null
    else
        (exec 3<>/dev/tcp/127.0.0.1/"$port") &>/dev/null
    fi
}

wait_for_port() {
    local port="$1"
    local max_tries=10
    local current_try=0
    while [ "$current_try" -lt "$max_tries" ]; do
        current_try=$((current_try + 1))
        if is_port_listening "$port"; then
            echo "  [+] Service on port $port confirmed READY."
            return 0
        fi
        sleep 1
    done
    echo "  [*] Service initialization taking longer than expected. Continuing..."
}

start_ollama() {
    if is_port_listening 11434; then
        echo "  [+] Ollama AI Core : ACTIVE [:11434 // Cloud Bridge Ready]"
        return 0
    fi
    if command -v ollama &>/dev/null; then
        echo "[*] Starting Ollama Cloud AI Backend Daemon (:11434)..."
        OLLAMA_KEEP_ALIVE=-1 OLLAMA_FLASH_ATTENTION=1 ollama serve >/dev/null 2>&1 &
        echo $! >> "$DIR/.argus_pids.txt"
        echo "  [+] Ollama Daemon  : SPAWNED [Persistent VRAM / Flash Attention Active]"
        sleep 2
    else
        echo "  [*] Ollama Core    : Not found in PATH (Optional for local LLM inference)"
    fi
}

start_tor() {
    if is_port_listening 9050; then
        echo "  [+] Tor Onion Daemon : ACTIVE [:9050 SOCKS5 // :9051 Control]"
        return 0
    fi
    if command -v tor &>/dev/null; then
        echo "[*] Starting Tor SOCKS5 Onion Daemon (:9050)..."
        mkdir -p "$DIR/data/tor" 2>/dev/null || true
        if [ -f "$DIR/torrc" ]; then
            tor -f "$DIR/torrc" >/dev/null 2>&1 &
        else
            tor >/dev/null 2>&1 &
        fi
        echo $! >> "$DIR/.argus_pids.txt"
        echo "  [+] Tor Onion Daemon : SPAWNED [SOCKS5 Port 9050]"
        sleep 2
    else
        echo "  [*] Tor Onion Daemon : Not found in PATH (Optional for onion routing)"
    fi
}

verify_node() {
    if ! command -v npm &>/dev/null; then
        echo ""
        echo "================================================================================"
        echo "  [*] NOTICE: Node.js and npm were not detected in system PATH."
        echo "      Vite HMR Dev server requires Node.js 18+."
        echo "  [*] Auto-routing to STANDALONE FLASK MODE [Option 3]..."
        echo "================================================================================"
        echo ""
        sleep 2
        launch_standalone
        exit 0
    fi
    if [ ! -d "$DIR/node_modules" ]; then
        echo "[*] node_modules not found. Running npm install..."
        npm install
    fi
}

check_ports() {
    if is_port_listening 5000 || is_port_listening 5173; then
        echo ""
        echo "[*] ALERT: Port 5000 or 5173 is already active."
        if [ -n "$IS_CLI" ]; then
            if [ "$2" == "--force" ]; then
                echo "[*] Force restart requested. Halting existing instances..."
                "$DIR/stop.sh" --no-pause
                sleep 2
            else
                echo "[*] Preserving running server instances..."
                SKIP_SERVER_LAUNCH=1
            fi
        else
            read -rp "Restart servers and terminate existing instances? [Y/N] [Default: Y]: " RESTART_SRV
            RESTART_SRV="${RESTART_SRV:-Y}"
            if [[ "$RESTART_SRV" =~ ^[Yy]$ ]]; then
                echo "[*] Stopping previous instances..."
                "$DIR/stop.sh" --no-pause
                sleep 2
            else
                echo "[*] Preserving running server instances..."
                SKIP_SERVER_LAUNCH=1
            fi
        fi
    fi
}

post_launch_menu() {
    trap cleanup EXIT SIGHUP SIGINT SIGTERM
    if [ -n "$IS_CLI" ]; then
        wait
        exit 0
    fi

    echo ""
    echo "================================================================================"
    echo "  [!] TACTICAL MISSION CONTROL STATUS: ACTIVE"
    echo "      * Keep this terminal window open while GeoVigilant Argus is active."
    echo "      * Closing this window ([X] / SIGHUP) will automatically launch stop.sh"
    echo "        and safely terminate all backend, Vite, AI, and Tor services."
    echo "================================================================================"
    echo ""
    echo "  Navigation:"
    echo "    [M] Return to Tactical Menu (Live Telemetry & Diagnostics)"
    echo "    [S] Stop all services now and exit"
    echo ""
    read -rp "Select option [M/S] [Press Enter for Menu]: " POST_ACTION
    POST_ACTION="${POST_ACTION:-M}"
    if [[ "$POST_ACTION" =~ ^[Ss]$ ]]; then
        trap - EXIT SIGHUP SIGINT SIGTERM
        exec "$DIR/stop.sh" --no-pause
    fi
    main_menu
}

# ==============================================================================
# Launch Operations
# ==============================================================================
launch_eco() {
    echo ""
    echo "================================================================================"
    echo "  ❄️  CONFIGURING SUMMER ECO DEV MODE (FLASK + VITE HMR // 30 FPS)"
    echo "================================================================================"
    verify_node
    export ARGUS_MODE="eco"
    check_ports
    start_ollama
    start_tor

    if [ -z "$SKIP_SERVER_LAUNCH" ]; then
        echo "[*] Starting GeoVigilant Flask Backend on Port 5000..."
        "$PY_BIN" app.py &
        FLASK_PID=$!
        echo "$FLASK_PID" >> "$DIR/.argus_pids.txt"

        echo "[*] Starting Vite Frontend Dev Server with HMR on Port 5173..."
        NODE_OPTIONS="--max-old-space-size=2048" npm run dev &
        VITE_PID=$!
        echo "$VITE_PID" >> "$DIR/.argus_pids.txt"

        wait_for_port 5000
        wait_for_port 5173
    fi

    echo ""
    echo "================================================================================"
    echo "  [OK] GEOVIGILANT ARGUS EYE ACTIVE IN FULL DEV + ECO MODE"
    echo "  * Frontend (Vite) : http://localhost:5173/ [Hot Reloading Active]"
    echo "  * Backend (Flask) : http://localhost:5000 [API Proxied]"
    echo "  * FPS Limit       : 30 FPS capped"
    echo "  * Stop Tool       : Run ./stop.sh or close this window"
    echo "================================================================================"
    post_launch_menu
}

launch_perf() {
    echo ""
    echo "================================================================================"
    echo "  ⚡  CONFIGURING PERFORMANCE DEV MODE (FLASK + VITE HMR // 60 FPS)"
    echo "================================================================================"
    verify_node
    export ARGUS_MODE="perf"
    check_ports
    start_ollama
    start_tor

    if [ -z "$SKIP_SERVER_LAUNCH" ]; then
        echo "[*] Starting GeoVigilant Flask Backend on Port 5000..."
        "$PY_BIN" app.py &
        FLASK_PID=$!
        echo "$FLASK_PID" >> "$DIR/.argus_pids.txt"

        echo "[*] Starting Vite Frontend Dev Server with HMR on Port 5173..."
        NODE_OPTIONS="--max-old-space-size=4096" npm run dev &
        VITE_PID=$!
        echo "$VITE_PID" >> "$DIR/.argus_pids.txt"

        wait_for_port 5000
        wait_for_port 5173
    fi

    echo ""
    echo "================================================================================"
    echo "  [OK] GEOVIGILANT ARGUS EYE ACTIVE IN FULL DEV + PERFORMANCE MODE"
    echo "  * Frontend (Vite) : http://localhost:5173/ [Hot Reloading Active]"
    echo "  * Backend (Flask) : http://localhost:5000 [API Proxied]"
    echo "  * FPS Limit       : 60 FPS full fidelity"
    echo "  * Stop Tool       : Run ./stop.sh or close this window"
    echo "================================================================================"
    post_launch_menu
}

launch_standalone() {
    echo ""
    echo "================================================================================"
    echo "  📦  CONFIGURING STANDALONE PRODUCTION MODE (FLASK ONLY // NO NODE.JS)"
    echo "================================================================================"
    export ARGUS_MODE="eco"
    check_ports
    start_ollama
    start_tor

    if [ -z "$SKIP_SERVER_LAUNCH" ]; then
        echo "[*] Starting GeoVigilant Flask Backend on Port 5000..."
        "$PY_BIN" app.py &
        FLASK_PID=$!
        echo "$FLASK_PID" >> "$DIR/.argus_pids.txt"

        wait_for_port 5000
    fi

    echo ""
    echo "================================================================================"
    echo "  [OK] STANDALONE BACKEND ACTIVE (LOWEST RAM)"
    echo "  * URL       : http://localhost:5000/"
    echo "  * Node/Vite : Disabled [Serving pre-compiled assets directly via Flask]"
    echo "  * FPS Limit : 30 FPS capped"
    echo "  * Stop Tool : Run ./stop.sh or close this window"
    echo "================================================================================"
    post_launch_menu
}

launch_ground() {
    echo ""
    echo "================================================================================"
    echo "  🗺️  CONFIGURING GROUNDVIEW 2D INTEL PROFILE"
    echo "================================================================================"
    verify_node
    export ARGUS_MODE="eco"
    check_ports
    start_ollama
    start_tor

    if [ -z "$SKIP_SERVER_LAUNCH" ]; then
        echo "[*] Starting GeoVigilant Flask Backend on Port 5000..."
        "$PY_BIN" app.py &
        FLASK_PID=$!
        echo "$FLASK_PID" >> "$DIR/.argus_pids.txt"

        echo "[*] Starting Vite Frontend Dev Server on Port 5173..."
        NODE_OPTIONS="--max-old-space-size=2048" npm run dev &
        VITE_PID=$!
        echo "$VITE_PID" >> "$DIR/.argus_pids.txt"

        wait_for_port 5000
        wait_for_port 5173
    fi

    echo ""
    echo "================================================================================"
    echo "  [OK] GROUNDVIEW 2D INTEL CONSOLE ACTIVE"
    echo "  * URL       : http://localhost:5173/ground"
    echo "  * Stop Tool : Run ./stop.sh or close this window"
    echo "================================================================================"
    post_launch_menu
}

# ==============================================================================
# Interactive Menu
# ==============================================================================
main_menu() {
    clear 2>/dev/null || true

    STAT_FLASK="[OFFLINE]"
    STAT_VITE="[OFFLINE]"
    STAT_OLLAMA="[OFFLINE]"
    STAT_TOR="[OFFLINE]"

    is_port_listening 5000 && STAT_FLASK="[ONLINE :5000]"
    is_port_listening 5173 && STAT_VITE="[ONLINE :5173]"
    is_port_listening 11434 && STAT_OLLAMA="[ONLINE :11434]"
    is_port_listening 9050 && STAT_TOR="[ONLINE :9050]"

    echo ""
    echo "================================================================================"
    echo "  [+] GEOVIGILANT ARGUS EYE // TACTICAL MISSION CONTROL (UNIX/POSIX)"
    echo "  // CLASSIFICATION: TOP SECRET // SI-TK // NOFORN"
    echo "  // MISSION CONTROL & THERMAL MANAGEMENT PROFILES"
    echo "================================================================================"
    echo ""
    echo "  LIVE SYSTEM TELEMETRY:"
    echo "    * Flask Backend   : $STAT_FLASK"
    echo "    * Vite Dev Server : $STAT_VITE"
    echo "    * Ollama AI Core  : $STAT_OLLAMA"
    echo "    * Tor Onion Proxy : $STAT_TOR"
    echo "    * Python Runtime  : $PY_BIN"
    echo "    * Close Watchdog  : [ACTIVE // Auto-Runs stop.sh on Window Close]"
    echo ""
    echo "  OPERATIONAL PROFILES:"
    echo ""
    echo "  [1] ❄️  SUMMER ECO DEV MODE      (FLASK + VITE HMR // 30 FPS)"
    echo "      - Full Dev Stack: Flask Backend (:5000) + Vite Dev Server (:5173)"
    echo "      - 30 FPS capped render loop, 2048MB Node heap buffer"
    echo "      - URL: http://localhost:5173/"
    echo ""
    echo "  [2] ⚡  PERFORMANCE DEV MODE     (FULL FIDELITY // 60 FPS)"
    echo "      - Full Dev Stack: Flask Backend (:5000) + Vite Dev Server (:5173)"
    echo "      - 60 FPS full render loop, 4096MB Node heap buffer"
    echo "      - URL: http://localhost:5173/"
    echo ""
    echo "  [3] 📦  STANDALONE FLASK ONLY    (DEFAULT // RECOMMENDED // ROOT URL)"
    echo "      - Starts Flask only (:5000) serving pre-compiled assets"
    echo "      - Zero Node.js overhead, ideal for low RAM"
    echo "      - URL: http://localhost:5000/"
    echo ""
    echo "  [4] 🗺️  GROUNDVIEW 2D INTEL      (LOWEST OVERHEAD)"
    echo "      - High-density tactical 2D vector intelligence & POI explorer"
    echo "      - URL: http://localhost:5173/ground"
    echo ""
    echo "  [5] 🛠️  BUILD PRODUCTION ASSETS  (Vite Rollup Bundler)"
    echo "      - Compiles and syncs latest frontend into static/js"
    echo ""
    echo "  [6] 🔄  RESTART ALL SERVICES     (Clean Cycle)"
    echo "      - Halts active instances, clears ports, and boots fresh stack"
    echo ""
    echo "  [7] 🔍  HARDWARE & GPU DIAGNOSTICS"
    echo "      - Tests PyTorch CUDA acceleration, ports, system thermals"
    echo ""
    echo "  [8] 🛑  STOP / END SERVICES"
    echo "      - Terminate all active GeoVigilant servers and free occupied ports"
    echo ""
    echo "  [9] 🧅  TOR ONION DAEMON CONTROL"
    echo "      - Start or verify local SOCKS5 proxy (:9050)"
    echo ""
    echo "  [I] 📦  VERIFY & INSTALL REQUIREMENTS / RESOURCES"
    echo "      - Validate Python packages, npm modules, .env vault, dataset resources"
    echo ""
    echo "  [D] 🛰️  DOWNLOAD FULL ARGUS DATASET (Optional // ~36.9 GB)"
    echo "      - Multi-threaded download of all 75,000+ surveillance images from Hugging Face"
    echo ""
    echo "  [0] 🚪  EXIT"
    echo ""
    echo "================================================================================"
    read -rp "Enter selection [1-9, I, D, or 0] [Press Enter for Default 3]: " CHOICE
    CHOICE="${CHOICE:-3}"

    case "$CHOICE" in
        [Ii]|[Vv])
            "$PY_BIN" "$DIR/scripts/verify_and_install_resources.py"
            read -rp "Press Enter to return to menu..." || true
            main_menu
            ;;
        [Dd])
            "$PY_BIN" "$DIR/scripts/download_full_dataset.py" --all
            read -rp "Press Enter to return to menu..." || true
            main_menu
            ;;
        1) launch_eco ;;
        2) launch_perf ;;
        3) launch_standalone ;;
        4) launch_ground ;;
        5)
            npm run build
            read -rp "Press Enter to return to menu..." || true
            main_menu
            ;;
        6)
            "$DIR/stop.sh" --no-pause
            sleep 2
            launch_eco
            ;;
        7)
            "$PY_BIN" "$DIR/scripts/diag.py"
            read -rp "Press Enter to return to menu..." || true
            main_menu
            ;;
        8)
            trap - EXIT SIGHUP SIGINT SIGTERM
            exec "$DIR/stop.sh" --no-pause
            ;;
        9)
            start_tor
            read -rp "Press Enter to return to menu..." || true
            main_menu
            ;;
        0)
            trap - EXIT SIGHUP SIGINT SIGTERM
            # Disarm watchdog on clean menu exit
            if [ -f "$DIR/.argus_watchdog.pid" ]; then
                kill -9 "$(cat "$DIR/.argus_watchdog.pid")" 2>/dev/null || true
                rm -f "$DIR/.argus_watchdog.pid"
            fi
            exit 0
            ;;
        *)
            echo "[*] Invalid selection. Please choose an option between 0 and 9."
            sleep 1
            main_menu
            ;;
    esac
}

show_help() {
    echo ""
    echo "GeoVigilant Argus Eye - Tactical CLI Launcher (Unix/Linux/macOS)"
    echo "Usage:"
    echo "  ./start.sh                     Open interactive menu with live telemetry"
    echo "  ./start.sh --install    (-i)   Verify requirements & resources, auto-install missing"
    echo "  ./start.sh --dataset    (-ds)  Download full 36.9 GB dataset with 75,000+ images"
    echo "  ./start.sh --eco        (-e)   Launch Summer Eco Dev Mode (Flask + Vite, 30 FPS)"
    echo "  ./start.sh --perf       (-p)   Launch Performance Dev Mode (Flask + Vite, 60 FPS)"
    echo "  ./start.sh --standalone (-s)   Launch Standalone Flask on :5000 (Default // No Node)"
    echo "  ./start.sh --ground     (-g)   Launch GroundView 2D Intelligence Mode"
    echo "  ./start.sh --build      (-b)   Compile frontend bundles with Vite into static/js"
    echo "  ./start.sh --restart    (-r)   Cleanly restart running Argus services"
    echo "  ./start.sh --diag       (-c)   Run hardware, CUDA GPU and network diagnostics"
    echo "  ./start.sh --stop       (-k)   Terminate all running Argus services"
    echo "  ./start.sh --tor        (-t)   Start or verify Tor SOCKS5 onion proxy (:9050)"
    echo "  ./start.sh --help       (-h)   Display this help reference"
    echo ""
    echo "Options:"
    echo "  --force                        When used with launch flags, forces termination"
    echo "                                 of existing server instances without prompting."
    echo ""
    exit 0
}

# ==============================================================================
# CLI Argument Dispatcher
# ==============================================================================
if [ -n "$1" ]; then
    IS_CLI=1
    case "$1" in
        --install|-i|--verify|-v)
            "$PY_BIN" "$DIR/scripts/verify_and_install_resources.py"
            exit 0
            ;;
        --dataset|-ds)
            "$PY_BIN" "$DIR/scripts/download_full_dataset.py" --all
            exit 0
            ;;
        --eco|-e|1) launch_eco ;;
        --perf|-p|2) launch_perf ;;
        --standalone|-s|3|--default|-d) launch_standalone ;;
        --ground|-g|4) launch_ground ;;
        --build|-b|5)
            npm run build
            exit 0
            ;;
        --restart|-r|6)
            "$DIR/stop.sh" --no-pause
            sleep 2
            launch_eco
            ;;
        --diag|-c|7)
            "$PY_BIN" "$DIR/scripts/diag.py"
            exit 0
            ;;
        --stop|--end|-k|8)
            trap - EXIT SIGHUP SIGINT SIGTERM
            exec "$DIR/stop.sh" "$@"
            ;;
        --tor|-t|9)
            start_tor
            exit 0
            ;;
        --help|-h|-\?|/\?) show_help ;;
        *)
            echo "[!] Unrecognized option: $1"
            show_help
            ;;
    esac
else
    main_menu
fi
