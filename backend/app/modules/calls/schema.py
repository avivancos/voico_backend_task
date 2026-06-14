import uuid
from datetime import datetime
from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import Text
from sqlmodel import Column, DateTime, Field, SQLModel


class CallStatus(str, Enum):
    in_progress = "in_progress"
    success = "success"
    failed = "failed"


class CallLabel(str, Enum):
    sales_inquiry = "Sales inquiry"
    support = "Support"
    complaint = "Complaint"
    appointment = "Appointment"
    follow_up = "Follow-up"
    other = "Other"


class CallSortField(str, Enum):
    """Whitelist of columns the list endpoint may sort by.

    Closed by construction: an unknown value is a 422 at the HTTP boundary, so the sort column can
    never be interpolated from arbitrary input. Internal/audit columns (raw_transcript, notes, the
    Task 4 queue columns) are deliberately absent — they are neither public nor sortable.
    """

    created_at = "created_at"
    started_at = "started_at"
    duration_seconds = "duration_seconds"
    caller_name = "caller_name"
    phone_number = "phone_number"
    status = "status"
    label = "label"


class SortDir(str, Enum):
    asc = "asc"
    desc = "desc"


class Call(SQLModel, table=True):
    __tablename__ = "calls"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
    )
    phone_number: str = Field(index=True)
    caller_name: Optional[str] = Field(default=None, index=True)
    duration_seconds: Optional[int] = Field(default=None, index=True)
    status: CallStatus = Field(default=CallStatus.in_progress, index=True)
    summary: Optional[str] = Field(default=None)
    label: Optional[CallLabel] = Field(default=None, index=True)
    started_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, nullable=False),
    )
    ended_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime, nullable=True),
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, nullable=False, index=True),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime, nullable=False),
    )
    raw_transcript: Optional[str] = Field(default=None)
    # Free-text user annotation (Task 1). No index — it is never filtered or sorted on.
    notes: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))


# --- Request / Response schemas ---


class WebhookCallPayload(SQLModel):
    call_id: uuid.UUID
    status: CallStatus
    duration_seconds: Optional[int] = None
    raw_transcript: Optional[str] = None
    ended_at: Optional[datetime] = None


class UpdateCallNotesRequest(BaseModel):
    """Required-but-nullable notes payload.

    The ``notes`` key must be present — an empty body ``{}`` is a 422. An explicit ``null`` (or a
    blank/whitespace string, normalized in the service) clears the note. The 2000-character cap is
    enforced here, before normalization. ``extra="forbid"`` makes the model fail-closed: any extra
    field (e.g. an attempt to over-post ``status``/``summary``) is rejected with 422, so this
    endpoint can never become a mass-assignment vector.
    """

    model_config = ConfigDict(extra="forbid")

    notes: Optional[Annotated[str, StringConstraints(max_length=2000)]]


class CallResponse(SQLModel):
    id: uuid.UUID
    phone_number: str
    caller_name: Optional[str]
    duration_seconds: Optional[int]
    status: CallStatus
    summary: Optional[str]
    label: Optional[CallLabel]
    started_at: datetime
    ended_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    raw_transcript: Optional[str]
    notes: Optional[str]


class CallCounts(SQLModel):
    in_progress: int = 0
    success: int = 0
    failed: int = 0


class PaginatedCallsResponse(SQLModel):
    data: list[CallResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    counts: CallCounts
