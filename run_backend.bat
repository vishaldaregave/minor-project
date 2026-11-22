@echo off
echo ===================================================
echo Starting Unified Veriqoo + LabelLens Backend Server
echo ===================================================
cd /d "%~dp0Product_commodities_packaging_complinace_check\Veriqoo"
set PYTHONPATH=.
echo Server listening at: http://127.0.0.1:8000
echo Swagger UI:          http://127.0.0.1:8000/docs
echo LabelLens Web UI:    http://127.0.0.1:8000/labellens
echo.
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
pause
