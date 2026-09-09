@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Please install the project environment first. See README.md.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m streamlit run src/ordercheck_app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
pause
