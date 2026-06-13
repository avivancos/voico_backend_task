"""End-to-end smoke tests proving the harness wires the real app to a real DB."""


async def test_health_ok(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_list_calls_empty(client):
    response = await client.get("/api/calls")
    assert response.status_code == 200
    body = response.json()
    assert body["data"] == []
    assert body["total"] == 0
    assert body["counts"] == {"in_progress": 0, "success": 0, "failed": 0}


async def test_query_counter_fixture_works(client, count_queries):
    await client.get("/api/calls")
    assert count_queries["n"] > 0
