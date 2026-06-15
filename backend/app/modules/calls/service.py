import logging
import unicodedata
import uuid
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status

from app.core.time import now_utc
from app.modules.calls.enrichment import Enricher
from app.modules.calls.repository import CallRepository
from app.modules.calls.schema import (
    CallCounts,
    CallLabel,
    CallResponse,
    CallSortField,
    CallStatus,
    PaginatedCallsResponse,
    SortDir,
    WebhookCallPayload,
)

_TERMINAL_STATUSES = (CallStatus.success, CallStatus.failed)

logger = logging.getLogger(__name__)


def _normalize_notes(notes: Optional[str]) -> Optional[str]:
    """NFC-normalize and strip; treat null/empty/whitespace-only as "no note" (NULL)."""
    if notes is None:
        return None
    cleaned = unicodedata.normalize("NFC", notes).strip()
    return cleaned or None


class CallService:
    def __init__(self, repository: CallRepository) -> None:
        self.repository = repository

    async def list_calls(
        self,
        *,
        status: Optional[CallStatus] = None,
        caller_name: Optional[str] = None,
        phone: Optional[str] = None,
        label: Optional[CallLabel] = None,
        min_duration: Optional[int] = None,
        max_duration: Optional[int] = None,
        sort_by: CallSortField = CallSortField.created_at,
        sort_dir: SortDir = SortDir.desc,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedCallsResponse:
        calls, total, total_pages, counts = await self.repository.list_calls(
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
        return PaginatedCallsResponse(
            data=[CallResponse.model_validate(c, from_attributes=True) for c in calls],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            counts=CallCounts(
                in_progress=counts.get("in_progress", 0),
                success=counts.get("success", 0),
                failed=counts.get("failed", 0),
            ),
        )

    async def get_call(self, call_id: uuid.UUID) -> CallResponse:
        call = await self.repository.get_by_id(call_id)
        if call is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
        return CallResponse.model_validate(call, from_attributes=True)

    async def expire_stale_calls(self, *, now: datetime, threshold_minutes: float) -> int:
        """Mark calls stuck in_progress past the threshold as failed; return how many changed."""
        return await self.repository.expire_stale(now=now, threshold_minutes=threshold_minutes)

    async def update_notes(self, call_id: uuid.UUID, notes: Optional[str]) -> CallResponse:
        call = await self.repository.get_by_id(call_id)
        if call is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")
        normalized = _normalize_notes(notes)
        if normalized != call.notes:
            # Only touch the row when the note actually changes, so a redundant save does not
            # re-stamp updated_at. No DB-level onupdate — each real writer bumps it explicitly.
            call.notes = normalized
            call.updated_at = now_utc()
            await self.repository.update(call)
        return CallResponse.model_validate(call, from_attributes=True)

    async def ingest_webhook(
        self, payload: WebhookCallPayload, enricher: Optional[Enricher]
    ) -> CallResponse:
        """Apply a call-completion webhook: update the call, then best-effort AI enrichment.

        Idempotent: only fields that actually change are written (so a re-delivery does not re-stamp
        ``updated_at``), and enrichment is skipped once a summary exists (so replays don't re-spend
        on OpenAI). Enrichment failures are swallowed *here*, inside the service, so the exception
        never reaches the router's ``@session_manager`` — the field update must persist even when
        OpenAI is down (``summary``/``label`` then stay null).
        """
        call = await self.repository.get_by_id(payload.call_id)
        if call is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")

        changed = False
        if call.status != payload.status:
            call.status = payload.status
            changed = True
        if (
            payload.duration_seconds is not None
            and call.duration_seconds != payload.duration_seconds
        ):
            call.duration_seconds = payload.duration_seconds
            changed = True
        if payload.raw_transcript is not None and call.raw_transcript != payload.raw_transcript:
            call.raw_transcript = payload.raw_transcript
            changed = True
        if payload.ended_at is not None and call.ended_at != payload.ended_at:
            call.ended_at = payload.ended_at
            changed = True

        # Enrich only a terminal call that has a transcript and is not already enriched. The status
        # is the validated payload value (never derived from the transcript), so untrusted transcript
        # text cannot influence which calls get enriched or how they are classified.
        if (
            enricher is not None
            and payload.status in _TERMINAL_STATUSES
            and call.raw_transcript
            and call.summary is None
        ):
            try:
                result = await enricher.enrich(call.raw_transcript)
                call.summary = result.summary
                call.label = result.label
                changed = True
            except Exception:
                logger.exception(
                    "AI enrichment failed for call %s; leaving summary/label null", call.id
                )

        if changed:
            call.updated_at = now_utc()
            await self.repository.update(call)
        return CallResponse.model_validate(call, from_attributes=True)
