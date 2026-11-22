"""FastAPI application entrypoint for LegalMetrologyAI backend."""

from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.errors import (
    ErrorResponse,
    generic_exception_handler,
    http_exception_handler,
    image_too_large_handler,
    inspection_not_found_handler,
    inspection_state_handler,
    invalid_image_handler,
    invalid_pipeline_input_handler,
    pipeline_error_handler,
    unsupported_image_handler,
    validation_exception_handler,
)
from backend.app.api.v1.endpoints.authority import router as authority_router
from backend.app.api.v1.endpoints.consumer_issues import router as consumer_issues_router
from backend.app.api.v1.endpoints.consumer_reports import router as consumer_reports_router
from backend.app.api.v1.endpoints.food_safety import (
    analyse_food_label_image,
    router as food_safety_router,
)
from backend.app.api.v1.endpoints.health import router as health_router
from backend.app.api.v1.endpoints.heatmap import router as heatmap_router
from backend.app.api.v1.endpoints.inspections import router as inspections_router
from backend.app.api.v1.endpoints.public_reports import router as public_reports_router
from backend.app.api.v1.endpoints.saved_products import router as saved_products_router
from backend.app.api.v1.endpoints.telegram_link import router as telegram_link_router
from backend.app.api.v1.endpoints.users import router as users_router
from backend.app.api.v1.endpoints.voice import router as voice_router
from backend.app.config import get_settings

from backend.app.services.evidence.errors import (
    ImageDecodeError,
    ImageIngestionError,
    ImageSecurityError,
    ImageTooLargeError,
    ImageTooManyPixelsError,
    InvalidImageError,
    UnsupportedImageFormatError,
)
from backend.app.services.inspection.errors import (
    InspectionNotFoundError,
    InspectionStateError,
    InvalidInspectionError,
    InvalidLifecycleTransitionError,
)
from backend.app.services.inspection_pipeline.errors import (
    InvalidPipelineInputError,
    PipelineError,
    PipelineExecutionError,
)


def create_app() -> FastAPI:
    """Application factory for LegalMetrologyAI FastAPI service."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Legal Metrology AI automated compliance & food safety verification service.",
        responses={
            400: {"model": ErrorResponse, "description": "Bad Request / Validation Failure"},
            404: {"model": ErrorResponse, "description": "Resource Not Found"},
            409: {"model": ErrorResponse, "description": "State Conflict"},
            500: {"model": ErrorResponse, "description": "Internal / Pipeline Error"},
        },
    )

    # Configure CORS (including LabelLens Vite default origins)
    allowed_origins = list(settings.cors_allowed_origins or [])
    for extra_origin in [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]:
        if extra_origin not in allowed_origins:
            allowed_origins.append(extra_origin)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Register Exception Handlers
    app.add_exception_handler(InspectionNotFoundError, inspection_not_found_handler)
    app.add_exception_handler(InspectionStateError, inspection_state_handler)
    app.add_exception_handler(InvalidLifecycleTransitionError, inspection_state_handler)
    app.add_exception_handler(ImageTooLargeError, image_too_large_handler)
    app.add_exception_handler(ImageTooManyPixelsError, image_too_large_handler)
    app.add_exception_handler(UnsupportedImageFormatError, unsupported_image_handler)
    app.add_exception_handler(InvalidImageError, invalid_image_handler)
    app.add_exception_handler(ImageDecodeError, invalid_image_handler)
    app.add_exception_handler(ImageSecurityError, invalid_image_handler)
    app.add_exception_handler(InvalidPipelineInputError, invalid_pipeline_input_handler)
    app.add_exception_handler(InvalidInspectionError, invalid_pipeline_input_handler)
    app.add_exception_handler(PipelineExecutionError, pipeline_error_handler)
    app.add_exception_handler(PipelineError, pipeline_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Register Routers
    # Root health endpoint and public report shares
    app.include_router(health_router)
    app.include_router(public_reports_router)

    # v1 health, inspections, public reports, heatmap, voice, authority, consumer reports, telegram, food safety endpoints
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(inspections_router, prefix="/api/v1")
    app.include_router(consumer_reports_router, prefix="/api/v1")
    app.include_router(public_reports_router, prefix="/api/v1")
    app.include_router(heatmap_router, prefix="/api/v1")
    app.include_router(voice_router, prefix="/api/v1")
    app.include_router(authority_router, prefix="/api/v1")
    app.include_router(telegram_link_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(saved_products_router, prefix="/api/v1")
    app.include_router(consumer_issues_router, prefix="/api/v1")
    app.include_router(food_safety_router, prefix="/api/v1")

    # Direct LabelLens compatibility route at /api/analyse
    app.add_api_route(
        "/api/analyse",
        analyse_food_label_image,
        methods=["POST"],
        summary="LabelLens Direct API compatibility endpoint",
        tags=["Food Safety & Additives Lens"],
    )

    # Serve LabelLens interactive Web UI directly
    labellens_index = Path("D:/Development/Minor Projezt/LabelLens/index.html")

    @app.get("/labellens", include_in_schema=False)
    def labellens_ui():
        if labellens_index.exists():
            return FileResponse(labellens_index)
        raise HTTPException(status_code=404, detail="LabelLens UI index.html not found.")

    # Mount compiled Flutter Web Application at /app
    flutter_web_dir = Path(__file__).resolve().parent.parent.parent / "build" / "web"
    if flutter_web_dir.exists():
        app.mount("/app", StaticFiles(directory=str(flutter_web_dir), html=True), name="flutter_app")

    return app


app = create_app()
