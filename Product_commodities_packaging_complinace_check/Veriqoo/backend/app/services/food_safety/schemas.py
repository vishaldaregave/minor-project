"""Pydantic data schemas for Food Safety & Additives Lens (LabelLens feature)."""

from __future__ import annotations

from typing import Any, List, Optional
from pydantic import BaseModel, Field


class Nutrition(BaseModel):
    """Nutritional facts per 100g/ml."""

    energy_kcal: Optional[float] = None
    fat_g: Optional[float] = None
    saturated_fat_g: Optional[float] = None
    carbohydrates_g: Optional[float] = None
    sugars_g: Optional[float] = None
    protein_g: Optional[float] = None
    salt_g: Optional[float] = None
    sodium_mg: Optional[float] = None
    fibre_g: Optional[float] = None


class Ingredient(BaseModel):
    """Single ingredient detail with classification and safety."""

    name: str
    category: str = "Base ingredient"
    safe_limit: str = "No established limit"
    concern_level: str = "safe"  # safe | moderate | harmful
    kids_safe: Optional[bool] = True
    note: Optional[str] = None


class HarmfulAdditive(BaseModel):
    """Additive with known or suspected health risks."""

    name: str
    e_number: Optional[str] = None
    why_harmful: str
    safe_limit_per_day: str = "Not established"
    kids_concern: Optional[bool] = False
    kids_note: Optional[str] = None


class Preservative(BaseModel):
    """Preservative substance detail and interactions."""

    name: str
    e_number: Optional[str] = None
    concern_level: str = "safe"  # safe | moderate | harmful
    note: str
    safe_limit_per_day: Optional[str] = None


class AnalysisResult(BaseModel):
    """Complete structured Food Safety & Additive verification result."""

    health_score: int = Field(..., ge=0, le=100, description="Overall health score from 0 to 100")
    kids_score: int = Field(..., ge=0, le=100, description="Kids specific safety score from 0 to 100")
    summary: str = Field(..., description="2-sentence plain English verdict")
    kids_verdict: Optional[str] = None
    nutrition_per_100g: Optional[Nutrition] = None
    harmful_additives: List[HarmfulAdditive] = Field(default_factory=list)
    preservatives: List[Preservative] = Field(default_factory=list)
    ingredients: List[Ingredient] = Field(default_factory=list)
    nova_group: Optional[int] = Field(default=None, ge=1, le=4, description="NOVA processing group (1-4)")
    overall_concerns: Optional[List[str]] = Field(default_factory=list)
    good_points: Optional[List[str]] = Field(default_factory=list)


class FoodSafetyTextAnalysisRequest(BaseModel):
    """Request payload for text-based food label analysis."""

    ingredients_text: str = Field(..., min_length=2, description="Extracted or manually entered ingredient list")
    product_name: Optional[str] = None
