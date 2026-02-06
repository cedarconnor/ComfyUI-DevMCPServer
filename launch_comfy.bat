@echo off
REM Helper script to launch ComfyUI with logging enabled
REM Usage: launch_comfy.bat [additional args]

REM Load .env if present (simple parsing)
if exist "%~dp0.env" (
    for /f "usebackq tokens=1,* delims==" %%a in ("%~dp0.env") do (
        if not "%%a"=="" if not "%%a:~0,1%"=="#" set "%%a=%%b"
    )
)

REM Check COMFYUI_PATH is set
if "%COMFYUI_PATH%"=="" (
    echo Error: COMFYUI_PATH not set
    echo Either set it in .env or set COMFYUI_PATH=C:\path\to\ComfyUI
    exit /b 1
)

REM Default log location
if "%COMFYUI_LOG%"=="" set "COMFYUI_LOG=%COMFYUI_PATH%\comfyui.log"

echo Starting ComfyUI...
echo   Path: %COMFYUI_PATH%
echo   Log:  %COMFYUI_LOG%
echo.

cd /d "%COMFYUI_PATH%"

REM Check for venv
set PYTHON=python
if exist "venv\Scripts\python.exe" set PYTHON=venv\Scripts\python.exe
if exist ".venv\Scripts\python.exe" set PYTHON=.venv\Scripts\python.exe

echo Using Python: %PYTHON%
echo Additional args: %*
echo.
echo --- ComfyUI Output ---

REM Run with PowerShell's Tee-Object to capture output
powershell -Command "& { %PYTHON% main.py %* 2>&1 | Tee-Object -FilePath '%COMFYUI_LOG%' }"
