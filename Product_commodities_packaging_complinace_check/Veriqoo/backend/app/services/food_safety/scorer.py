"""scorer.py — Evidence-based health score (0–100) and Kids Safety scoring.

Scoring philosophy:
- Start at 100, deduct for risks
- Additives, excessive sugar, salt, and ultra-processing level all penalise
- Natural whole ingredients receive no penalty
- Score bands:
  - 75–100: Good / Safe
  - 50–74:  Moderate / Consume in moderation
  - 25–49:  Poor / High concerns
  - 0–24:   Avoid / Ultra-processed with dangerous additives
"""

from __future__ import annotations

from typing import Any, Dict, List

# Penalties
HARMFUL_ADDITIVE_PENALTY = 18
MODERATE_ADDITIVE_PENALTY = 6
PRESERVATIVE_HARMFUL = 14
PRESERVATIVE_MODERATE = 5
LONG_INGREDIENTS_PENALTY = 5
CLEAN_LABEL_BONUS = 8

# Nutritional thresholds (per 100g)
SUGAR_THRESHOLDS = [
    (5.0, 0),    # <= 5g: no penalty
    (10.0, 5),   # <= 10g: mild
    (20.0, 12),  # <= 20g: moderate
    (30.0, 20),  # <= 30g: high
    (999.0, 28), # > 30g: severe
]

SALT_THRESHOLDS = [
    (0.3, 0),    # <= 0.3g: low (green)
    (0.6, 5),    # <= 0.6g: medium
    (1.0, 12),   # <= 1.0g: high
    (1.5, 18),   # <= 1.5g: very high
    (999.0, 24), # > 1.5g: extreme
]

FAT_THRESHOLDS = [
    (5.0, 0),
    (15.0, 4),
    (25.0, 8),
    (999.0, 13),
]

SATURATED_FAT_THRESHOLDS = [
    (2.0, 0),
    (5.0, 6),
    (10.0, 12),
    (999.0, 18),
]

NOVA_PENALTIES = {
    1: 0,   # Unprocessed / minimally processed
    2: 3,   # Processed culinary ingredients
    3: 8,   # Processed foods
    4: 16,  # Ultra-processed
}

KID_CONCERN_ADDITIVES = {
    "tartrazine", "e102",
    "sunset yellow fcf", "e110",
    "carmoisine", "azorubine", "e122",
    "allura red ac", "e129",
    "quinoline yellow", "e104",
    "ponceau 4r", "e124",
    "sodium benzoate", "e211",
    "potassium benzoate", "e212",
    "aspartame", "e951",
    "acesulfame k", "e950",
    "msg", "monosodium glutamate", "e621",
    "bha", "e320",
    "bht", "e321",
    "tbhq", "e319",
    "caffeine",
    "saccharin", "e954",
    "cyclamate", "e952",
    "titanium dioxide", "e171",
}


def _threshold_penalty(value: float, thresholds: List[tuple]) -> int:
    for limit, penalty in thresholds:
        if value <= limit:
            return penalty
    return thresholds[-1][1]


def compute_health_score(analysis: Dict[str, Any]) -> int:
    """Calculate overall evidence-based health score between 0 and 100."""
    score = 100

    harmful_additives = analysis.get("harmful_additives", []) or []
    preservatives = analysis.get("preservatives", []) or []
    ingredients = analysis.get("ingredients", []) or []
    nutrition = analysis.get("nutrition_per_100g", {}) or {}
    nova = analysis.get("nova_group")

    # 1. Harmful additives penalty
    score -= len(harmful_additives) * HARMFUL_ADDITIVE_PENALTY

    # 2. Moderate additives penalty
    moderate_additives = [
        i for i in ingredients
        if isinstance(i, dict)
        and i.get("concern_level") == "moderate"
        and i.get("category") not in ("Sweetener", "Mineral", "Base ingredient", "Fat")
    ]
    score -= min(len(moderate_additives), 4) * MODERATE_ADDITIVE_PENALTY

    # 3. Preservatives penalty
    for p in preservatives:
        if isinstance(p, dict):
            level = p.get("concern_level", "safe")
            if level == "harmful":
                score -= PRESERVATIVE_HARMFUL
            elif level == "moderate":
                score -= PRESERVATIVE_MODERATE

    # 4. Nutrition penalties
    if isinstance(nutrition, dict):
        sugar = nutrition.get("sugars_g")
        salt = nutrition.get("salt_g") or (
            (nutrition.get("sodium_mg") or 0.0) * 0.0025
        )
        fat = nutrition.get("fat_g")
        sat_fat = nutrition.get("saturated_fat_g")

        if sugar is not None:
            try:
                score -= _threshold_penalty(float(sugar), SUGAR_THRESHOLDS)
            except (ValueError, TypeError):
                pass
        if salt is not None:
            try:
                score -= _threshold_penalty(float(salt), SALT_THRESHOLDS)
            except (ValueError, TypeError):
                pass
        if fat is not None:
            try:
                score -= _threshold_penalty(float(fat), FAT_THRESHOLDS)
            except (ValueError, TypeError):
                pass
        if sat_fat is not None:
            try:
                score -= _threshold_penalty(float(sat_fat), SATURATED_FAT_THRESHOLDS)
            except (ValueError, TypeError):
                pass

    # 5. NOVA Processing level penalty
    if nova and str(nova).isdigit():
        score -= NOVA_PENALTIES.get(int(nova), 0)

    # 6. Long ingredient list penalty (> 10 items)
    if len(ingredients) > 10:
        score -= LONG_INGREDIENTS_PENALTY

    # 7. Clean label bonus
    no_harmful = len(harmful_additives) == 0
    no_harmful_preservatives = all(
        (p.get("concern_level") != "harmful" if isinstance(p, dict) else True)
        for p in preservatives
    )
    if no_harmful and no_harmful_preservatives:
        score += CLEAN_LABEL_BONUS

    return max(0, min(100, score))


def score_for_kids(analysis: Dict[str, Any]) -> int:
    """Stricter health scoring for children.

    Additives linked to hyperactivity, behavioral issues, or metabolic distress
    carry extra penalties, with tighter sugar thresholds.
    """
    base = compute_health_score(analysis)

    harmful_additives = analysis.get("harmful_additives", []) or []
    ingredients = analysis.get("ingredients", []) or []
    all_items = harmful_additives + ingredients

    extra_penalty = 0
    for item in all_items:
        if isinstance(item, dict):
            name = (item.get("name") or "").lower()
            e_num = (item.get("e_number") or "").lower()
            if any(k in name for k in KID_CONCERN_ADDITIVES) or e_num in KID_CONCERN_ADDITIVES:
                extra_penalty += 12

    # Kids sugar penalty: WHO recommends < 12g/day free sugars for children
    nutrition = analysis.get("nutrition_per_100g", {}) or {}
    if isinstance(nutrition, dict):
        sugar = nutrition.get("sugars_g")
        if sugar is not None:
            try:
                s_val = float(sugar)
                if s_val > 12:
                    extra_penalty += 10
                elif s_val > 6:
                    extra_penalty += 5
            except (ValueError, TypeError):
                pass

    return max(0, min(100, base - extra_penalty))
