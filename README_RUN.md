# Quick Run Guide — Veriqoo + LabelLens Feature

This project unifies **Veriqoo** (Legal Metrology Packaged Commodity Compliance) and **LabelLens** (Food Safety, EFSA Additives & Child Health Intelligence) into a single integrated system.

---

## 1. Run the Backend Server

Double click [`run_backend.bat`](file:///D:/Development/Minor%20Projezt/run_backend.bat) or run from PowerShell:

```powershell
cd "D:\Development\Minor Projezt\Product_commodities_packaging_complinace_check\Veriqoo"
$env:PYTHONPATH="."
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Once running:
- **Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **LabelLens Web UI**: [http://127.0.0.1:8000/labellens](http://127.0.0.1:8000/labellens)
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 2. Food Safety & Additives API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/food-safety/analyse` | `POST` | Upload food label photo (`image` multipart file) |
| `/api/v1/food-safety/analyse-text` | `POST` | Audit raw ingredients text JSON payload |
| `/api/v1/food-safety/substances/search?q={query}` | `GET` | Search 3,175+ EFSA OpenFoodTox substances |
| `/api/analyse` | `POST` | Direct compatibility route for LabelLens web clients |

### Quick Test via cURL / PowerShell:
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/food-safety/analyse-text" -Method Post -ContentType "application/json" -Body '{"ingredients_text": "Sugar, Tartrazine (E102), Sodium benzoate (E211), Ascorbic acid (Vitamin C)"}'
```

---

## 3. Run the Test Suite

Double click [`run_tests.bat`](file:///D:/Development/Minor%20Projezt/run_tests.bat) or run:

```powershell
cd "D:\Development\Minor Projezt\Product_commodities_packaging_complinace_check\Veriqoo"
$env:PYTHONPATH="."
pytest tests/test_food_safety_labellens.py tests/test_phase8a_api.py -v
```

---

## 4. Run the Flutter Application

```powershell
cd "D:\Development\Minor Projezt\Product_commodities_packaging_complinace_check\Veriqoo"
flutter run -d chrome
```
*(or target your connected Android/iOS device/emulator)*

The Flutter application includes the **"LabelLens Food Safety"** card on the home screen and a dedicated screen at route `'/food-safety'`.
