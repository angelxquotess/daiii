@echo off
REM ============================================================
REM  start_quasi.bat — avvia QUASI / MARK XXXIX-OR in HEADLESS
REM  (nessuna GUI, ma con tutte le funzioni: voce + tool calling
REM   + dashboard messaggi cross-platform in modalita' console).
REM
REM  Uso:
REM     1) Doppio click su start_quasi.bat
REM     2) Oppure da prompt: start_quasi.bat
REM ============================================================

setlocal ENABLEDELAYEDEXPANSION
cd /d "%~dp0"

REM ---- Cerca un interprete Python disponibile ----------------
set "PYEXE="
where py >nul 2>nul
if %errorlevel%==0 (
    set "PYEXE=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 set "PYEXE=python"
)

if not defined PYEXE (
    echo [ERRORE] Python non trovato nel PATH. Installa Python 3.11/3.12.
    pause
    exit /b 1
)

REM ---- (opzionale) installa dipendenze al primo avvio --------
if not exist ".deps_ok" (
    echo Installo le dipendenze (solo la prima volta)...
    %PYEXE% -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        echo [ATTENZIONE] alcune dipendenze non sono state installate.
    ) else (
        echo. > .deps_ok
    )
)

REM ---- Limita uso CPU del processo Python --------------------
REM     priority "BelowNormal" + affinita' su 2 core max riduce
REM     drasticamente il carico senza modificare la logica.
echo Avvio QUASI in modalita' HEADLESS (priorita' bassa)...
start "QUASI" /B /BELOWNORMAL %PYEXE% main_headless.py
exit /b 0
