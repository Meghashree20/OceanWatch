@echo off
echo ==============================================
echo       OceanWatch - Starting Services
echo ==============================================

echo Starting FastAPI Backend on http://127.0.0.1:8000 ...
start "OceanWatch Backend" cmd /k "cd /d "%~dp0backend" && venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo Starting Vite Frontend on http://localhost:5173 ...
start "OceanWatch Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo All services launched!
echo Backend API Docs: http://127.0.0.1:8000/docs
echo Frontend Web App: http://localhost:5173
pause

