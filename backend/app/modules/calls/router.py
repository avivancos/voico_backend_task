import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db import async_session
from app.core.decorators import session_manager
from app.modules.calls.enrichment import Enricher, build_default_enricher
from app.modules.calls.repository import CallRepository
from app.modules.calls.schema import (
    CallLabel,
    CallResponse,
    CallSortField,
    CallStatus,
    PaginatedCallsResponse,
    SortDir,
    UpdateCallNotesRequest,
    WebhookCallPayload,
)
from app.modules.calls.security import verify_webhook_signature
from app.modules.calls.service import CallService

router = APIRouter()


async def get_session():
    async with async_session() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_call_service(session: SessionDep) -> CallService:
    return CallService(CallRepository(session))


def get_enricher() -> Optional[Enricher]:
    """The configured AI enricher, or None when no OPENAI_API_KEY is set. Overridden in tests."""
    return build_default_enricher()


EnricherDep = Annotated[Optional[Enricher], Depends(get_enricher)]


@router.get(
    "/calls",
    response_model=PaginatedCallsResponse,
    summary="List calls with filtering, search and sorting",
    responses={422: {"description": "Invalid filter, sort field, or duration range"}},
)
async def list_calls(
    session: SessionDep,
    service: Annotated[CallService, Depends(get_call_service)],
    status: Optional[CallStatus] = Query(default=None, description="Exact status match."),
    caller_name: Optional[str] = Query(
        default=None, description="Case-insensitive partial match on the caller's name."
    ),
    phone: Optional[str] = Query(
        default=None,
        description="Partial phone match. Compared on digits only, so formatting is ignored "
        "(e.g. `5552014832` matches `+1 (555) 201-4832`).",
    ),
    label: Optional[CallLabel] = Query(
        default=None, description="Exact label match (e.g. `Sales inquiry`)."
    ),
    min_duration: Optional[int] = Query(
        default=None, ge=0, le=86_400, description="Minimum call duration in seconds (inclusive)."
    ),
    max_duration: Optional[int] = Query(
        default=None, ge=0, le=86_400, description="Maximum call duration in seconds (inclusive)."
    ),
    sort_by: CallSortField = Query(
        default=CallSortField.created_at, description="Column to sort by (whitelisted)."
    ),
    sort_dir: SortDir = Query(default=SortDir.desc, description="Sort direction."),
    page: int = Query(default=1, ge=1, le=1_000_000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedCallsResponse:
    """List calls. All filters are optional and combined with AND; an empty text filter is ignored.

    `counts` is the per-status breakdown over the active content filters (ignoring `status`), so the
    status tabs stay informative; `total` and the returned page additionally respect `status`.
    """
    if min_duration is not None and max_duration is not None and min_duration > max_duration:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="min_duration must be less than or equal to max_duration",
        )
    return await service.list_calls(
        status=status,
        caller_name=caller_name,
        phone=phone,
        label=label,
        min_duration=min_duration,
        max_duration=max_duration,
        sort_by=sort_by,
        sort_dir=sort_dir,
        page=page,
        page_size=page_size,
    )


@router.get("/calls/{call_id}", response_model=CallResponse)
async def get_call(
    call_id: uuid.UUID,
    session: SessionDep,
    service: Annotated[CallService, Depends(get_call_service)],
) -> CallResponse:
    return await service.get_call(call_id)


@router.patch(
    "/calls/{call_id}/notes",
    response_model=CallResponse,
    summary="Update call notes",
    responses={404: {"description": "Call not found"}},
)
@session_manager
async def update_call_notes(
    call_id: uuid.UUID,
    payload: UpdateCallNotesRequest,
    session: SessionDep,
    service: Annotated[CallService, Depends(get_call_service)],
) -> CallResponse:
    """Set or clear the free-text note on a call.

    Send ``{"notes": "..."}`` to set it, ``{"notes": null}`` (or a blank string) to clear it. The
    note is NFC-normalized and trimmed; an absent ``notes`` key is rejected with 422.
    """
    return await service.update_notes(call_id, payload.notes)


@router.post(
    "/webhook/call",
    response_model=CallResponse,
    summary="Ingest a call-completion webhook (update + AI enrichment)",
    responses={
        401: {"description": "Missing or invalid webhook signature (when WEBHOOK_SECRET is set)"},
        404: {"description": "Call not found"},
        422: {"description": "Invalid webhook payload"},
    },
    dependencies=[Depends(verify_webhook_signature)],
)
@session_manager
async def webhook_call(
    payload: WebhookCallPayload,
    session: SessionDep,
    service: Annotated[CallService, Depends(get_call_service)],
    enricher: EnricherDep,
) -> CallResponse:
    """Update a call from its closing webhook and, for terminal calls with a transcript, enrich it.

    Finds the call by ``call_id`` and updates ``status``, ``duration_seconds``, ``raw_transcript``
    and ``ended_at``. When the new status is ``success``/``failed`` and a transcript is present, an
    OpenAI summary and ``CallLabel`` classification are generated and stored; if OpenAI is
    unavailable the field update still persists and ``summary``/``label`` stay null. Re-delivery is
    idempotent (no re-stamp, no re-enrichment once summarized).

    When ``WEBHOOK_SECRET`` is configured the request must carry a valid HMAC ``X-Signature`` and a
    fresh ``X-Timestamp`` (replay window); otherwise it is rejected with 401. See ADR-0007.
    """
    return await service.ingest_webhook(payload, enricher)
