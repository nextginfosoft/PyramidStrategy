@echo off
set "PROJECT_DIR=%~dp0"

echo Starting PyramidStrategy Backend...
start "PyramidStrategy Backend" cmd /k "cd /d %PROJECT_DIR%backend && venv\Scripts\activate && uvicorn app.main:app --reload --port 8000"

echo Starting PyramidStrategy Frontend...
start "PyramidStrategy Frontend" cmd /k "cd /d %PROJECT_DIR%frontend && npm run dev"

echo Both servers have been launched in separate terminal windows.
pause
