@echo off
title F1 Telemetry Launcher
echo.
echo ========================================================
echo         F1 TELEMETRY  -  Multi-Game Dashboard
echo         Supports F1 2019 . F1 2020 . F1 2021
echo ========================================================
echo.

REM Try to find Python
where python >nul 2>&1
if %errorlevel% equ 0 (
    python "%~dp0launch.py"
) else (
    where python3 >nul 2>&1
    if %errorlevel% equ 0 (
        python3 "%~dp0launch.py"
    ) else (
        echo [ERROR] Python is not installed or not in PATH.
        echo.
        echo Please install Python 3.8+ from https://www.python.org/downloads/
        echo Make sure to check "Add Python to PATH" during installation.
        echo.
        pause
        exit /b 1
    )
)
pause
