"""Coverage for internal wiring the behavioral suites don't reach: the ``@session_manager`` guard,
the real ``get_session`` dependency (normally overridden in tests), and the get-by-id 404 path.
All exercised for real — no mocks.
"""

import uuid

import pytest

from app.core.decorators import session_manager
from app.modules.calls.router import get_session

pytestmark = pytest.mark.integration


async def test_session_manager_requires_a_session_kwarg():
    @session_manager
    async def handler(*, session=None):  # pragma: no cover - body never runs (guard fires first)
        return "ok"

    with pytest.raises(RuntimeError, match="requires a"):
        await handler()  # no session kwarg -> the guard raises before the body


async def test_get_session_yields_a_real_session():
    # The genuine dependency (tests normally override it). Drive the generator once to exercise it.
    agen = get_session()
    session = await agen.__anext__()
    try:
        assert session is not None
    finally:
        await agen.aclose()  # runs the `async with` exit -> closes the session


async def test_get_call_unknown_id_is_404(client):
    resp = await client.get(f"/api/calls/{uuid.uuid4()}")
    assert resp.status_code == 404
