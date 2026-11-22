@echo off
echo ===================================================
echo Running Veriqoo + LabelLens Test Suite
echo ===================================================
cd /d "%~dp0Product_commodities_packaging_complinace_check\Veriqoo"
set PYTHONPATH=.
pytest tests/test_food_safety_labellens.py tests/test_phase8a_api.py -v
pause
