@echo off
cd /d "%~dp0"
set PYTHONPATH=.
set PYTHON_EXE=C:\Users\vishal\AppData\Local\Python\bin\python.exe
if not exist "%PYTHON_EXE%" set PYTHON_EXE=python

echo ==========================================================
echo Starting Veriqoo Backend + LabelLens Food Safety Engine
echo Local API Docs:    http://127.0.0.1:8000/docs
echo Flutter Web App:   http://127.0.0.1:8000/app/
echo LabelLens Portal:  http://127.0.0.1:8000/labellens
echo ==========================================================
"%PYTHON_EXE%" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
pause
