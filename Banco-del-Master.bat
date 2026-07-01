@echo off
REM ============================================================
REM  Banco del Master — app di Aedo
REM  Doppio click: si apre la finestra del Banco (niente browser).
REM  Da li' accendi il resto (bot Discord, API, web giocatore).
REM ============================================================
cd /d "%~dp0"

REM pythonw = nessuna finestra nera del terminale, solo l'app.
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" -m aedo.admin
) else (
    start "" pythonw -m aedo.admin
)
