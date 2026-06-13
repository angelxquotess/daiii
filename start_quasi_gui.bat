@echo off
REM start_quasi_gui.bat — avvia QUASI in modalita' GUI (PyQt6).
setlocal ENABLEDELAYEDEXPANSION
cd /d "%~dp0"

set "PYEXE="
where py >nul 2>nul && set "PYEXE=py -3"
if not defined PYEXE (
    where python >nul 2>nul && set "PYEXE=python"
)
if not defined PYEXE (
    echo [ERRORE] Python non trovato nel PATH.
    pause
    exit /b 1
)

if not exist ".deps_ok" (
    echo Installo le dipendenze (solo la prima volta)...
    %PYEXE% -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        echo [ATTENZIONE] alcune dipendenze non sono state installate.
    ) else (
        echo. > .deps_ok
    )
)

echo Avvio QUASI in modalita' GUI...
start "QUASI" /BELOWNORMAL %PYEXE% main.py
exit /b 0
