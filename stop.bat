@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

title GeoVigilant Argus Eye - Service Stopper

echo.
echo ================================================================================
echo   🛑 GEOVIGILANT ARGUS EYE // TERMINATING SERVICES
echo ================================================================================
echo.

REM Python virtual environment detection
set "PY_BIN=python"
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY_BIN=%~dp0.venv\Scripts\python.exe"
) else if exist "%~dp0venv\Scripts\python.exe" (
    set "PY_BIN=%~dp0venv\Scripts\python.exe"
)

"!PY_BIN!" --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    "!PY_BIN!" scripts\stop_services.py
)

REM Direct fallback port cleanup using netstat + taskkill
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":5000" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":5173" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":11434" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)
taskkill /f /im tor.exe >nul 2>&1

REM Terminate named server console windows (protecting this cleanup window)
taskkill /fi "WINDOWTITLE eq GeoVigilant_Argus_Backend*" /f /t >nul 2>&1
taskkill /fi "WINDOWTITLE eq GeoVigilant_Argus_Vite*" /f /t >nul 2>&1
taskkill /fi "WINDOWTITLE eq GeoVigilant_Argus_Ollama*" /f /t >nul 2>&1
taskkill /fi "WINDOWTITLE eq GeoVigilant_Argus_Tor*" /f /t >nul 2>&1
taskkill /fi "WINDOWTITLE eq GeoVigilant_Argus_Watchdog*" /f /t >nul 2>&1

echo.
echo  [+] Port 5000 [Backend]   : CLEARED
echo  [+] Port 5173 [Dev Vite]  : CLEARED
echo  [+] Port 11434 [AI Core]  : CLEARED
echo  [+] Port 9050 [Tor Proxy] : CLEARED
echo  [+] Background processes  : TERMINATED
echo.
echo ================================================================================
echo   System cooled down. All GeoVigilant services safely halted.
echo ================================================================================
echo.

if "%~1"=="--no-pause" (
    rem Exit immediately without waiting
) else if "%~1"=="--auto-close" (
    echo  [*] Auto-closing cleanup console in 2 seconds...
    ping 127.0.0.1 -n 3 >nul 2>&1
) else (
    pause
)

