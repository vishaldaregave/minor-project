"""FoodSafetyService — Unified Food Label & Additives Safety Intelligence Service.

Combines multimodal vision OCR, EFSA OpenFoodTox retrieval, deterministic chemical
interaction analysis, and AI reasoning to produce instant, actionable health verdicts.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from typing import Any, Dict, List, Optional

from backend.app.config import get_settings
from backend.app.services.food_safety.e_number_map import E_NUMBER_MAP, normalise_e_number
from backend.app.services.food_safety.efsa_database import EFSADatabase
from backend.app.services.food_safety.schemas import (
    AnalysisResult,
    HarmfulAdditive,
    Ingredient,
    Nutrition,
    Preservative,
)
from backend.app.services.food_safety.scorer import compute_health_score, score_for_kids

logger = logging.getLogger(__name__)

# Known high-concern additives and interactions
HIGH_CONCERN_SUBSTANCES: Dict[str, Dict[str, Any]] = {
    "E102": {
        "name": "Tartrazine",
        "why_harmful": "Synthetic azo dye linked to hyperactivity in children, allergic reactions, and asthma triggers (EFSA ADI: 7.5 mg/kg bw/day).",
        "safe_limit": "7.5 mg/kg body weight/day (EFSA)",
        "kids_concern": True,
        "kids_note": "Linked to attention-deficit hyperactivity disorder (ADHD) and behavioral issues in children.",
    },
    "E110": {
        "name": "Sunset Yellow FCF",
        "why_harmful": "Synthetic petroleum-derived dye associated with hyperactivity in children and urticaria. Requires EU warning label.",
        "safe_limit": "4 mg/kg body weight/day (EFSA)",
        "kids_concern": True,
        "kids_note": "May trigger severe hyperactivity and attention issues in young children.",
    },
    "E122": {
        "name": "Carmoisine / Azorubine",
        "why_harmful": "Red azo dye banned in several jurisdictions; associated with hyperactivity and histamine reactions.",
        "safe_limit": "4 mg/kg body weight/day (EFSA)",
        "kids_concern": True,
        "kids_note": "Included in the Southampton study of additives that provoke child hyperactivity.",
    },
    "E129": {
        "name": "Allura Red AC",
        "why_harmful": "Synthetic azo dye; linked to gut inflammation, allergic reactions, and child hyperactivity.",
        "safe_limit": "7 mg/kg body weight/day (EFSA)",
        "kids_concern": True,
        "kids_note": "Strictly regulated in child diets; triggers hyperactivity.",
    },
    "E171": {
        "name": "Titanium Dioxide",
        "why_harmful": "Nanoparticle food additive banned across the European Union due to genotoxicity concerns (cannot exclude DNA damage).",
        "safe_limit": "No safe level established (Banned in EU)",
        "kids_concern": True,
        "kids_note": "Potential genotoxicity and cellular accumulation.",
    },
    "E211": {
        "name": "Sodium Benzoate",
        "why_harmful": "Preservative that can react with Ascorbic Acid (Vitamin C) to form carcinogenic benzene.",
        "safe_limit": "5 mg/kg body weight/day (EFSA)",
        "kids_concern": True,
        "kids_note": "Combined with artificial colors, significantly increases child hyperactivity.",
    },
    "E319": {
        "name": "TBHQ (Tertiary Butylhydroquinone)",
        "why_harmful": "Synthetic antioxidant preservative; high doses in animal studies linked to stomach tumors and cellular damage.",
        "safe_limit": "0.7 mg/kg body weight/day (EFSA)",
        "kids_concern": True,
        "kids_note": "May affect immune response and cellular health.",
    },
    "E320": {
        "name": "BHA (Butylated Hydroxyanisole)",
        "why_harmful": "Synthetic antioxidant classified as reasonably anticipated to be a human carcinogen by the US NTP.",
        "safe_limit": "1.0 mg/kg body weight/day (EFSA)",
        "kids_concern": True,
        "kids_note": "Endocrine disruptor with potential metabolic effects.",
    },
    "E621": {
        "name": "Monosodium Glutamate (MSG)",
        "why_harmful": "Excitotoxin flavour enhancer; can trigger headaches, sweating, and numbness in sensitive individuals.",
        "safe_limit": "30 mg/kg body weight/day (EFSA)",
        "kids_concern": False,
        "kids_note": None,
    },
    "E951": {
        "name": "Aspartame",
        "why_harmful": "Artificial non-nutritive sweetener classified as possibly carcinogenic to humans (IARC Group 2B). Contains phenylalanine.",
        "safe_limit": "40 mg/kg body weight/day (WHO/EFSA)",
        "kids_concern": True,
        "kids_note": "Not recommended for children; disrupts developing metabolic signaling.",
    },
}


class FoodSafetyService:
    """Core service providing food safety analysis and EFSA additive validation."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.efsa_db = EFSADatabase.get_instance()
        self._gemini_client = None

    def _get_gemini_client(self):
        """Lazy load Gemini client if configured."""
        if self._gemini_client is None:
            api_key = (self.settings.gemini_api_key or "").strip()
            if api_key:
                try:
                    from google import genai
                    self._gemini_client = genai.Client(api_key=api_key)
                except Exception as exc:
                    logger.warning("Failed to initialize google.genai Client: %s", exc)
        return self._gemini_client

    def analyze_text(self, ingredients_text: str, product_name: Optional[str] = None) -> AnalysisResult:
        """Perform comprehensive food safety and additive audit on raw ingredients text."""
        cleaned_text = ingredients_text.strip()
        if not cleaned_text:
            return self._build_empty_fallback("No ingredients provided.")

        # 1. Parse individual ingredient tokens
        raw_items = self._split_ingredients(cleaned_text)

        # 2. Extract and resolve EFSA data and context
        efsa_context = self.efsa_db.get_safety_context_for_ingredients(raw_items)

        # 3. Try LLM analysis first (Gemini 2.5 Flash)
        gemini = self._get_gemini_client()
        if gemini:
            try:
                llm_result = self._call_gemini_analysis(cleaned_text, efsa_context, product_name)
                if llm_result:
                    return self._finalize_result(llm_result, raw_items)
            except Exception as exc:
                logger.warning("Gemini analysis failed or rate limited, falling back to deterministic engine: %s", exc)

        # 4. Deterministic Rule-Engine Fallback (100% resilient, offline-safe)
        return self._deterministic_analysis(raw_items, cleaned_text, product_name)

    def analyze_image(self, image_bytes: bytes, content_type: str = "image/jpeg") -> AnalysisResult:
        """Perform multimodal food label extraction and safety analysis from an image."""
        if not image_bytes:
            return self._build_empty_fallback("Empty image provided.")

        gemini = self._get_gemini_client()
        if gemini:
            try:
                # Direct multimodal analysis via Gemini
                prompt = (
                    "You are a food safety expert. Read this food product label image.\n"
                    "Extract the complete ingredient list, E-numbers, nutrition facts per 100g, "
                    "and identify harmful additives and preservatives.\n"
                    "Return ONLY valid JSON matching this exact structure:\n"
                    "{\n"
                    '  "summary": "2-sentence plain-English verdict.",\n'
                    '  "nutrition_per_100g": {"energy_kcal": null, "fat_g": null, "saturated_fat_g": null, "carbohydrates_g": null, "sugars_g": null, "protein_g": null, "salt_g": null, "sodium_mg": null, "fibre_g": null},\n'
                    '  "harmful_additives": [{"name": "Substance Name", "e_number": "E102", "why_harmful": "Reason", "safe_limit_per_day": "7.5 mg/kg bw", "kids_concern": true, "kids_note": "Reason for kids"}],\n'
                    '  "preservatives": [{"name": "Substance Name", "e_number": "E211", "concern_level": "moderate", "note": "Description", "safe_limit_per_day": "5 mg/kg"}],\n'
                    '  "ingredients": [{"name": "Sugar", "category": "Sweetener", "concern_level": "moderate", "safe_limit": "< 25g/day (WHO)", "kids_safe": true, "note": "High sugar content"}],\n'
                    '  "nova_group": 4,\n'
                    '  "overall_concerns": ["High sugar", "Synthetic food dyes"],\n'
                    '  "good_points": ["Source of protein"],\n'
                    '  "kids_verdict": "One clear sentence for parents regarding child safety."\n'
                    "}"
                )
                from google.genai import types
                part = types.Part.from_bytes(data=image_bytes, mime_type=content_type or "image/jpeg")
                response = gemini.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[part, prompt],
                    config={"response_mime_type": "application/json", "temperature": 0.1},
                )
                if response.text:
                    parsed = json.loads(self._clean_json(response.text))
                    return self._finalize_result(parsed, [])
            except Exception as exc:
                logger.warning("Gemini multimodal image analysis failed: %s", exc)

        # Fallback: OCR text extraction via PaddleOCR or heuristic, then analyze text
        extracted_text = self._extract_ocr_fallback(image_bytes)
        return self.analyze_text(extracted_text or "Packaged food commodity label")

    def _split_ingredients(self, text: str) -> List[str]:
        """Split a raw ingredient declaration into individual ingredients."""
        # Remove prefix like "Ingredients:", "Contains:", etc.
        cleaned = re.sub(r"^(ingredients|contains|ingredients\s*list)\s*[:\-]\s*", "", text, flags=re.IGNORECASE)
        # Split on commas, semicolons, bullets, and handle parentheses
        tokens = re.split(r"[,;•\n\r]+", cleaned)
        results = []
        for t in tokens:
            item = t.strip()
            if item and len(item) > 1 and not re.match(r"^\d+%$", item):
                results.append(item)
        return results

    def _call_gemini_analysis(self, text: str, efsa_context: str, product_name: Optional[str]) -> Optional[Dict[str, Any]]:
        gemini = self._get_gemini_client()
        if not gemini:
            return None

        prompt = (
            f"You are a senior food safety scientist and EFSA regulatory expert.\n"
            f"Analyse this food ingredient list carefully.\n"
            f"Product: {product_name or 'Packaged Food'}\n\n"
            f"--- INGREDIENTS ---\n{text}\n\n"
            f"--- EFSA OPENFOODTOX DATABASE CONTEXT ---\n{efsa_context}\n\n"
            f"Return ONLY valid JSON matching this exact structure:\n"
            f"{{\n"
            f'  "summary": "2-sentence plain-English verdict. Sentence 1: overall assessment. Sentence 2: key safety/health concern.",\n'
            f'  "nutrition_per_100g": {{"energy_kcal": null, "fat_g": null, "saturated_fat_g": null, "carbohydrates_g": null, "sugars_g": null, "protein_g": null, "salt_g": null, "sodium_mg": null, "fibre_g": null}},\n'
            f'  "harmful_additives": [{{"name": "...", "e_number": "E...", "why_harmful": "...", "safe_limit_per_day": "...", "kids_concern": true, "kids_note": "..."}}],\n'
            f'  "preservatives": [{{"name": "...", "e_number": "E...", "concern_level": "safe|moderate|harmful", "note": "...", "safe_limit_per_day": "..."}}],\n'
            f'  "ingredients": [{{"name": "...", "category": "Base ingredient|Fat|Sweetener|Mineral|Synthetic colour|Preservative|Flavouring|Emulsifier|Acidity regulator|Antioxidant|Thickener|Other additive", "concern_level": "safe|moderate|harmful", "safe_limit": "...", "kids_safe": true, "note": "..."}}],\n'
            f'  "nova_group": 1|2|3|4,\n'
            f'  "overall_concerns": ["..."],\n'
            f'  "good_points": ["..."],\n'
            f'  "kids_verdict": "One clear sentence specifically for parents on whether this is safe for kids."\n'
            f"}}"
        )
        response = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"response_mime_type": "application/json", "temperature": 0.1},
        )
        if response.text:
            return json.loads(self._clean_json(response.text))
        return None

    def _deterministic_analysis(
        self, items: List[str], raw_text: str, product_name: Optional[str]
    ) -> AnalysisResult:
        """Rule-based EFSA analysis ensuring complete robustness even when offline or unauthenticated."""
        harmful_additives: List[HarmfulAdditive] = []
        preservatives: List[Preservative] = []
        ingredients_list: List[Ingredient] = []
        overall_concerns: List[str] = []
        good_points: List[str] = []
        nova_group = 1

        has_benzene_risk = False
        has_sugar = False
        has_artificial_color = False
        has_high_processing = False

        for item_str in items:
            lowered = item_str.lower()
            e_match = normalise_e_number(item_str)
            e_code = e_match["e_number"] if e_match else None
            canonical_name = e_match["name"] if e_match else item_str

            concern = "safe"
            category = "Base ingredient"
            safe_limit = "No established limit"
            kids_safe = True
            note = f"Standard dietary ingredient ({canonical_name})."

            # Check known high-concern dictionary
            if e_code and e_code in HIGH_CONCERN_SUBSTANCES:
                sub_info = HIGH_CONCERN_SUBSTANCES[e_code]
                concern = "harmful"
                category = "Synthetic colour" if "E1" in e_code else "Preservative" if "E2" in e_code else "Other additive"
                safe_limit = sub_info["safe_limit"]
                kids_safe = not sub_info["kids_concern"]
                note = sub_info["why_harmful"]

                harmful_additives.append(
                    HarmfulAdditive(
                        name=sub_info["name"],
                        e_number=e_code,
                        why_harmful=sub_info["why_harmful"],
                        safe_limit_per_day=sub_info["safe_limit"],
                        kids_concern=sub_info["kids_concern"],
                        kids_note=sub_info["kids_note"],
                    )
                )
                if sub_info["kids_concern"]:
                    has_artificial_color = True
                nova_group = 4

            # Check preservative characteristics
            if "preservative" in lowered or (e_code and e_code.startswith("E2")):
                category = "Preservative"
                pres_concern = "harmful" if (e_code in ("E211", "E250", "E251")) else "moderate"
                preservatives.append(
                    Preservative(
                        name=canonical_name,
                        e_number=e_code,
                        concern_level=pres_concern,
                        note=note,
                        safe_limit_per_day=safe_limit,
                    )
                )

            # Check sugar & sweeteners
            if any(s in lowered for s in ("sugar", "glucose", "fructose", "syrup", "sucrose")):
                category = "Sweetener"
                concern = "moderate"
                safe_limit = "< 25g/day free sugars (WHO)"
                has_sugar = True
                note = "Contributes to free sugar intake."

            # Check fats & oils
            if any(f in lowered for f in ("oil", "fat", "palm", "butter")):
                category = "Fat"
                if "palm" in lowered or "hydrogenated" in lowered:
                    concern = "harmful"
                    note = "High in saturated/trans fatty acids."
                    overall_concerns.append("Contains highly processed or saturated fats.")
                else:
                    note = "Edible fat source."

            # EFSA Database substance lookup
            efsa_hits = self.efsa_db.search_substance(item_str, limit=1)
            if efsa_hits:
                hit = efsa_hits[0]
                if hit.get("adi_lower") is not None:
                    safe_limit = f"{hit['adi_lower']} {hit.get('adi_unit', '')}".strip()

            ingredients_list.append(
                Ingredient(
                    name=item_str,
                    category=category,
                    safe_limit=safe_limit,
                    concern_level=concern,
                    kids_safe=kids_safe,
                    note=note,
                )
            )

        # Check hazardous interaction: Sodium Benzoate (E211) + Ascorbic Acid (Vitamin C / E300)
        has_benzoate = any("e211" in i.name.lower() or "benzoate" in i.name.lower() for i in ingredients_list)
        has_ascorbic = any("e300" in i.name.lower() or "ascorbic" in i.name.lower() or "vitamin c" in i.name.lower() for i in ingredients_list)
        if has_benzoate and has_ascorbic:
            has_benzene_risk = True
            overall_concerns.append("DANGEROUS INTERACTION: Sodium Benzoate combined with Ascorbic Acid (Vitamin C) can form carcinogenic benzene.")

        if has_sugar:
            overall_concerns.append("High glycemic risk from added sugars.")
        if has_artificial_color:
            overall_concerns.append("Contains synthetic dyes associated with child hyperactivity.")

        if len(ingredients_list) <= 5 and not harmful_additives:
            good_points.append("Clean label: minimal ingredients with no confirmed harmful additives.")
            nova_group = 1
        elif len(harmful_additives) > 0 or len(preservatives) > 1:
            nova_group = 4

        # Assemble summary and verdicts
        if harmful_additives:
            summary = (
                f"This product contains {len(harmful_additives)} additive(s) with confirmed health concerns, "
                f"including {harmful_additives[0].name}. Regular consumption is not recommended, especially for children."
            )
            kids_verdict = "Avoid: Contains additives linked to hyperactivity, allergic sensitivity, or metabolic stress."
        elif preservatives:
            summary = (
                f"This product is moderately processed with {len(preservatives)} preservative(s). "
                "Safe for occasional adult consumption within standard dietary guidelines."
            )
            kids_verdict = "Suitable in moderation; monitor cumulative intake of processed additives."
        else:
            summary = "This product contains primarily whole and standard ingredients with no critical additive alerts."
            kids_verdict = "Safe for children as part of a balanced diet."

        partial_dict = {
            "summary": summary,
            "nutrition_per_100g": {},
            "harmful_additives": [h.model_dump() for h in harmful_additives],
            "preservatives": [p.model_dump() for p in preservatives],
            "ingredients": [i.model_dump() for i in ingredients_list],
            "nova_group": nova_group,
            "overall_concerns": overall_concerns,
            "good_points": good_points,
            "kids_verdict": kids_verdict,
        }

        return self._finalize_result(partial_dict, items)

    def _finalize_result(self, raw_data: Dict[str, Any], raw_items: List[str]) -> AnalysisResult:
        """Compute final scores and wrap in verified AnalysisResult model."""
        health_score = compute_health_score(raw_data)
        kids_score = score_for_kids(raw_data)

        # Parse nutrition sub-model safely
        nut_raw = raw_data.get("nutrition_per_100g")
        nutrition_obj = None
        if isinstance(nut_raw, dict):
            nutrition_obj = Nutrition(**{k: v for k, v in nut_raw.items() if hasattr(Nutrition, k)})

        # Parse harmful additives
        harmful_list = [
            HarmfulAdditive(**h) for h in (raw_data.get("harmful_additives") or [])
            if isinstance(h, dict) and "name" in h and "why_harmful" in h
        ]

        # Parse preservatives
        preservatives_list = [
            Preservative(**p) for p in (raw_data.get("preservatives") or [])
            if isinstance(p, dict) and "name" in p and "note" in p
        ]

        # Parse ingredients
        ingredients_list = [
            Ingredient(**i) for i in (raw_data.get("ingredients") or [])
            if isinstance(i, dict) and "name" in i
        ]

        nova = raw_data.get("nova_group")
        nova_val = int(nova) if (nova and str(nova).isdigit() and 1 <= int(nova) <= 4) else None

        return AnalysisResult(
            health_score=health_score,
            kids_score=kids_score,
            summary=raw_data.get("summary") or "Food label analysis completed.",
            kids_verdict=raw_data.get("kids_verdict"),
            nutrition_per_100g=nutrition_obj,
            harmful_additives=harmful_list,
            preservatives=preservatives_list,
            ingredients=ingredients_list,
            nova_group=nova_val,
            overall_concerns=raw_data.get("overall_concerns") or [],
            good_points=raw_data.get("good_points") or [],
        )

    def _clean_json(self, text: str) -> str:
        """Strip markdown code fences and whitespace from LLM output."""
        t = text.strip()
        t = re.sub(r"^```json\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"^```\s*", "", t)
        t = re.sub(r"```$", "", t).strip()
        return t

    def _extract_ocr_fallback(self, image_bytes: bytes) -> str:
        """Attempt local OCR extraction via PaddleOCR if available."""
        try:
            from backend.app.services.ocr.engine import get_ocr_engine
            engine = get_ocr_engine()
            lines = engine.extract_text_lines(image_bytes)
            return " ".join([l.text for l in lines])
        except Exception:
            return ""

    def _build_empty_fallback(self, reason: str) -> AnalysisResult:
        return AnalysisResult(
            health_score=50,
            kids_score=50,
            summary=reason,
            kids_verdict="Cannot determine safety without readable ingredients.",
            harmful_additives=[],
            preservatives=[],
            ingredients=[],
            nova_group=None,
            overall_concerns=[reason],
            good_points=[],
        )
