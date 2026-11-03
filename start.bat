@echo off
REM =============================
REM BOPEL — versi pywebview (desktop app UI web)
REM (Textual TUI lama: start_tui.bat)
REM
REM Dijalankan dengan pythonw.exe + `start` (DETACHED) supaya TIDAK ada
REM console window yang menempel ke app.py — fix sesi 2026-08-14:
REM sebelumnya `python app.py` (python.exe) selalu membuka console
REM (bukti: core/launcher.py sudah CREATE_NO_WINDOW, jadi console bukan
REM dari subprocess tool). Kalau mau lihat log/error di console saat
REM development: pakai start_debug.bat (python.exe biasa).
REM =============================
cd /d "%~dp0"

where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw app.py
    exit /b 0
)

where python >nul 2>nul
if %errorlevel%==0 (
    start "" python app.py
    exit /b 0
)

where py >nul 2>nul
if %errorlevel%==0 (
    start "" py app.py
    exit /b 0
)

echo.
echo [ERROR] Python gak ketemu di komputer ini.
echo    Install dulu dari https://www.python.org/downloads/
echo    Pas install, centang "Add Python to PATH".
echo.
pause
exit /b 1
