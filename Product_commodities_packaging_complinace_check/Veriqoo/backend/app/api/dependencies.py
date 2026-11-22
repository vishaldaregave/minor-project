"""Dependency injection providers for FastAPI API endpoints."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Generator
from fastapi import Depends

from backend.app.api.session_store import InMemoryInspectionStore
from backend.app.auth import AuthenticatedUser, get_current_user
from backend.app.config import Settings, get_settings
from backend.app.services.evidence.ingestion import ImageIngestionService
from backend.app.services.evidence.models import IngestionConfig
from backend.app.services.inspection_pipeline.orchestrator import InspectionPipelineOrchestrator


# Singleton in-memory store for API sessions
_GLOBAL_SESSION_STORE = InMemoryInspectionStore()


def get_session_store() -> InMemoryInspectionStore:
    """Provide the in-memory inspection session store (singleton / injectable)."""
    return _GLOBAL_SESSION_STORE


def get_ingestion_service() -> ImageIngestionService:
    """Provide the Phase 5A image ingestion service."""
    return ImageIngestionService(config=IngestionConfig())


def get_pipeline_orchestrator() -> InspectionPipelineOrchestrator:
    """Provide the Phase 7 unified end-to-end inspection orchestrator."""
    return InspectionPipelineOrchestrator()


def get_app_settings() -> Settings:
    """Provide application configuration settings."""
    return get_settings()


def get_image_storage():
    """Provide ImageStorage backend (SupabaseImageStorage when configured, InMemoryImageStorage otherwise)."""
    from backend.app.services.storage import InMemoryImageStorage, SupabaseImageStorage

    settings = get_settings()
    if settings.supabase_url and (getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key):
        return SupabaseImageStorage(settings=settings)
    return InMemoryImageStorage()


def get_inspection_service(
    ingestion_service: ImageIngestionService | None = None,
    orchestrator: InspectionPipelineOrchestrator | None = None,
):
    """Provide InspectionService coordinator."""
    from backend.app.services.inspection.repository import InMemoryInspectionRepository
    from backend.app.services.inspection.service import InspectionService

    storage = get_image_storage()
    repo = InMemoryInspectionRepository()
    return InspectionService(
        repository=repo,
        ingestion_service=ingestion_service or get_ingestion_service(),
        orchestrator=orchestrator or get_pipeline_orchestrator(),
        storage=storage,
    )


# Singleton execution service for process-local background task management
_GLOBAL_EXECUTION_SERVICE: Any = None


def get_inspection_execution_service(
    session_store: InMemoryInspectionStore | None = None,
    orchestrator: InspectionPipelineOrchestrator | None = None,
):
    """Provide process-local InspectionExecutionService."""
    global _GLOBAL_EXECUTION_SERVICE
    from backend.app.services.inspection.execution import InspectionExecutionService
    from backend.app.services.inspection.service import InspectionService

    if _GLOBAL_EXECUTION_SERVICE is None:
        service = get_inspection_service(orchestrator=orchestrator)
        _GLOBAL_EXECUTION_SERVICE = InspectionExecutionService(inspection_service=service)
    return _GLOBAL_EXECUTION_SERVICE


_GLOBAL_ACCOUNT_LINK_REPO: Any = None


def get_account_link_repository():
    """Provide AccountLinkRepository backend (Supabase or In-Memory)."""
    global _GLOBAL_ACCOUNT_LINK_REPO
    from backend.app.telegram.account_linking import (
        InMemoryAccountLinkRepository,
        SupabaseAccountLinkRepository,
    )

    if _GLOBAL_ACCOUNT_LINK_REPO is None:
        settings = get_settings()
        if settings.supabase_url and (getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key):
            _GLOBAL_ACCOUNT_LINK_REPO = SupabaseAccountLinkRepository(settings=settings)
        else:
            _GLOBAL_ACCOUNT_LINK_REPO = InMemoryAccountLinkRepository()
    return _GLOBAL_ACCOUNT_LINK_REPO


def get_account_linking_service():
    """Provide AccountLinkingService coordinator."""
    from backend.app.telegram.account_linking import AccountLinkingService

    repo = get_account_link_repository()
    return AccountLinkingService(repository=repo)


def get_report_sharing_service(
    store: InMemoryInspectionStore = Depends(get_session_store),
    settings: Settings = Depends(get_app_settings),
):
    """Provide ReportSharingService coordinator for Phase U4."""
    from backend.app.services.report_sharing.service import ReportSharingService

    return ReportSharingService(store=store, settings=settings)


def get_consumer_intelligence_service(
    store: InMemoryInspectionStore = Depends(get_session_store),
):
    """Provide ConsumerIntelligenceService coordinator for Phase U5."""
    from backend.app.localization.service import get_localization_service
    from backend.app.services.consumer_intelligence.service import ConsumerIntelligenceService

    loc = get_localization_service()
    return ConsumerIntelligenceService(store=store, localization=loc)


def get_consumer_result_service(
    store: InMemoryInspectionStore = Depends(get_session_store),
    intelligence_service: Any = Depends(get_consumer_intelligence_service),
):
    """Provide ConsumerResultService coordinator for Phase U6."""
    from backend.app.localization.service import get_localization_service
    from backend.app.services.consumer_result.service import ConsumerResultService

    loc = get_localization_service()
    return ConsumerResultService(
        session_store=store,
        localization_service=loc,
        intelligence_service=intelligence_service,
    )


def get_heatmap_service(
    store: InMemoryInspectionStore = Depends(get_session_store),
    intelligence_service: Any = Depends(get_consumer_intelligence_service),
):
    """Provide HeatmapService coordinator for Phase U7."""
    from backend.app.localization.service import get_localization_service
    from backend.app.services.heatmap.service import HeatmapService

    loc = get_localization_service()
    return HeatmapService(
        store=store,
        localization=loc,
        intelligence_service=intelligence_service,
    )


def get_voice_service(
    store: InMemoryInspectionStore = Depends(get_session_store),
    intelligence_service: Any = Depends(get_consumer_intelligence_service),
    consumer_result_service: Any = Depends(get_consumer_result_service),
    settings: Settings = Depends(get_app_settings),
):
    """Provide VoiceAssistantService coordinator for Phase U8."""
    from backend.app.localization.service import get_localization_service
    from backend.app.services.voice.context import VoiceContextResolver
    from backend.app.services.voice.providers.reasoning import (
        FakeVoiceReasoningProvider,
        GeminiVoiceReasoningProvider,
    )
    from backend.app.services.voice.providers.stt import (
        DeepgramSpeechToTextProvider,
        FakeSpeechToTextProvider,
    )
    from backend.app.services.voice.providers.tts import (
        CartesiaTextToSpeechProvider,
        FakeTextToSpeechProvider,
    )
    from backend.app.services.voice.service import VoiceAssistantService

    loc = get_localization_service()

    # Configure STT provider
    if settings.deepgram_api_key:
        stt_provider = DeepgramSpeechToTextProvider(
            api_key=settings.deepgram_api_key,
            model=settings.deepgram_model,
        )
    else:
        stt_provider = FakeSpeechToTextProvider()

    # Configure TTS provider
    if settings.cartesia_api_key:
        tts_provider = CartesiaTextToSpeechProvider(
            api_key=settings.cartesia_api_key,
            model_id=settings.cartesia_model_id,
            default_voice_id=settings.cartesia_voice_id or None,
        )
    else:
        tts_provider = FakeTextToSpeechProvider()

    # Configure Voice Reasoning provider
    if settings.gemini_api_key:
        reasoning_provider = GeminiVoiceReasoningProvider(
            api_key=settings.gemini_api_key,
        )
    else:
        reasoning_provider = FakeVoiceReasoningProvider()

    context_resolver = VoiceContextResolver(
        session_store=store,
        localization=loc,
        consumer_result_service=consumer_result_service,
        consumer_intelligence_service=intelligence_service,
    )

    return VoiceAssistantService(
        stt_provider=stt_provider,
        tts_provider=tts_provider,
        reasoning_provider=reasoning_provider,
        context_resolver=context_resolver,
        localization=loc,
    )


_GLOBAL_AUTHORITY_REPO: Any = None


def get_authority_repository():
    """Provide AuthorityRepository backend (Supabase or In-Memory)."""
    global _GLOBAL_AUTHORITY_REPO
    from backend.app.services.authority.repository import (
        InMemoryAuthorityRepository,
        SupabaseAuthorityRepository,
    )

    if _GLOBAL_AUTHORITY_REPO is None:
        settings = get_settings()
        if settings.supabase_url and (getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key):
            _GLOBAL_AUTHORITY_REPO = SupabaseAuthorityRepository(
                supabase_url=settings.supabase_url,
                supabase_key=getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key,
            )
        else:
            _GLOBAL_AUTHORITY_REPO = InMemoryAuthorityRepository()
    return _GLOBAL_AUTHORITY_REPO


def get_authority_service(
    repo: Any = Depends(get_authority_repository),
):
    """Provide AuthorityService coordinator for Phase U9 / T3-4."""
    from backend.app.services.authority.service import AuthorityService

    return AuthorityService(repository=repo)


_GLOBAL_INSPECTION_REPO: Any = None


def get_inspection_repository():
    """Provide InspectionRepository backend (Supabase or In-Memory)."""
    global _GLOBAL_INSPECTION_REPO
    from backend.app.services.inspection.repository import (
        InMemoryInspectionRepository,
        SupabaseInspectionRepository,
    )

    if _GLOBAL_INSPECTION_REPO is None:
        settings = get_settings()
        if settings.supabase_url and (getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key):
            _GLOBAL_INSPECTION_REPO = SupabaseInspectionRepository(
                supabase_url=settings.supabase_url,
                supabase_key=getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key,
            )
        else:
            _GLOBAL_INSPECTION_REPO = InMemoryInspectionRepository()
    return _GLOBAL_INSPECTION_REPO


def get_consumer_report_service(
    store: InMemoryInspectionStore = Depends(get_session_store),
    intelligence_service: Any = Depends(get_consumer_intelligence_service),
    consumer_result_service: Any = Depends(get_consumer_result_service),
    repository: Any = Depends(get_inspection_repository),
):
    """Provide ConsumerReportService coordinator for Phase U10."""
    from backend.app.localization.service import get_localization_service
    from backend.app.services.consumer_report.service import ConsumerReportService

    loc = get_localization_service()
    return ConsumerReportService(
        store=store,
        repository=repository,
        localization=loc,
        consumer_intel_service=intelligence_service,
        consumer_result_service=consumer_result_service,
    )


_GLOBAL_SYNC_OPERATION_REPO: Any = None


def get_sync_operation_repository():
    """Provide SyncOperationRepository backend (Supabase or In-Memory)."""
    global _GLOBAL_SYNC_OPERATION_REPO
    from backend.app.services.offline_sync.repository import (
        InMemorySyncOperationRepository,
        SupabaseSyncOperationRepository,
    )

    if _GLOBAL_SYNC_OPERATION_REPO is None:
        settings = get_settings()
        if settings.supabase_url and (getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key):
            _GLOBAL_SYNC_OPERATION_REPO = SupabaseSyncOperationRepository(settings=settings)
        else:
            _GLOBAL_SYNC_OPERATION_REPO = InMemorySyncOperationRepository()
    return _GLOBAL_SYNC_OPERATION_REPO


def get_sync_ingestion_service(
    sync_repo: Any = Depends(get_sync_operation_repository),
    inspection_repo: Any = Depends(get_inspection_repository),
    settings: Settings = Depends(get_app_settings),
):
    """Provide SyncIngestionService coordinator for Phase U24."""
    from backend.app.services.offline_sync.ingestion import SyncIngestionService

    return SyncIngestionService(
        sync_repository=sync_repo,
        inspection_repository=inspection_repo,
        server_version=settings.app_version,
    )


def get_server_revalidation_service(
    sync_repo: Any = Depends(get_sync_operation_repository),
    inspection_repo: Any = Depends(get_inspection_repository),
    store: InMemoryInspectionStore = Depends(get_session_store),
):
    """Provide ServerRevalidationService coordinator for Phase U24-F/G."""
    from backend.app.services.offline_sync.revalidation import ServerRevalidationService

    return ServerRevalidationService(
        sync_repository=sync_repo,
        inspection_repository=inspection_repo,
        session_store=store,
    )


_GLOBAL_EVIDENCE_CHAIN_REPO: Any = None


def get_evidence_chain_repository():
    """Provide EvidenceChainRepository backend (Supabase or In-Memory)."""
    global _GLOBAL_EVIDENCE_CHAIN_REPO
    from backend.app.services.evidence_chain.repository import (
        InMemoryEvidenceChainRepository,
        SupabaseEvidenceChainRepository,
    )

    if _GLOBAL_EVIDENCE_CHAIN_REPO is None:
        settings = get_settings()
        if settings.supabase_url and (getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key):
            _GLOBAL_EVIDENCE_CHAIN_REPO = SupabaseEvidenceChainRepository(settings=settings)
        else:
            _GLOBAL_EVIDENCE_CHAIN_REPO = InMemoryEvidenceChainRepository()
    return _GLOBAL_EVIDENCE_CHAIN_REPO


def get_evidence_chain_service(
    evidence_repo: Any = Depends(get_evidence_chain_repository),
    storage: Any = Depends(get_image_storage),
):
    """Provide EvidenceChainService coordinator for Phase U25."""
    from backend.app.services.evidence_chain.service import EvidenceChainService

    return EvidenceChainService(
        repository=evidence_repo,
        storage=storage,
    )


_GLOBAL_USER_PROFILE_REPO: Any = None


def get_user_profile_repository():
    """Provide UserProfileRepository backend (Supabase or In-Memory)."""
    global _GLOBAL_USER_PROFILE_REPO
    from backend.app.services.user_profile.repository import (
        InMemoryUserProfileRepository,
        SupabaseUserProfileRepository,
    )

    if _GLOBAL_USER_PROFILE_REPO is None:
        settings = get_settings()
        if settings.supabase_url and (getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key):
            _GLOBAL_USER_PROFILE_REPO = SupabaseUserProfileRepository(
                supabase_url=settings.supabase_url,
                supabase_key=getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key,
            )
        else:
            _GLOBAL_USER_PROFILE_REPO = InMemoryUserProfileRepository()
    return _GLOBAL_USER_PROFILE_REPO


def get_user_profile_service(
    repo: Any = Depends(get_user_profile_repository),
):
    """Provide UserProfileService coordinator for T3-1."""
    from backend.app.services.user_profile.service import UserProfileService

    return UserProfileService(repository=repo)


_GLOBAL_SAVED_PRODUCT_REPO: Any = None


def get_saved_product_repository():
    """Provide SavedProductRepository backend (Supabase or In-Memory)."""
    global _GLOBAL_SAVED_PRODUCT_REPO
    from backend.app.services.saved_products.repository import (
        InMemorySavedProductRepository,
        SupabaseSavedProductRepository,
    )

    if _GLOBAL_SAVED_PRODUCT_REPO is None:
        settings = get_settings()
        if settings.supabase_url and (getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key):
            _GLOBAL_SAVED_PRODUCT_REPO = SupabaseSavedProductRepository(
                supabase_url=settings.supabase_url,
                supabase_key=getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key,
            )
        else:
            _GLOBAL_SAVED_PRODUCT_REPO = InMemorySavedProductRepository()
    return _GLOBAL_SAVED_PRODUCT_REPO


def get_saved_product_service(
    repo: Any = Depends(get_saved_product_repository),
    inspection_repo: Any = Depends(get_inspection_repository),
    store: InMemoryInspectionStore = Depends(get_session_store),
):
    """Provide SavedProductService coordinator for T3-2."""
    from backend.app.services.saved_products.service import SavedProductService

    return SavedProductService(
        repository=repo,
        inspection_repository=inspection_repo,
        session_store=store,
    )


_GLOBAL_CONSUMER_ISSUE_REPO: Any = None


def get_consumer_issue_repository():
    """Provide ConsumerIssueRepository backend (Supabase or In-Memory)."""
    global _GLOBAL_CONSUMER_ISSUE_REPO
    from backend.app.services.consumer_issues.repository import (
        InMemoryConsumerIssueRepository,
        SupabaseConsumerIssueRepository,
    )

    if _GLOBAL_CONSUMER_ISSUE_REPO is None:
        settings = get_settings()
        if settings.supabase_url and (getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key):
            _GLOBAL_CONSUMER_ISSUE_REPO = SupabaseConsumerIssueRepository(
                supabase_url=settings.supabase_url,
                supabase_key=getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key,
            )
        else:
            _GLOBAL_CONSUMER_ISSUE_REPO = InMemoryConsumerIssueRepository()
    return _GLOBAL_CONSUMER_ISSUE_REPO


def get_consumer_issue_service(
    repo: Any = Depends(get_consumer_issue_repository),
    store: InMemoryInspectionStore = Depends(get_session_store),
    saved_product_repo: Any = Depends(get_saved_product_repository),
):
    """Provide ConsumerIssueService coordinator for T3-3."""
    from backend.app.services.consumer_issues.service import ConsumerIssueService

    return ConsumerIssueService(
        repository=repo,
        session_store=store,
        saved_product_repository=saved_product_repo,
    )


_GLOBAL_ESTABLISHMENT_REPO: Any = None


def get_establishment_repository():
    """Provide EstablishmentRepository backend (Supabase or In-Memory)."""
    global _GLOBAL_ESTABLISHMENT_REPO
    from backend.app.services.establishment.repository import (
        InMemoryEstablishmentRepository,
        SupabaseEstablishmentRepository,
    )

    if _GLOBAL_ESTABLISHMENT_REPO is None:
        settings = get_settings()
        if settings.supabase_url and (getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key):
            _GLOBAL_ESTABLISHMENT_REPO = SupabaseEstablishmentRepository(
                supabase_url=settings.supabase_url,
                supabase_key=getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key,
            )
        else:
            _GLOBAL_ESTABLISHMENT_REPO = InMemoryEstablishmentRepository()
    return _GLOBAL_ESTABLISHMENT_REPO


def get_establishment_service(
    repo: Any = Depends(get_establishment_repository),
):
    """Provide EstablishmentService coordinator."""
    from backend.app.services.establishment.service import EstablishmentService

    return EstablishmentService(repository=repo)


_GLOBAL_AUTHORITY_CASE_REPO: Any = None


def get_authority_case_repository():
    """Provide AuthorityCaseRepository backend (Supabase or In-Memory)."""
    global _GLOBAL_AUTHORITY_CASE_REPO
    from backend.app.services.authority.case_repository import (
        InMemoryAuthorityCaseRepository,
        SupabaseAuthorityCaseRepository,
    )

    if _GLOBAL_AUTHORITY_CASE_REPO is None:
        settings = get_settings()
        if settings.supabase_url and (getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key):
            _GLOBAL_AUTHORITY_CASE_REPO = SupabaseAuthorityCaseRepository(
                supabase_url=settings.supabase_url,
                supabase_key=getattr(settings, "supabase_service_role_key", None) or settings.supabase_anon_key,
            )
        else:
            _GLOBAL_AUTHORITY_CASE_REPO = InMemoryAuthorityCaseRepository()
    return _GLOBAL_AUTHORITY_CASE_REPO


def get_authority_case_service(
    case_repo: Any = Depends(get_authority_case_repository),
    auth_repo: Any = Depends(get_authority_repository),
    est_repo: Any = Depends(get_establishment_repository),
):
    """Provide AuthorityCaseService coordinator for T3-4."""
    from backend.app.services.authority.case_service import AuthorityCaseService

    return AuthorityCaseService(
        case_repository=case_repo,
        authority_repository=auth_repo,
        establishment_repository=est_repo,
    )
