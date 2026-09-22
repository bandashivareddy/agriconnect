@echo off
setlocal

title AgriConnect Stopper

cls

echo.
echo ============================================================
echo                    AGRICONNECT
echo                  Application Stopper
echo ============================================================
echo.
echo Stopping AgriConnect...
echo.

echo [1/4] Stopping Cloudflare tunnel...

taskkill /FI "WINDOWTITLE eq AgriConnect Cloudflare*" /T /F >nul 2>&1

if errorlevel 1 (
    echo        Cloudflare was not running or could not be stopped.
    echo        If its window is still open, press Ctrl+C there.
) else (
    echo        Cloudflare stopped. The public tunnel is closed.
)

echo.
echo [2/4] Stopping frontend...

taskkill /FI "WINDOWTITLE eq AgriConnect Frontend*" /T /F >nul 2>&1

if errorlevel 1 (
    echo        Frontend was not running.
) else (
    echo        Frontend stopped.
)

echo.

echo [3/4] Stopping backend...

taskkill /FI "WINDOWTITLE eq AgriConnect Backend*" /T /F >nul 2>&1

if errorlevel 1 (
    echo        Backend was not running.
) else (
    echo        Backend stopped.
)

echo.

echo [4/4] PostgreSQL...

sc query "postgresql-x64-18" | findstr /I "RUNNING" >nul 2>&1

if errorlevel 1 (
    echo        PostgreSQL is not running.
) else (
    echo        PostgreSQL remains running.
)

echo.
echo ============================================================
echo.
echo                 AGRICONNECT STOPPED
echo.
echo ============================================================
echo.
echo PostgreSQL has been left running.
echo.
echo You can start AgriConnect again using:
echo start_agriconnect.bat
echo.

powershell -NoProfile -Command ^
"Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('AgriConnect has been stopped.`n`nPostgreSQL remains running.','AgriConnect','OK','Information')"

pause
exit /b 0