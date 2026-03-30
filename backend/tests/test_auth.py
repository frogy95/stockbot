import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

from main import create_app


@pytest.fixture
def app():
    return create_app()


async def _get_token(client: AsyncClient, password: str = "testpass123") -> str:
    resp = await client.post("/api/v1/auth/login", json={"password": password})
    return resp.json().get("access_token", "")


@pytest.mark.asyncio
async def test_login_success(app):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("api.routes.auth.settings") as mock_settings:
                mock_settings.ADMIN_PASSWORD = "testpass123"
                mock_settings.JWT_SECRET = "test-secret"
                mock_settings.JWT_EXPIRY_HOURS = 24
                mock_settings.TRADING_ENV = "paper"

                with patch("api.routes.auth.redis_client") as mock_redis:
                    mock_redis.get = AsyncMock(return_value=None)
                    mock_redis.set = AsyncMock(return_value=True)
                    mock_redis.delete = AsyncMock(return_value=True)

                    resp = await client.post(
                        "/api/v1/auth/login", json={"password": "testpass123"}
                    )

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "expires_in" in data


@pytest.mark.asyncio
async def test_login_wrong_password(app):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("api.routes.auth.settings") as mock_settings:
                mock_settings.ADMIN_PASSWORD = "testpass123"
                mock_settings.JWT_SECRET = "test-secret"
                mock_settings.JWT_EXPIRY_HOURS = 24

                with patch("api.routes.auth.redis_client") as mock_redis:
                    mock_redis.get = AsyncMock(return_value=None)
                    mock_redis.set = AsyncMock(return_value=True)
                    mock_redis.expire = AsyncMock(return_value=True)

                    resp = await client.post(
                        "/api/v1/auth/login", json={"password": "wrongpassword"}
                    )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_locked_after_5_failures(app):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("api.routes.auth.settings") as mock_settings:
                mock_settings.ADMIN_PASSWORD = "testpass123"
                mock_settings.JWT_SECRET = "test-secret"
                mock_settings.JWT_EXPIRY_HOURS = 24

                with patch("api.routes.auth.redis_client") as mock_redis:
                    # 5회 실패 상태 시뮬레이션
                    mock_redis.get = AsyncMock(return_value=b"5")

                    resp = await client.post(
                        "/api/v1/auth/login", json={"password": "wrongpassword"}
                    )

    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_auth_me_with_valid_token(app):
    import jwt as pyjwt
    from datetime import datetime, timedelta, timezone

    token = pyjwt.encode(
        {
            "sub": "admin",
            "exp": datetime.now(timezone.utc) + timedelta(hours=24),
            "trading_env": "paper",
        },
        "test-secret",
        algorithm="HS256",
    )

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("api.deps.settings") as mock_settings:
                mock_settings.JWT_SECRET = "test-secret"
                mock_settings.TRADING_ENV = "paper"

                resp = await client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {token}"},
                )

    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "admin"
    assert "trading_env" in data


@pytest.mark.asyncio
async def test_auth_me_with_invalid_token(app):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer invalid-token"},
            )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_token_refresh(app):
    import jwt as pyjwt
    from datetime import datetime, timedelta, timezone

    token = pyjwt.encode(
        {
            "sub": "admin",
            "exp": datetime.now(timezone.utc) + timedelta(hours=24),
            "trading_env": "paper",
        },
        "test-secret",
        algorithm="HS256",
    )

    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("api.routes.auth.settings") as mock_settings:
                mock_settings.JWT_SECRET = "test-secret"
                mock_settings.JWT_EXPIRY_HOURS = 24
                mock_settings.TRADING_ENV = "paper"

                with patch("api.deps.settings") as mock_deps_settings:
                    mock_deps_settings.JWT_SECRET = "test-secret"
                    mock_deps_settings.TRADING_ENV = "paper"

                    resp = await client.post(
                        "/api/v1/auth/refresh",
                        headers={"Authorization": f"Bearer {token}"},
                    )

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_health_no_auth_required(app):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/health")

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_login_no_auth_required(app):
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("api.routes.auth.settings") as mock_settings:
                mock_settings.ADMIN_PASSWORD = ""
                mock_settings.JWT_SECRET = "test-secret"
                mock_settings.JWT_EXPIRY_HOURS = 24

                with patch("api.routes.auth.redis_client") as mock_redis:
                    mock_redis.get = AsyncMock(return_value=None)

                    # 빈 비밀번호이면 401 (비밀번호 미설정 시 로그인 차단)
                    resp = await client.post(
                        "/api/v1/auth/login", json={"password": "anything"}
                    )

    assert resp.status_code == 401
