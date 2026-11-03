@echo off
title BOPEL AUTOMATION TOOLKIT
cd /d "%~dp0"

REM =============================
REM UTF-8 output
REM =============================
chcp 65001 >nul 2>nul

REM =============================
REM Auto-relaunch ke Windows Terminal (kalau ada)
REM =============================
if defined WT_SESSION (
    REM Sudah di Windows Terminal, lanjut
    goto :run
)
where wt.exe >nul 2>nul
if %errorlevel%==0 (
    wt.exe "%~f0"
    exit /b
)

:run
REM =============================
REM Cek Python ada atau enggak
REM =============================
where python >nul 2>nul
if %errorlevel%==0 (
    cls
    python main.py
    goto :selesai
)

where py >nul 2>nul
if %errorlevel%==0 (
    cls
    py main.py
    goto :selesai
)

echo.
echo ❌ Python gak ketemu di komputer ini.
echo    Install dulu dari https://www.python.org/downloads/
echo    Pas install, centang "Add Python to PATH".
echo.
pause
exit /b 1

:selesai
echo.
pause
