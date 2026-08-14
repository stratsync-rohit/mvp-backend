"""Browser-facing MVP account discovery with a deliberately minimal response."""
from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import get_tenant_mapping_service
from app.schemas.accounts import AccountListItem
from app.services.tenant_mapping_service import TenantMappingService

router = APIRouter(prefix="/api/accounts", tags=["Accounts"])
TenantMappingServiceDep = Annotated[
    TenantMappingService, Depends(get_tenant_mapping_service)
]


@router.get("", response_model=list[AccountListItem])
async def list_accounts(service: TenantMappingServiceDep) -> list[dict[str, str]]:
    """MVP/internal selector data; production visibility must come from auth claims."""
    return await service.list_accounts()
