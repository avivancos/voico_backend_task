"""Webhook authentication: HMAC signature + replay window (Task 4).

The webhook is a publicly reachable, unauthenticated endpoint, so when a signing secret is
configured we require each request to prove it came from the caller that holds the secret and that
it is fresh (not a captured request replayed later).

Design (opt-in, see ADR-0007):
- ``WEBHOOK_SECRET`` empty -> accept unsigned requests (dev / the README Swagger demo).
- ``WEBHOOK_SECRET`` set -> require ``X-Signature: sha256=<hex>`` = HMAC-SHA256 over
  ``"{X-Timestamp}.{raw_body}"`` and an ``X-Timestamp`` (Unix seconds) within
  ``WEBHOOK_TOLERANCE_SECONDS`` of now. Signature compared in constant time; the timestamp both
  bounds replay and is bound into the MAC so it cannot be tampered with independently.
"""

import hashlib
import hmac
import logging
from datetime import datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi import status as http_status

from app.core.config import settings
from app.core.time import now_utc, to_unix

logger = logging.getLogger(__name__)


def get_now() -> datetime:
    """Current time as a dependency, so the replay-window check is deterministic in tests."""
    return now_utc()


def _unauthorized(reason: str) -> HTTPException:
    # Log server-side; return a single opaque message so probing can't distinguish failure modes.
    logger.warning("Rejected webhook: %s", reason)
    return HTTPException(
        status_code=http_status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature"
    )


async def verify_webhook_signature(
    request: Request,
    now: Annotated[datetime, Depends(get_now)],
) -> None:
    """Reject the request (401) unless it is correctly signed and fresh. No-op when unconfigured."""
    secret = settings.webhook_secret
    if not secret:
        return

    signature = request.headers.get("X-Signature")
    timestamp = request.headers.get("X-Timestamp")
    if not signature or not timestamp:
        raise _unauthorized("missing X-Signature/X-Timestamp")

    try:
        ts = int(timestamp)
    except ValueError:
        raise _unauthorized("non-numeric X-Timestamp")

    if abs(to_unix(now) - ts) > settings.webhook_tolerance_seconds:
        raise _unauthorized("timestamp outside tolerance window")

    body = await request.body()
    expected = hmac.new(
        secret.encode("utf-8"), timestamp.encode("utf-8") + b"." + body, hashlib.sha256
    ).hexdigest()
    provided = signature[len("sha256=") :] if signature.startswith("sha256=") else signature
    if not hmac.compare_digest(expected, provided):
        raise _unauthorized("signature mismatch")
