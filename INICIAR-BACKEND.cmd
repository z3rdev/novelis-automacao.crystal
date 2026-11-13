@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-local-backend.ps1"
set "NOVELIS_START_EXIT=%ERRORLEVEL%"
if not "%NOVELIS_START_EXIT%"=="0" (
  echo.
  echo O erro fica registrado em runtime\logs\backend-local.
  pause
)
exit /b %NOVELIS_START_EXIT%
