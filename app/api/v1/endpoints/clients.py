"""
Client Management endpoints (Module 1).

    POST   /api/v1/clients              Register a new API client
    GET    /api/v1/clients/{id}         Get client details
    GET    /api/v1/clients              List clients (search/filter/paginate)
    PATCH  /api/v1/clients/{id}/disable Disable a client
    PATCH  /api/v1/clients/{id}/enable  Enable a client

Endpoints stay thin: parse/validate the request, call the service, shape the
response. All business logic lives in ClientService.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.dependencies import PaginationParams
from app.db.session import get_db
from app.models.client import PlanType
from app.schemas.client import (
    ClientCreate,
    ClientListResponse,
    ClientRead,
    ClientRegisterResponse,
)
from app.services.client_service import ClientService

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post(
    "",
    response_model=ClientRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new API client",
)
async def register_client(payload: ClientCreate, db: AsyncSession = Depends(get_db)):
    service = ClientService(db)
    client, api_key = await service.register_client(
        client_name=payload.client_name, email=payload.email, plan=payload.plan
    )
    await db.commit()
    return ClientRegisterResponse(client_id=client.id, api_key=api_key)


@router.get("", response_model=ClientListResponse, summary="List clients")
async def list_clients(
    pagination: PaginationParams = Depends(),
    search: str | None = Query(default=None, description="Search by client name or email"),
    status_filter: str | None = Query(
        default=None, alias="status", description="Filter by status: active | inactive"
    ),
    plan: PlanType | None = Query(default=None, description="Filter by plan"),
    ordering: str = Query(default="-created_at", description="e.g. -created_at, client_name"),
    db: AsyncSession = Depends(get_db),
):
    service = ClientService(db)
    clients, total = await service.list_clients(
        search=search,
        status=status_filter,
        plan=plan.value if plan else None,
        ordering=ordering,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return ClientListResponse(
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        results=[ClientRead.model_validate(c) for c in clients],
    )


@router.get("/{client_id}", response_model=ClientRead, summary="Get client details")
async def get_client(client_id: int, db: AsyncSession = Depends(get_db)):
    service = ClientService(db)
    return await service.get_client(client_id)


@router.patch("/{client_id}/disable", response_model=ClientRead, summary="Disable a client")
async def disable_client(client_id: int, db: AsyncSession = Depends(get_db)):
    service = ClientService(db)
    client = await service.disable_client(client_id)
    await db.commit()
    return client


@router.patch("/{client_id}/enable", response_model=ClientRead, summary="Enable a client")
async def enable_client(client_id: int, db: AsyncSession = Depends(get_db)):
    service = ClientService(db)
    client = await service.enable_client(client_id)
    await db.commit()
    return client
