@echo off
setlocal EnableExtensions EnableDelayedExpansion

title AgriConnect Launcher

REM ============================================================
REM AGRICONNECT CONFIGURATION
REM ============================================================

set "PROJECT=%~dp0."
set "BACKEND=%PROJECT%\backend"
set "FRONTEND=%PROJECT%\frontend"
set "VENV=%PROJECT%\.venv"
set "PG_SERVICE=postgresql-x64-18"

REM ============================================================
REM HEADER
REM ============================================================

cls

echo.
echo ============================================================
echo                    AGRICONNECT
echo                 Application Launcher
echo ============================================================
echo.
echo Starting AgriConnect...
echo.

REM ============================================================
REM CHECK PROJECT
REM ============================================================

echo [1/8] Checking AgriConnect project...

if not exist "%PROJECT%" (
    echo ERROR: Project folder was not found.
    goto FAILED
)

if not exist "%BACKEND%\main.py" (
    echo ERROR: Backend main.py was not found.
    goto FAILED
)

if not exist "%FRONTEND%\package.json" (
    echo ERROR: Frontend package.json was not found.
    goto FAILED
)

echo        OK
echo.

REM ============================================================
REM CHECK PYTHON ENVIRONMENT
REM ============================================================

echo [2/8] Checking Python environment...

if not exist "%VENV%\Scripts\python.exe" (
    echo ERROR: Python virtual environment was not found.
    goto FAILED
)

echo        OK
echo.

REM ============================================================
REM CHECK NODE / NPM
REM ============================================================

echo [3/8] Checking Node.js / npm...

where npm >nul 2>&1

if errorlevel 1 (
    echo ERROR: npm was not found.
    echo Please install Node.js or check your PATH.
    goto FAILED
)

echo        OK
echo.

REM ============================================================
REM CHECK / START POSTGRESQL
REM ============================================================

REM Prefer the installed executable; only search PATH as a fallback.
set "CLOUDFLARED=C:\Program Files (x86)\cloudflared\cloudflared.exe"
if exist "%CLOUDFLARED%" goto CLOUDFLARED_FOUND
set "CLOUDFLARED=cloudflared"
where cloudflared >nul 2>&1
if errorlevel 1 (
    echo ERROR: Cloudflare executable was not found in its install folder or PATH.
    goto FAILED
)
:CLOUDFLARED_FOUND
echo [4/8] Checking PostgreSQL service...

sc query "%PG_SERVICE%" >nul 2>&1

if errorlevel 1 (
    echo ERROR: PostgreSQL service "%PG_SERVICE%" was not found.
    goto FAILED
)

for /f "tokens=4" %%A in ('sc query "%PG_SERVICE%" ^| findstr "STATE"') do (
    set "PG_STATE=%%A"
)

if /I "!PG_STATE!"=="RUNNING" (
    echo        PostgreSQL is already running.
) else (
    echo        PostgreSQL is not running.
    echo        Attempting to start PostgreSQL...

    net start "%PG_SERVICE%" >nul 2>&1

    if errorlevel 1 (
        echo ERROR: Could not start PostgreSQL.
        echo Please run this launcher as Administrator.
        goto FAILED
    )

    echo        PostgreSQL started successfully.
)

echo.

REM ============================================================
REM CHECK DATABASE CONNECTION
REM ============================================================

echo [5/8] Checking AgriConnect database...

"%VENV%\Scripts\python.exe" "%BACKEND%\health_check.py"

if errorlevel 1 (
    echo.
    echo ERROR: AgriConnect database is not available.
    goto FAILED
)

echo        Database is ready.
echo.

REM ============================================================
REM START BACKEND
REM ============================================================

echo [6/8] Starting AgriConnect backend...

start "AgriConnect Backend" /D "%BACKEND%" "%ComSpec%" /D /K ""%VENV%\Scripts\python.exe" -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"

echo        Waiting for backend...

set /a BACKEND_ATTEMPTS=0

:WAIT_BACKEND

set /a BACKEND_ATTEMPTS+=1

timeout /t 2 /nobreak >nul

powershell -NoProfile -Command "try { $r=Invoke-WebRequest -Uri 'http://127.0.0.1:8000/docs' -UseBasicParsing -TimeoutSec 2; if($r.StatusCode -eq 200){exit 0}else{exit 1} } catch { exit 1 }"

if not errorlevel 1 (
    echo        Backend is ready.
    goto START_FRONTEND
)

if !BACKEND_ATTEMPTS! GEQ 30 (
    echo ERROR: Backend did not become ready within 60 seconds.
    goto FAILED
)

goto WAIT_BACKEND


REM ============================================================
REM START FRONTEND
REM ============================================================

:START_FRONTEND

echo.
echo [7/8] Starting AgriConnect frontend...

start "AgriConnect Frontend" /D "%FRONTEND%" "%ComSpec%" /D /K "npm run dev"

echo        Waiting for frontend...

set /a FRONTEND_ATTEMPTS=0

:WAIT_FRONTEND

set /a FRONTEND_ATTEMPTS+=1

timeout /t 2 /nobreak >nul

powershell -NoProfile -Command "try { $r=Invoke-WebRequest -Uri 'http://127.0.0.1:5173' -UseBasicParsing -TimeoutSec 5; if($r.StatusCode -eq 200){exit 0}else{exit 1} } catch { exit 1 }"

if not errorlevel 1 (
    goto READY
)

if !FRONTEND_ATTEMPTS! GEQ 30 (
    echo ERROR: Frontend did not become ready after 30 attempts. Check the Vite window and errors above.
    goto FAILED
)

goto WAIT_FRONTEND


REM ============================================================
REM SUCCESS
REM ============================================================

:READY

echo [8/8] Starting Cloudflare Quick Tunnel...
REM Use a fresh log so an earlier tunnel URL is never reused.
set "AGRICONNECT_TUNNEL_LOG=%TEMP%\AgriConnect-tunnel-%RANDOM%-%RANDOM%-%RANDOM%.log"
start "AgriConnect Cloudflare" /D "%PROJECT%" "%ComSpec%" /D /K ""%CLOUDFLARED%" tunnel --url http://localhost:5173 --logfile "%AGRICONNECT_TUNNEL_LOG%""

cls

echo.
echo ============================================================
echo.
echo                  AGRICONNECT IS READY
echo.
echo ============================================================
echo.
echo    Application : http://localhost:5173
echo    Backend     : http://127.0.0.1:8000
echo    API Docs    : http://127.0.0.1:8000/docs
echo.
echo    PostgreSQL  : Running
echo    Database    : Connected
echo    Backend     : Ready
echo    Frontend    : Ready
echo.
echo    Public URL  : Copy the https://...trycloudflare.com URL
echo                  from the AgriConnect Cloudflare window.
echo    Keep all three service windows open while testing.
echo    To stop the tunnel, press Ctrl+C in its window.
echo    Run stop_agriconnect.bat to stop all three services.
echo.
echo ============================================================
echo.

echo Waiting up to 90 seconds for the new public URL...
powershell -NoProfile -STA -Command "& ([scriptblock]::Create([IO.File]::ReadAllText((Join-Path $env:PROJECT 'show_agriconnect_url.ps1'))))"

echo.
echo AgriConnect has been launched successfully.
echo You can close this launcher window.
echo.

pause
exit /b 0


REM ============================================================
REM FAILURE
REM ============================================================

:FAILED

echo.
echo ============================================================
echo.
echo              AGRICONNECT COULD NOT START
echo.
echo ============================================================
echo.
echo Please review the error message above.
echo.

powershell -NoProfile -Command ^
"Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('AgriConnect could not be started.`n`nPlease check the launcher window for details.','AgriConnect','OK','Error')"

pause
exit /b 1
