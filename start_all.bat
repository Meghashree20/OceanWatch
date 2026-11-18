@echo off
setlocal
set "ROOT=%~dp0"
set "BACKEND_DIR=%ROOT%backend"
set "FRONTEND_DIR=%ROOT%frontend"
set "BACKEND_PYTHON=%BACKEND_DIR%\.venv-stage25\Scripts\python.exe"

if not exist "%BACKEND_PYTHON%" set "BACKEND_PYTHON=%BACKEND_DIR%\venv\Scripts\python.exe"
if not exist "%BACKEND_PYTHON%" (
  echo OceanWatch backend Python environment was not found.
  echo Create backend\venv or install backend\.venv-stage25.
  exit /b 1
)
if not defined AUTH_JWT_SECRET (
  echo AUTH_JWT_SECRET is required and must be at least 32 characters.
  echo In PowerShell, generate it with the Python command in docs\OCEANWATCH_COMPLETE_INTEGRATION_AUDIT.md.
  echo Set AUTH_JWT_SECRET in this session and run start_all.bat again.
  exit /b 1
)
if not exist "%FRONTEND_DIR%\node_modules\.bin\vite.cmd" (
  echo Frontend dependencies are missing. Run npm.cmd install in frontend first.
  exit /b 1
)

echo Starting FastAPI on http://127.0.0.1:8000 ...
start "OceanWatch Backend" cmd /k "cd /d ""%BACKEND_DIR%"" && set OCEANWATCH_ENV=development && ""%BACKEND_PYTHON%"" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo Starting Vite on http://127.0.0.1:5173 ...
start "OceanWatch Frontend" cmd /k "cd /d ""%FRONTEND_DIR%"" && npm.cmd run dev -- --host 127.0.0.1 --port 5173"

echo Both services launched.
echo API docs: http://127.0.0.1:8000/docs
echo Frontend: http://127.0.0.1:5173
endlocal
