"""
FastAPI dependency wiring: Router -> Service -> Repository -> MongoDB.

Each `get_*_service` dependency builds a fresh service instance backed by
the current request's database handle. Repositories/services are cheap to
construct (no I/O in __init__), so this keeps things simple and avoids any
global mutable state beyond the Mongo client itself.
"""
from typing import Annotated

from fastapi import Depends, Header, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings, get_settings
from app.database import get_database
from app.exceptions.handlers import UnauthorizedError
from app.repositories.idempotency_repository import IdempotencyRepository
from app.repositories.notification_log_repository import NotificationLogRepository
from app.repositories.risk_repository import RiskRepository
from app.repositories.teams_destination_repository import TeamsDestinationRepository
from app.repositories.teams_installation_repository import TeamsInstallationRepository
from app.repositories.tenant_mapping_repository import TenantMappingRepository
from app.services.action_service import ActionService
from app.services.n8n_service import N8nService
from app.services.notification_log_service import NotificationLogService
from app.services.notification_service import NotificationService
from app.services.risk_service import RiskService
from app.services.teams_destination_service import TeamsDestinationService
from app.services.teams_installation_service import TeamsInstallationService
from app.services.tenant_mapping_service import TenantMappingService

DbDep = Annotated[AsyncIOMotorDatabase, Depends(get_database)]


def get_risk_repository(db: DbDep) -> RiskRepository:
    return RiskRepository(db)


def get_teams_destination_repository(db: DbDep) -> TeamsDestinationRepository:
    return TeamsDestinationRepository(db)


def get_teams_installation_repository(db: DbDep) -> TeamsInstallationRepository:
    return TeamsInstallationRepository(db)


def get_tenant_mapping_repository(db: DbDep) -> TenantMappingRepository:
    return TenantMappingRepository(db)


def get_notification_log_repository(db: DbDep) -> NotificationLogRepository:
    return NotificationLogRepository(db)


def get_idempotency_repository(db: DbDep) -> IdempotencyRepository:
    return IdempotencyRepository(db)


def get_risk_service(
    repo: Annotated[RiskRepository, Depends(get_risk_repository)],
) -> RiskService:
    return RiskService(repo)


def get_teams_destination_service(
    repo: Annotated[TeamsDestinationRepository, Depends(get_teams_destination_repository)],
) -> TeamsDestinationService:
    return TeamsDestinationService(repo)


def get_teams_installation_service(
    repo: Annotated[TeamsInstallationRepository, Depends(get_teams_installation_repository)],
    tenant_mapping_repo: Annotated[
        TenantMappingRepository, Depends(get_tenant_mapping_repository)
    ],
) -> TeamsInstallationService:
    return TeamsInstallationService(repo, tenant_mapping_repo)


def get_tenant_mapping_service(
    repo: Annotated[TenantMappingRepository, Depends(get_tenant_mapping_repository)],
) -> TenantMappingService:
    return TenantMappingService(repo)


def get_notification_log_service(
    repo: Annotated[NotificationLogRepository, Depends(get_notification_log_repository)],
) -> NotificationLogService:
    return NotificationLogService(repo)


def get_n8n_service() -> N8nService:
    return N8nService()


def get_notification_service(
    risk_service: Annotated[RiskService, Depends(get_risk_service)],
    installation_service: Annotated[
        TeamsInstallationService, Depends(get_teams_installation_service)
    ],
    log_repo: Annotated[NotificationLogRepository, Depends(get_notification_log_repository)],
    idempotency_repo: Annotated[IdempotencyRepository, Depends(get_idempotency_repository)],
    n8n_service: Annotated[N8nService, Depends(get_n8n_service)],
) -> NotificationService:
    return NotificationService(
        risk_service=risk_service,
        installation_service=installation_service,
        notification_log_repository=log_repo,
        idempotency_repository=idempotency_repo,
        n8n_service=n8n_service,
    )


def get_action_service(
    risk_service: Annotated[RiskService, Depends(get_risk_service)],
) -> ActionService:
    return ActionService(risk_service)


async def verify_internal_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    x_internal_api_key: Annotated[str | None, Header()] = None,
) -> None:
    """Optional internal API key guard for sensitive internal endpoints.

    Disabled entirely when `internal_api_key_enabled` is False (e.g. local
    development), so it never blocks day-to-day testing unless explicitly
    turned on.
    """
    if not settings.internal_api_key_enabled:
        return

    if not x_internal_api_key or x_internal_api_key != settings.internal_api_key:
        raise UnauthorizedError()
