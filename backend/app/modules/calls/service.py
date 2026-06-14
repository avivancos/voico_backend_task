import logging
import unicodedata
import uuid
from typing import Optional

from fastapi import HTTPException, status

from app.core.time import now_utc
from app.modules.calls.repository import CallRepository
from app.modules.calls.schema import (
    CallCounts,
    CallLabel,
    CallResponse,
    CallSortField,
    CallStatus,
    PaginatedCallsResponse,
    SortDir,
)

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
