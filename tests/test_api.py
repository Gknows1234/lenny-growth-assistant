from collections.abc import AsyncIterator

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.main import app


async def test_session_api_contract() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    transport = httpx.ASGITransport(app=app)
    headers = {"X-User-Id": "api-test"}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/api/sessions", json={"user_metadata": {"role": "evaluator"}}, headers=headers
        )
        listed = await client.get("/api/sessions", headers=headers)
        detail = await client.get(f"/api/sessions/{created.json()['id']}", headers=headers)

    assert created.status_code == 201
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == created.json()["id"]
    assert detail.json()["messages"] == []
    app.dependency_overrides.clear()
    await engine.dispose()


async def test_validation_errors_are_structured() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/sessions/abc/messages", json={"content": ""})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["details"]["trace_id"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["server-timing"].startswith("app;dur=")
