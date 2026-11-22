"""Unit & Integration Test Suite for Food Safety & Additives Intelligence (LabelLens Feature)."""

from __future__ import annotations

import io
import unittest
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.main import app
from backend.app.services.food_safety.e_number_map import normalise_e_number
from backend.app.services.food_safety.efsa_database import EFSADatabase
from backend.app.services.food_safety.scorer import compute_health_score, score_for_kids
from backend.app.services.food_safety.service import FoodSafetyService


def _create_sample_label_image(width: int = 300, height: int = 200) -> bytes:
    """Generate dummy label image for multipart upload testing."""
    img = Image.new("RGB", (width, height), color=(240, 240, 240))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class FoodSafetyLabelLensTestCase(unittest.TestCase):
    """Test suite validating LabelLens integration in Veriqoo."""

    def setUp(self) -> None:
        self.client = TestClient(app)
        self.service = FoodSafetyService()
        self.efsa_db = EFSADatabase.get_instance()

    def test_e_number_normalizer(self) -> None:
        """Test canonical resolution of E-numbers."""
        res1 = normalise_e_number("E102")
        self.assertIsNotNone(res1)
        self.assertEqual(res1["e_number"], "E102")
        self.assertIn("Tartrazine", res1["name"])

        res2 = normalise_e_number("INS 211")
        self.assertIsNotNone(res2)
        self.assertEqual(res2["e_number"], "E211")
        self.assertIn("Sodium Benzoate", res2["name"])

        res3 = normalise_e_number("contains Sunset Yellow FCF")
        self.assertIsNotNone(res3)
        self.assertEqual(res3["e_number"], "E110")

    def test_efsa_database_search(self) -> None:
        """Test EFSA OpenFoodTox database retrieval."""
        results = self.efsa_db.search_substance("E102", limit=5)
        self.assertTrue(len(results) > 0)
        top = results[0]
        self.assertIn("Tartrazine", top.get("name", ""))

        # API Search endpoint
        response = self.client.get("/api/v1/food-safety/substances/search?q=benzoic")
        self.assertEqual(response.status_code, 200)
        items = response.json()
        self.assertTrue(len(items) > 0)

    def test_analyse_harmful_additives_and_benzene_interaction(self) -> None:
        """Test detection of harmful additives and benzene risk from E211 + Vitamin C."""
        ingredients_text = (
            "Carbonated water, High fructose corn syrup, Citric acid (E330), "
            "Sodium benzoate (E211), Ascorbic acid (Vitamin C / E300), "
            "Tartrazine (E102), Sunset yellow (E110), Artificial flavours"
        )
        payload = {"ingredients_text": ingredients_text, "product_name": "Orange Soda"}
        response = self.client.post("/api/v1/food-safety/analyse-text", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Health score must be penalized due to harmful additives and preservatives
        self.assertLess(data["health_score"], 60)
        self.assertLess(data["kids_score"], 40)

        # Harmful additives detected
        harmful_names = [h["name"].lower() for h in data["harmful_additives"]]
        self.assertTrue(any("tartrazine" in n for n in harmful_names))
        self.assertTrue(any("sunset" in n for n in harmful_names))

        # Kids concern flag should be True for azo dyes
        for h in data["harmful_additives"]:
            if "tartrazine" in h["name"].lower():
                self.assertTrue(h["kids_concern"])

        # Hazardous interaction check: Sodium Benzoate + Ascorbic Acid
        concerns_text = " ".join(data.get("overall_concerns", []))
        self.assertTrue("benzene" in concerns_text.lower() or "interaction" in concerns_text.lower())

        # NOVA classification
        self.assertEqual(data["nova_group"], 4)
        self.assertIn("Avoid", data["kids_verdict"])

    def test_analyse_clean_label_food(self) -> None:
        """Test clean whole food label receives clean label bonus and high score."""
        ingredients_text = "Rolled whole grain oats, raw almonds, organic chia seeds, dried apples, cinnamon powder"
        payload = {"ingredients_text": ingredients_text, "product_name": "Organic Muesli"}
        response = self.client.post("/api/v1/food-safety/analyse-text", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Clean label should have high score
        self.assertGreaterEqual(data["health_score"], 75)
        self.assertGreaterEqual(data["kids_score"], 75)
        self.assertEqual(len(data["harmful_additives"]), 0)
        self.assertEqual(len(data["preservatives"]), 0)
        self.assertIn("Safe for children", data["kids_verdict"])

    def test_direct_labellens_api_analyse_endpoint(self) -> None:
        """Test POST /api/analyse for 100% backward compatibility with LabelLens UI."""
        img_bytes = _create_sample_label_image()
        response = self.client.post(
            "/api/analyse",
            files={"image": ("label.jpg", img_bytes, "image/jpeg")},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("health_score", data)
        self.assertIn("kids_score", data)
        self.assertIn("summary", data)
        self.assertIn("harmful_additives", data)
        self.assertIn("preservatives", data)
        self.assertIn("ingredients", data)

    def test_v1_food_safety_image_upload(self) -> None:
        """Test POST /api/v1/food-safety/analyse multipart upload."""
        img_bytes = _create_sample_label_image()
        response = self.client.post(
            "/api/v1/food-safety/analyse",
            files={"image": ("nutrition_label.png", img_bytes, "image/png")},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("health_score", data)
        self.assertIn("kids_score", data)
