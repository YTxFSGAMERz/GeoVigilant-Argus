@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

title GeoVigilant Argus Eye - Tactical Mission Launcher

REM ============================================================================
REM Python & Virtual Environment Auto-Detection
REM ============================================================================
set "PY_BIN=python"
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY_BIN=%~dp0.venv\Scripts\python.exe"
) else if exist "%~dp0venv\Scripts\python.exe" (
    set "PY_BIN=%~dp0venv\Scripts\python.exe"
)

"!PY_BIN!" --version >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo ================================================================================
    echo   [!] CRITICAL ERROR: Python is not detected in your PATH or virtualenv.
    echo       Please install Python 3.10+ from python.org and add it to PATH.
    echo ================================================================================
    echo.
    pause
    exit /b 1
)

if /i "%~1"=="--help" goto SHOW_HELP
if /i "%~1"=="-h"     goto SHOW_HELP
if /i "%~1"=="/?"     goto SHOW_HELP
if /i "%~1"=="--stop" (set "IS_CLI=1" & goto RUN_STOP)
if /i "%~1"=="--end"  (set "IS_CLI=1" & goto RUN_STOP)
if /i "%~1"=="-k"     (set "IS_CLI=1" & goto RUN_STOP)
if /i "%~1"=="8"      (set "IS_CLI=1" & goto RUN_STOP)

REM Initialize Terminal Window-Close Watchdog
call :START_WATCHDOG

REM ============================================================================
REM Requirements & Resources Pre-Flight Check (Auto-Installs Missing Items)
REM ============================================================================
"!PY_BIN!" "%~dp0scripts\verify_and_install_resources.py"
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo [!] WARNING: Pre-flight check encountered non-fatal notices.
    echo.
)

REM ============================================================================
REM Handle CLI Arguments
REM ============================================================================
if /i "%~1"=="--install"    (set "IS_CLI=1" & goto RUN_INSTALL)
if /i "%~1"=="-i"           (set "IS_CLI=1" & goto RUN_INSTALL)
if /i "%~1"=="--verify"     (set "IS_CLI=1" & goto RUN_INSTALL)
if /i "%~1"=="-v"           (set "IS_CLI=1" & goto RUN_INSTALL)
if /i "%~1"=="--eco"        (set "IS_CLI=1" & goto LAUNCH_ECO)
if /i "%~1"=="-e"           (set "IS_CLI=1" & goto LAUNCH_ECO)
if /i "%~1"=="1"            (set "IS_CLI=1" & goto LAUNCH_ECO)

if /i "%~1"=="--perf"       (set "IS_CLI=1" & goto LAUNCH_PERF)
if /i "%~1"=="-p"           (set "IS_CLI=1" & goto LAUNCH_PERF)
if /i "%~1"=="2"            (set "IS_CLI=1" & goto LAUNCH_PERF)

if /i "%~1"=="--standalone" (set "IS_CLI=1" & goto LAUNCH_STANDALONE)
if /i "%~1"=="-s"           (set "IS_CLI=1" & goto LAUNCH_STANDALONE)
if /i "%~1"=="3"            (set "IS_CLI=1" & goto LAUNCH_STANDALONE)
if /i "%~1"=="--default"    (set "IS_CLI=1" & goto LAUNCH_STANDALONE)
if /i "%~1"=="-d"           (set "IS_CLI=1" & goto LAUNCH_STANDALONE)

if /i "%~1"=="--ground"     (set "IS_CLI=1" & goto LAUNCH_GROUND)
if /i "%~1"=="-g"           (set "IS_CLI=1" & goto LAUNCH_GROUND)
if /i "%~1"=="4"            (set "IS_CLI=1" & goto LAUNCH_GROUND)

if /i "%~1"=="--build"      (set "IS_CLI=1" & goto RUN_BUILD)
if /i "%~1"=="-b"           (set "IS_CLI=1" & goto RUN_BUILD)
if /i "%~1"=="5"            (set "IS_CLI=1" & goto RUN_BUILD)

if /i "%~1"=="--restart"    (set "IS_CLI=1" & goto RUN_RESTART)
if /i "%~1"=="-r"           (set "IS_CLI=1" & goto RUN_RESTART)
if /i "%~1"=="6"            (set "IS_CLI=1" & goto RUN_RESTART)

if /i "%~1"=="--diag"       (set "IS_CLI=1" & goto RUN_DIAG)
if /i "%~1"=="-c"           (set "IS_CLI=1" & goto RUN_DIAG)
if /i "%~1"=="7"            (set "IS_CLI=1" & goto RUN_DIAG)

if /i "%~1"=="--stop"       (set "IS_CLI=1" & goto RUN_STOP)
if /i "%~1"=="--end"        (set "IS_CLI=1" & goto RUN_STOP)
if /i "%~1"=="-k"           (set "IS_CLI=1" & goto RUN_STOP)
if /i "%~1"=="8"            (set "IS_CLI=1" & goto RUN_STOP)

if /i "%~1"=="--tor"        (set "IS_CLI=1" & goto RUN_TOR)
if /i "%~1"=="-t"           (set "IS_CLI=1" & goto RUN_TOR)
if /i "%~1"=="9"            (set "IS_CLI=1" & goto RUN_TOR)

if /i "%~1"=="--dataset"    (set "IS_CLI=1" & goto RUN_DATASET)
if /i "%~1"=="-ds"          (set "IS_CLI=1" & goto RUN_DATASET)

if /i "%~1"=="--help"       goto SHOW_HELP
if /i "%~1"=="-h"           goto SHOW_HELP
if /i "%~1"=="/?"           goto SHOW_HELP

REM ============================================================================
REM Interactive Main Menu with Live Telemetry
REM ============================================================================
:MAIN_MENU
call :START_WATCHDOG
cls
set "STAT_FLASK=[OFFLINE]"
set "STAT_VITE=[OFFLINE]"
set "STAT_OLLAMA=[OFFLINE]"
set "STAT_TOR=[OFFLINE]"

netstat -ano 2>nul | findstr ":5000" | findstr "LISTENING" >nul && set "STAT_FLASK=[ONLINE :5000]"
netstat -ano 2>nul | findstr ":5173" | findstr "LISTENING" >nul && set "STAT_VITE=[ONLINE :5173]"
netstat -ano 2>nul | findstr ":11434" | findstr "LISTENING" >nul && set "STAT_OLLAMA=[ONLINE :11434]"
netstat -ano 2>nul | findstr ":9050" | findstr "LISTENING" >nul && set "STAT_TOR=[ONLINE :9050]"

echo.
echo ================================================================================
echo   [+] GEOVIGILANT ARGUS EYE // TACTICAL MISSION CONTROL
echo   // CLASSIFICATION: TOP SECRET // SI-TK // NOFORN
echo   // MISSION CONTROL ^& THERMAL MANAGEMENT PROFILES
echo ================================================================================
echo.
echo   LIVE SYSTEM TELEMETRY:
echo     * Flask Backend   : !STAT_FLASK!
echo     * Vite Dev Server : !STAT_VITE!
echo     * Ollama AI Core  : !STAT_OLLAMA!
echo     * Tor Onion Proxy : !STAT_TOR!
echo     * Python Runtime  : !PY_BIN!
echo     * Close Watchdog  : [ACTIVE // Auto-Runs stop.bat on Window Close]
echo.
echo   OPERATIONAL PROFILES:
echo.
echo   [1] ❄️  SUMMER ECO DEV MODE      (FLASK + VITE HMR // 30 FPS)
echo       - Full Dev Stack: Flask Backend (:5000) + Vite Dev Server (:5173) with HMR
echo       - 30 FPS capped render loop, 2048MB Node heap buffer, minimal thermal load
echo       - Ideal for live coding, testing UI changes, and whisper-quiet fans
echo       - URL: http://localhost:5173/
echo.
echo   [2] ⚡  PERFORMANCE DEV MODE     (FULL FIDELITY // 60 FPS)
echo       - Full Dev Stack: Flask Backend (:5000) + Vite Dev Server (:5173) with HMR
echo       - 60 FPS full render loop, 4096MB Node heap buffer, max texture/shader sampling
echo       - URL: http://localhost:5173/
echo.
echo   [3] 📦  STANDALONE FLASK ONLY    (DEFAULT // RECOMMENDED // ROOT URL)
echo       - Starts Flask only (:5000) serving pre-compiled assets
echo       - Zero Node.js overhead, ideal for low RAM or background server use
echo       - URL: http://localhost:5000/
echo.
echo   [4] 🗺️  GROUNDVIEW 2D INTEL      (LOWEST OVERHEAD)
echo       - High-density tactical 2D vector intelligence ^& POI explorer
echo       - Ultra-low battery ^& thermal consumption
echo       - URL: http://localhost:5173/ground
echo.
echo   [5] 🛠️  BUILD PRODUCTION ASSETS  (Vite Rollup Bundler)
echo       - Compiles and syncs latest frontend into static/js for Standalone Mode
echo.
echo   [6] 🔄  RESTART ALL SERVICES     (Clean Cycle)
echo       - Halts active instances, clears ports, and boots fresh stack
echo.
echo   [7] 🔍  HARDWARE ^& GPU DIAGNOSTICS
echo       - Tests PyTorch CUDA acceleration, NVIDIA RTX 3050 status, ports, thermals
echo.
echo   [8] 🛑  STOP / END SERVICES
echo       - Terminate all active GeoVigilant servers and free occupied ports
echo.
echo   [9] 🧅  TOR ONION DAEMON CONTROL
echo       - Start or verify local SOCKS5 proxy (:9050) and Control Port (:9051)
echo.
echo   [I] 📦  VERIFY ^& INSTALL REQUIREMENTS / RESOURCES
echo       - Validate Python packages, npm modules, .env vault, and core dataset resources
echo.
echo   [D] 🛰️  DOWNLOAD FULL ARGUS DATASET (Optional // ~36.9 GB)
echo       - Multi-threaded download of all 75,000+ surveillance images from Hugging Face
echo.
echo   [0] 🚪  EXIT
echo.
echo ================================================================================
set "CHOICE=3"
set /p "CHOICE=Enter selection [1-9, I, D, or 0] [Press Enter for Default 3]: "

if /i "%CHOICE%"=="I" goto RUN_INSTALL
if /i "%CHOICE%"=="V" goto RUN_INSTALL
if /i "%CHOICE%"=="D" goto RUN_DATASET
if "%CHOICE%"=="1" goto LAUNCH_ECO
if "%CHOICE%"=="2" goto LAUNCH_PERF
if "%CHOICE%"=="3" goto LAUNCH_STANDALONE
if "%CHOICE%"=="4" goto LAUNCH_GROUND
if "%CHOICE%"=="5" goto RUN_BUILD
if "%CHOICE%"=="6" goto RUN_RESTART
if "%CHOICE%"=="7" goto RUN_DIAG
if "%CHOICE%"=="8" goto RUN_STOP
if "%CHOICE%"=="9" goto RUN_TOR
if "%CHOICE%"=="0" goto EXIT_SCRIPT

echo [*] Invalid selection. Please choose an option between 0 and 9.
ping 127.0.0.1 -n 2 >nul
goto MAIN_MENU

REM ============================================================================
REM TERMINAL CLOSE WATCHDOG (Auto-runs stop.bat if user clicks [X] on this window)
REM ============================================================================
:START_WATCHDOG
if not defined WATCHDOG_ACTIVE (
    set "WATCHDOG_ACTIVE=1"
    "!PY_BIN!" "%~dp0scripts\watchdog.py" --spawn >nul 2>&1
)
exit /b 0

REM ============================================================================
REM PRE-FLIGHT PORT CHECK HELPER (Checks both Flask :5000 and Vite :5173)
REM ============================================================================
:CHECK_PORTS
set "PORTS_BUSY=0"
set "SKIP_SERVER_LAUNCH=0"
set "CONFLICT_PIDS="

for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":5000 :5173" ^| findstr "LISTENING"') do (
    set "PORTS_BUSY=1"
    set "CONFLICT_PIDS=!CONFLICT_PIDS! %%a"
)

if "!PORTS_BUSY!"=="1" (
    echo.
    echo [*] ALERT: Port 5000 or 5173 is already active [PIDs:!CONFLICT_PIDS!].
    if defined IS_CLI (
        if /i "%~2"=="--force" (
            echo [*] Force restart requested. Halting existing instances...
            call stop.bat --no-pause
            ping 127.0.0.1 -n 3 >nul
        ) else (
            echo [*] Preserving running server instances. Directing to web console...
            set "SKIP_SERVER_LAUNCH=1"
        )
    ) else (
        set "RESTART_SRV=Y"
        set /p "RESTART_SRV=Restart servers and terminate existing instances? [Y/N] [Default: Y]: "
        if /i "!RESTART_SRV!"=="Y" (
            echo [*] Stopping previous instances...
            call stop.bat --no-pause
            ping 127.0.0.1 -n 3 >nul
        ) else (
            echo [*] Preserving running server instances. Directing to web console...
            set "SKIP_SERVER_LAUNCH=1"
        )
    )
)
exit /b 0

REM ============================================================================
REM NODE & NODE_MODULES VERIFICATION (For Vite-dependent modes)
REM ============================================================================
:VERIFY_NODE
where npm >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo.
    echo ================================================================================
    echo   [*] NOTICE: Node.js and npm were not detected in system PATH.
    echo       Vite HMR Dev server requires Node.js 18+.
    echo.
    echo   [*] Auto-routing to STANDALONE FLASK MODE [Option 3]...
    echo       [Flask serves all compiled assets directly with zero Node.js overhead]
    echo ================================================================================
    echo.
    ping 127.0.0.1 -n 3 >nul
    goto LAUNCH_STANDALONE
)

if not exist "%~dp0node_modules" (
    echo.
    echo [*] ALERT: node_modules directory was not found.
    set "DO_NPM_INSTALL=Y"
    if not defined IS_CLI (
        set /p "DO_NPM_INSTALL=Run 'npm install' now to setup frontend dependencies? [Y/N] [Default: Y]: "
    )
    if /i "!DO_NPM_INSTALL!"=="Y" (
        echo [*] Running npm install...
        call npm install
    )
)
exit /b 0

REM ============================================================================
REM OLLAMA CLOUD BACKEND DAEMON CHECK & LAUNCHER
REM ============================================================================
:START_OLLAMA
set "OLLAMA_ACTIVE=0"
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":11434" ^| findstr "LISTENING"') do (
    set "OLLAMA_ACTIVE=1"
)
if "!OLLAMA_ACTIVE!"=="1" (
    echo  [+] Ollama AI Core : ACTIVE [:11434 // Cloud Bridge Ready]
    exit /b 0
)

echo [*] Starting Ollama Cloud AI Backend Daemon (:11434)...
set "OLLAMA_EXE="
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if not defined OLLAMA_EXE (
    for /f "delims=" %%i in ('where ollama 2^>nul') do (
        if not defined OLLAMA_EXE set "OLLAMA_EXE=%%i"
    )
)
if defined OLLAMA_EXE (
    start "GeoVigilant_Argus_Ollama" /min cmd /c "title GeoVigilant_Argus_Ollama && set OLLAMA_KEEP_ALIVE=-1 && set OLLAMA_FLASH_ATTENTION=1 && "!OLLAMA_EXE!" serve"
    echo  [+] Ollama Daemon  : SPAWNED [Persistent VRAM / Flash Attention Active]
    ping 127.0.0.1 -n 3 >nul
) else (
    echo  [*] Ollama Core    : Not found in PATH [Optional: install from ollama.com for local LLM inference]
)
exit /b 0

REM ============================================================================
REM TOR SOCKS5 ONION DAEMON CHECK & LAUNCHER
REM ============================================================================
:START_TOR
set "TOR_ACTIVE=0"
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":9050" ^| findstr "LISTENING"') do (
    set "TOR_ACTIVE=1"
)
if "!TOR_ACTIVE!"=="1" (
    echo  [+] Tor Onion Daemon : ACTIVE [:9050 SOCKS5 // :9051 Control]
    exit /b 0
)

echo [*] Starting Tor SOCKS5 Onion Daemon (:9050)...
set "TOR_EXE=%~dp0tor-expert-bundle-windows-i686-15.0.19\tor\tor.exe"
if exist "!TOR_EXE!" (
    if not exist "%~dp0data\tor" mkdir "%~dp0data\tor" >nul 2>&1
    start "GeoVigilant_Argus_Tor" /min cmd /c "title GeoVigilant_Argus_Tor && cd /d "%~dp0" && "!TOR_EXE!" -f torrc"
    echo  [+] Tor Onion Daemon : SPAWNED [SOCKS5 Port 9050 // Control Port 9051]
    ping 127.0.0.1 -n 2 >nul
) else (
    echo  [*] Tor Onion Daemon : Executable not found at !TOR_EXE!
)
exit /b 0

REM ============================================================================
REM ACTIVE PORT READINESS LOOP
REM ============================================================================
:WAIT_FOR_PORT
REM %1 = Port to wait for
set "PORT_TO_WAIT=%~1"
set "MAX_TRIES=10"
set "CURRENT_TRY=0"

:WAIT_PORT_LOOP
set /a CURRENT_TRY+=1
netstat -ano 2>nul | findstr ":!PORT_TO_WAIT!" | findstr "LISTENING" >nul
if !ERRORLEVEL! EQU 0 (
    echo  [+] Service on port !PORT_TO_WAIT! confirmed READY.
    exit /b 0
)
if !CURRENT_TRY! GEQ !MAX_TRIES! (
    echo  [*] Server initialization taking longer than expected. Continuing launch...
    exit /b 0
)
ping 127.0.0.1 -n 2 >nul
goto WAIT_PORT_LOOP

REM ============================================================================
REM 1. SUMMER ECO DEV MODE (Flask Backend + Vite Dev Server in 30 FPS Eco Mode)
REM ============================================================================
:LAUNCH_ECO
echo.
echo ================================================================================
echo   ❄️  CONFIGURING SUMMER ECO DEV MODE (FLASK + VITE HMR // 30 FPS)
echo ================================================================================
call :VERIFY_NODE
set "ARGUS_MODE=eco"
call :CHECK_PORTS
call :START_OLLAMA
call :START_TOR

set "TARGET_URL=http://localhost:5173/"

if "!SKIP_SERVER_LAUNCH!"=="1" goto OPEN_ECO_UI

echo [*] Starting GeoVigilant Flask Backend on Port 5000...
start "GeoVigilant_Argus_Backend" cmd /k "title GeoVigilant_Argus_Backend && set ARGUS_MODE=eco && "!PY_BIN!" app.py"

echo [*] Starting Vite Frontend Dev Server with HMR on Port 5173 (2048MB heap buffer)...
start "GeoVigilant_Argus_Vite" cmd /k "title GeoVigilant_Argus_Vite && set NODE_OPTIONS=--max-old-space-size=2048 && npm run dev"

echo [*] Verifying backend and frontend readiness...
call :WAIT_FOR_PORT 5000
call :WAIT_FOR_PORT 5173

:OPEN_ECO_UI
echo [*] Launching operator tactical console: %TARGET_URL%
start "" "%TARGET_URL%"

echo.
echo ================================================================================
echo   [OK] GEOVIGILANT ARGUS EYE ACTIVE IN FULL DEV + ECO MODE
echo   * Frontend (Vite) : http://localhost:5173/ [Hot Reloading Active]
echo   * Backend (Flask) : http://localhost:5000 [API Proxied]
echo   * FPS Limit       : 30 FPS capped [Slashing thermal wattage by ~60%%]
echo   * Node Heap       : 2048 MB allocated [OOM Protected]
echo   * Live Coding     : Edit frontend in globe/src/ - updates reflect live.
echo   * Stop Tool       : Run stop.bat or end.bat to terminate stack
echo ================================================================================
if not defined IS_CLI goto POST_LAUNCH_MENU
exit /b 0

REM ============================================================================
REM 2. PERFORMANCE DEV MODE (Flask Backend + Vite Dev Server in 60 FPS Turbo Mode)
REM ============================================================================
:LAUNCH_PERF
echo.
echo ================================================================================
echo   ⚡  CONFIGURING PERFORMANCE DEV MODE (FLASK + VITE HMR // 60 FPS)
echo ================================================================================
call :VERIFY_NODE
set "ARGUS_MODE=perf"
call :CHECK_PORTS
call :START_OLLAMA
call :START_TOR

set "TARGET_URL=http://localhost:5173/"

if "!SKIP_SERVER_LAUNCH!"=="1" goto OPEN_PERF_UI

echo [*] Starting GeoVigilant Flask Backend on Port 5000...
start "GeoVigilant_Argus_Backend" cmd /k "title GeoVigilant_Argus_Backend && set ARGUS_MODE=perf && "!PY_BIN!" app.py"

echo [*] Starting Vite Frontend Dev Server with HMR on Port 5173 (4096MB heap buffer)...
start "GeoVigilant_Argus_Vite" cmd /k "title GeoVigilant_Argus_Vite && set NODE_OPTIONS=--max-old-space-size=4096 && npm run dev"

echo [*] Verifying backend and frontend readiness...
call :WAIT_FOR_PORT 5000
call :WAIT_FOR_PORT 5173

:OPEN_PERF_UI
echo [*] Launching operator tactical console: %TARGET_URL%
start "" "%TARGET_URL%"

echo.
echo ================================================================================
echo   [OK] GEOVIGILANT ARGUS EYE ACTIVE IN FULL DEV + PERFORMANCE MODE
echo   * Frontend (Vite) : http://localhost:5173/ [Hot Reloading Active]
echo   * Backend (Flask) : http://localhost:5000 [API Proxied]
echo   * FPS Limit       : 60 FPS full fidelity
echo   * Node Heap       : 4096 MB allocated [Max Performance Buffer]
echo   * Live Coding     : Edit frontend in globe/src/ - updates reflect live.
echo   * Stop Tool       : Run stop.bat or end.bat to terminate stack
echo ================================================================================
if not defined IS_CLI goto POST_LAUNCH_MENU
exit /b 0

REM ============================================================================
REM 3. STANDALONE FLASK ONLY (No Vite / No Node.js / Lowest RAM)
REM ============================================================================
:LAUNCH_STANDALONE
echo.
echo ================================================================================
echo   📦  CONFIGURING STANDALONE PRODUCTION MODE (FLASK ONLY // NO NODE.JS)
echo ================================================================================
set "ARGUS_MODE=eco"
call :CHECK_PORTS
call :START_OLLAMA
call :START_TOR

set "TARGET_URL=http://localhost:5000/"

if "!SKIP_SERVER_LAUNCH!"=="1" goto OPEN_STANDALONE_UI

echo [*] Starting GeoVigilant Flask Backend on Port 5000...
start "GeoVigilant_Argus_Backend" cmd /k "title GeoVigilant_Argus_Backend && set ARGUS_MODE=eco && "!PY_BIN!" app.py"

echo [*] Verifying telemetry uplink readiness...
call :WAIT_FOR_PORT 5000

:OPEN_STANDALONE_UI
echo [*] Launching operator tactical console: %TARGET_URL%
start "" "%TARGET_URL%"

echo.
echo ================================================================================
echo   [OK] STANDALONE BACKEND ACTIVE (LOWEST RAM)
echo   * URL       : %TARGET_URL%
echo   * Node/Vite : Disabled [Serving pre-compiled assets directly via Flask]
echo   * FPS Limit : 30 FPS capped [Cool thermal footprint]
echo   * Stop Tool : Run stop.bat or end.bat to terminate
echo ================================================================================
if not defined IS_CLI goto POST_LAUNCH_MENU
exit /b 0

REM ============================================================================
REM 4. GROUNDVIEW 2D INTEL
REM ============================================================================
:LAUNCH_GROUND
echo.
echo ================================================================================
echo   🗺️  CONFIGURING GROUNDVIEW 2D INTEL PROFILE
echo ================================================================================
call :VERIFY_NODE
set "ARGUS_MODE=eco"
call :CHECK_PORTS
call :START_OLLAMA
call :START_TOR

set "TARGET_URL=http://localhost:5173/ground"

if "!SKIP_SERVER_LAUNCH!"=="1" goto OPEN_GROUND_UI

echo [*] Starting GeoVigilant Flask Backend on Port 5000...
start "GeoVigilant_Argus_Backend" cmd /k "title GeoVigilant_Argus_Backend && set ARGUS_MODE=eco && "!PY_BIN!" app.py"

echo [*] Starting Vite Frontend Dev Server on Port 5173 (2048MB heap buffer)...
start "GeoVigilant_Argus_Vite" cmd /k "title GeoVigilant_Argus_Vite && set NODE_OPTIONS=--max-old-space-size=2048 && npm run dev"

echo [*] Verifying servers readiness...
call :WAIT_FOR_PORT 5000
call :WAIT_FOR_PORT 5173

:OPEN_GROUND_UI
echo [*] Launching GroundView console: %TARGET_URL%
start "" "%TARGET_URL%"

echo.
echo ================================================================================
echo   [OK] GROUNDVIEW 2D INTEL CONSOLE ACTIVE
echo   * URL       : %TARGET_URL%
echo   * Node Heap : 2048 MB allocated [OOM Protected]
echo   * Stop Tool : Run stop.bat or end.bat to terminate
echo ================================================================================
if not defined IS_CLI goto POST_LAUNCH_MENU
exit /b 0

REM ============================================================================
REM POST-LAUNCH MISSION CONTROL STATUS & MENU RETURN
REM ============================================================================
:POST_LAUNCH_MENU
if defined IS_CLI exit /b 0

echo.
echo ================================================================================
echo   [!] TACTICAL MISSION CONTROL STATUS: ACTIVE
echo       * Keep this window open while GeoVigilant Argus is active.
echo       * Clicking [X] (Cross) on this window will automatically launch stop.bat
echo         and safely terminate all backend, Vite, AI, and Tor services.
echo ================================================================================
echo.
echo   Navigation:
echo     [M] Return to Tactical Menu (Live Telemetry ^& Diagnostics)
echo     [S] Stop all services now and exit
echo.
set "POST_ACTION=M"
set /p "POST_ACTION=Select option [M/S] [Press Enter for Menu]: "
if /i "!POST_ACTION!"=="S" goto RUN_STOP
goto MAIN_MENU


REM ============================================================================
REM 5. BUILD PRODUCTION ASSETS
REM ============================================================================
:RUN_BUILD
cls
echo.
echo ================================================================================
echo   🛠️  COMPILING PRODUCTION FRONTEND ASSETS (VITE ROLLUP BUNDLER)
echo ================================================================================
echo.
where npm >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [!] ERROR: Node.js and npm are required to build production assets.
    if defined IS_CLI exit /b 1
    pause
    goto MAIN_MENU
)
call npm run build
echo.
if !ERRORLEVEL! EQU 0 (
    echo [+] Build successful: Pre-compiled assets deployed to static/js/
) else (
    echo [!] Build exited with code !ERRORLEVEL!. Please check compiler errors above.
)
echo.
if defined IS_CLI exit /b 0
pause
goto MAIN_MENU

REM ============================================================================
REM 6. RESTART SERVICES (Clean Cycle)
REM ============================================================================
:RUN_RESTART
cls
echo.
echo ================================================================================
echo   🔄 RESTARTING GEOVIGILANT ARGUS EYE SERVICES
echo ================================================================================
echo.
echo [*] Terminating existing server instances...
call stop.bat --no-pause
ping 127.0.0.1 -n 3 >nul
echo [*] Re-launching Summer Eco Dev Mode...
goto LAUNCH_ECO

REM ============================================================================
REM 7. DIAGNOSTICS
REM ============================================================================
:RUN_DIAG
cls
"!PY_BIN!" scripts\diag.py
echo.
if defined IS_CLI exit /b 0
pause
goto MAIN_MENU

REM ============================================================================
REM 8. STOP SERVICES
REM ============================================================================
:RUN_STOP
cls
call stop.bat --no-pause
echo.
if defined IS_CLI exit /b 0
pause
goto MAIN_MENU

REM ============================================================================
REM 9. TOR ONION DAEMON CONTROL
REM ============================================================================
:RUN_TOR
cls
echo.
echo ================================================================================
echo   🧅 GEOVIGILANT ARGUS EYE // TOR SOCKS5 ONION DAEMON
echo ================================================================================
echo.
call :START_TOR
echo.
echo [*] Tor socket verification:
netstat -ano 2>nul | findstr ":9050 :9051" | findstr "LISTENING"
echo.
if defined IS_CLI exit /b 0
pause
goto MAIN_MENU

REM ============================================================================
REM I. VERIFY & INSTALL REQUIREMENTS / RESOURCES
REM ============================================================================
:RUN_INSTALL
cls
echo.
echo ================================================================================
echo   [+] VERIFYING REQUIREMENTS ^& RESOURCES (AUTO-INSTALLER)
echo ================================================================================
"!PY_BIN!" "%~dp0scripts\verify_and_install_resources.py"
echo.
if defined IS_CLI exit /b 0
pause
goto MAIN_MENU

REM ============================================================================
REM D. DOWNLOAD FULL ARGUS DATASET (75,000+ images from Hugging Face)
REM ============================================================================
:RUN_DATASET
cls
"!PY_BIN!" "%~dp0scripts\download_full_dataset.py" --all
echo.
if defined IS_CLI exit /b 0
pause
goto MAIN_MENU

REM ============================================================================
REM HELP
REM ============================================================================
:SHOW_HELP
echo.
echo GeoVigilant Argus Eye - Tactical CLI Launcher
echo Usage:
echo   start.bat                     Open interactive menu with live telemetry
echo   start.bat --install    (-i)   Verify requirements ^& resources, auto-install missing
echo   start.bat --dataset    (-ds)  Download full 36.9 GB dataset with 75,000+ images
echo   start.bat --eco        (-e)   Launch Summer Eco Dev Mode (Flask + Vite, 30 FPS)
echo   start.bat --perf       (-p)   Launch Performance Dev Mode (Flask + Vite, 60 FPS)
echo   start.bat --standalone (-s)   Launch Standalone Flask on :5000 (Default // No Node)
echo   start.bat --ground     (-g)   Launch GroundView 2D Intelligence Mode
echo   start.bat --build      (-b)   Compile frontend bundles with Vite into static/js
echo   start.bat --restart    (-r)   Cleanly restart running Argus services
echo   start.bat --diag       (-c)   Run hardware, CUDA GPU and network diagnostics
echo   start.bat --stop       (-k)   Terminate all running Argus services
echo   start.bat --tor        (-t)   Start or verify Tor SOCKS5 onion proxy (:9050)
echo   start.bat --help       (-h)   Display this help reference
echo.
echo Options:
echo   --force                       When used with launch flags, forces termination
echo                                 of existing server instances without prompting.
echo.
exit /b 0

:EXIT_SCRIPT
if exist "%~dp0.argus_watchdog.pid" (
    for /f "usebackq" %%w in ("%~dp0.argus_watchdog.pid") do (
        taskkill /f /pid %%w >nul 2>&1
    )
    del "%~dp0.argus_watchdog.pid" >nul 2>&1
)
exit /b 0
