@echo off
REM ============================================================
REM  Banco del Master — versione DEBUG
REM  Uguale all'app, ma tiene aperta la console per vedere
REM  eventuali errori. Usala se il Banco non parte.
REM ============================================================
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m aedo.admin
) else (
    python -m aedo.admin
)

echo.
echo   Banco del Master arrestato.
pause
