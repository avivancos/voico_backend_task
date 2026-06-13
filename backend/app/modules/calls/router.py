import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import async_session
from app.core.decorators import session_manager
from app.modules.calls.repository import CallRepository
from app.modules.calls.schema import (
    CallResponse,
    CallStatus,
    PaginatedCallsResponse,
    WebhookCallPayload,
)
from app.modules.calls.service import CallService

router = APIRouter()


async def get_session():
    async with async_session() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_call_service(session: SessionDep) -> CallService:
    return CallService(CallRepository(session))


@router.get("/calls", response_model=PaginatedCallsResponse)
async def list_calls(
    session: SessionDep,
    service: Annotated[CallService, Depends(get_call_service)],
    status: Optional[CallStatus] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedCallsResponse:
    return await service.list_calls(status=status, page=page, page_size=page_size)


@router.get("/calls/{call_id}", response_model=CallResponse)
async def get_call(
    call_id: uuid.UUID,
    session: SessionDep,
    service: Annotated[CallService, Depends(get_call_service)],
) -> CallResponse:
    return await service.get_call(call_id)


@router.post("/webhook/call", response_model=CallResponse)
@session_manager
async def webhook_call(
    payload: WebhookCallPayload,
    session: SessionDep,
) -> CallResponse:
    raise NotImplementedError("webhook_call is implemented in Task 4")
