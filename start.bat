@echo off
REM Quick Start Script for SGIMI TECNOGAS
REM This script sets up and runs the system on Windows

echo =========================================
echo SGIMI TECNOGAS - Quick Start Script
echo =========================================

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python not found. Please install Python 3.8+
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Python version: %PYTHON_VERSION%

REM Create virtual environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt

REM Create logs directory
if not exist "logs" mkdir logs

REM Run application
echo.
echo Starting SGIMI TECNOGAS...
echo Default credentials: admin@tecnogas.com / admin123
echo.
python main.py

pause
