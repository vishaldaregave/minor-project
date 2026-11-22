"""FastAPI endpoints for Food Safety, Additives, and EFSA Nutrition Analysis (LabelLens)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from backend.app.services.food_safety.efsa_database import EFSADatabase
from backend.app.services.food_safety.schemas import (
    AnalysisResult,
    FoodSafetyTextAnalysisRequest,
)
from backend.app.services.food_safety.service import FoodSafetyService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/food-safety", tags=["Food Safety & Additives Lens"])

# Global singleton service instance
_FOOD_SAFETY_SERVICE: Optional[FoodSafetyService] = None


def get_food_safety_service() -> FoodSafetyService:
    """Dependency provider for FoodSafetyService."""
    global _FOOD_SAFETY_SERVICE
    if _FOOD_SAFETY_SERVICE is None:
        _FOOD_SAFETY_SERVICE = FoodSafetyService()
    return _FOOD_SAFETY_SERVICE


@router.post(
    "/analyse",
    response_model=AnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Analyse Food Label Image (LabelLens)",
    description="Extracts ingredients from label image, verifies against EFSA OpenFoodTox database, checks child safety and harmful additives.",
)
async def analyse_food_label_image(
    image: UploadFile = File(..., description="Photograph of packaged food ingredient label"),
    service: FoodSafetyService = Depends(get_food_safety_service),
) -> AnalysisResult:
    """Analyse food label photo."""
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image file received.")

    try:
        return service.analyze_image(image_bytes=image_bytes, content_type=image.content_type or "image/jpeg")
    except Exception as exc:
        logger.error("Food safety image analysis failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Food safety analysis pipeline failure: {str(exc)}",
        )


@router.post(
    "/analyse-text",
    response_model=AnalysisResult,
    status_code=status.HTTP_200_OK,
    summary="Analyse Food Ingredients Text",
    description="Audits raw ingredients text against EFSA database, calculates health score, kids verdict, and identifies dangerous additive combinations.",
)
def analyse_food_ingredients_text(
    payload: FoodSafetyTextAnalysisRequest,
    service: FoodSafetyService = Depends(get_food_safety_service),
) -> AnalysisResult:
    """Analyse text ingredient declaration."""
    try:
        return service.analyze_text(
            ingredients_text=payload.ingredients_text,
            product_name=payload.product_name,
        )
    except Exception as exc:
        logger.error("Food safety text analysis failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Food safety text analysis failed: {str(exc)}",
        )


@router.get(
    "/substances/search",
    response_model=List[Dict[str, Any]],
    summary="Search EFSA OpenFoodTox Database",
    description="Search 3,175+ EFSA food substances by name, E-number, or toxicological keyword.",
)
def search_efsa_substances(
    q: str = Query(..., min_length=2, description="Substance name, E-number, or keyword"),
    limit: int = Query(10, ge=1, le=50),
) -> List[Dict[str, Any]]:
    """Search EFSA database."""
    db = EFSADatabase.get_instance()
    return db.search_substance(q, limit=limit)
