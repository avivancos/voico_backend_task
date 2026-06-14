import math
import re
import uuid
from typing import Any, Optional

from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.calls.schema import Call, CallLabel, CallSortField, CallStatus, SortDir

# Whitelisted sort target -> ORM column. The router validates the key via the CallSortField enum,
# so this mapping is total and the column is never built from a raw string. Values are ORM column
# expressions; typed Any because SQLModel surfaces table attributes as their Python field type.
_SORT_COLUMNS: dict[CallSortField, Any] = {
    CallSortField.created_at: Call.created_at,
    CallSortField.started_at: Call.started_at,
    CallSortField.duration_seconds: Call.duration_seconds,
    CallSortField.caller_name: Call.caller_name,
    CallSortField.phone_number: Call.phone_number,
    CallSortField.status: Call.status,
    CallSortField.label: Call.label,
}

# Separators stripped from phone numbers so a digit-only search matches a formatted stored value.
_PHONE_SEPARATORS = (" ", "(", ")", "-", "+", ".", "/")


def _escape_like(term: str) -> str:
    """Escape LIKE/ILIKE metacharacters so user input is matched literally, not as a pattern."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _phone_digits_expr(column: Any) -> Any:
    """SQL expression that strips separators from a phone column down to bare digits."""
    expr = column
    for ch in _PHONE_SEPARATORS:
        expr = func.replace(expr, ch, "")
    return expr


class CallRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, call_id: uuid.UUID) -> Optional[Call]:
        result = await self.session.exec(select(Call).where(Call.id == call_id))
        return result.first()

    def _content_filters(
        self,
        *,
        caller_name: Optional[str],
        phone: Optional[str],
        label: Optional[CallLabel],
        min_duration: Optional[int],
        max_duration: Optional[int],
    ) -> list[Any]:
        """Build every filter *except* status (status drives `total`; these drive `counts`)."""
        caller_col: Any = Call.caller_name
        phone_col: Any = Call.phone_number
        label_col: Any = Call.label
        duration_col: Any = Call.duration_seconds

        filters: list[Any] = []

        caller_term = caller_name.strip() if caller_name else ""
        if caller_term:  # a blank/whitespace-only term degrades to "no caller filter"
            pattern = f"%{_escape_like(caller_term)}%"
            filters.append(caller_col.ilike(pattern, escape="\\"))

        if phone:
            digits = re.sub(r"\D", "", phone)
            if digits:  # a non-digit-only search term degrades to "no phone filter"
                filters.append(_phone_digits_expr(phone_col).like(f"%{digits}%"))

        if label is not None:
            filters.append(label_col == label)

        if min_duration is not None:
            filters.append(duration_col >= min_duration)
        if max_duration is not None:
            filters.append(duration_col <= max_duration)

        return filters

    async def list_calls(
        self,
        *,
        status: Optional[CallStatus],
        caller_name: Optional[str],
        phone: Optional[str],
        label: Optional[CallLabel],
        min_duration: Optional[int],
        max_duration: Optional[int],
        sort_by: CallSortField,
        sort_dir: SortDir,
        page: int,
        page_size: int,
    ) -> tuple[list[Call], int, int, dict[str, int]]:
        content_filters = self._content_filters(
            caller_name=caller_name,
            phone=phone,
            label=label,
            min_duration=min_duration,
            max_duration=max_duration,
        )

        # One aggregate query yields the per-status breakdown over the content filters. `counts`
        # ignores the status tab (so the tabs stay informative); `total` is derived from it and
        # *does* respect status. This replaces the scaffold's 4 separate COUNT queries.
        agg = (
            select(Call.status, func.count())  # type: ignore[call-overload]
            .where(*content_filters)
            .group_by(Call.status)
        )
        counts: dict[str, int] = {s.value: 0 for s in CallStatus}
        for row_status, n in (await self.session.exec(agg)).all():
            key = row_status.value if isinstance(row_status, CallStatus) else str(row_status)
            counts[key] = n

        total = counts[status.value] if status is not None else sum(counts.values())

        data_filters = list(content_filters)
        if status is not None:
            data_filters.append(Call.status == status)

        sort_col: Any = _SORT_COLUMNS[sort_by]
        id_col: Any = Call.id
        direction = sort_col.asc() if sort_dir == SortDir.asc else sort_col.desc()
        # NULLs always sort last (rows missing the value go to the bottom either way), making the
        # order deterministic across SQLite/Postgres rather than relying on a backend default.
        primary = direction.nulls_last()
        # Stable tiebreaker on the primary key so equal sort keys never reorder across pages.
        order = [primary, id_col.asc()]

        offset = (page - 1) * page_size
        query = select(Call).where(*data_filters).order_by(*order).offset(offset).limit(page_size)
        calls = list((await self.session.exec(query)).all())

        total_pages = math.ceil(total / page_size) if total > 0 else 1
        return calls, total, total_pages, counts

    async def update(self, call: Call) -> Call:
        self.session.add(call)
        await self.session.flush()
        await self.session.refresh(call)
        return call
