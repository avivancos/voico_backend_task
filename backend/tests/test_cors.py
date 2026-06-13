"""CORS must be an explicit allow-list, never wildcard + credentials."""


async def test_preflight_allows_configured_origin(client):
    response = await client.options(
        "/api/calls",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    # Credentials must NOT be enabled (no auth) — avoids the invalid "*" + credentials combo.
    assert response.headers.get("access-control-allow-credentials") != "true"


async def test_preflight_rejects_unknown_origin(client):
    response = await client.options(
        "/api/calls",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in response.headers
