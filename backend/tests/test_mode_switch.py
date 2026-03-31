"""모드 전환 보호 API + 감사 로그 테스트."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from api.deps import get_current_user, UserInfo
from main import create_app


@pytest.fixture
def app():
    """lifespan 비활성화 테스트 앱."""
    test_app = create_app()
    test_app.router.lifespan_context = None
    test_app.dependency_overrides[get_current_user] = lambda: UserInfo(
        username="admin", trading_env="paper"
    )
    yield test_app
    test_app.dependency_overrides.clear()


def _mock_db_with_setting(value="paper", has_position=False):
    """DB 세션 mock — settings + positions 조회용."""
    session = AsyncMock()

    setting = MagicMock()
    setting.key = "trading_env"
    setting.value = value
    setting.value_type = "str"
    setting.category = "trading"
    setting.description = "거래 환경"

    setting_result = MagicMock()
    setting_result.scalar_one_or_none.return_value = setting
    setting_result.scalar_one.return_value = 1 if has_position else 0

    session.execute = AsyncMock(return_value=setting_result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


# ── 모드 전환 테스트 ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mode_switch_success(app, monkeypatch):
    """PUT /settings/mode -- 정상 전환 -> 200."""
    monkeypatch.setattr("api.routes.settings.settings.ADMIN_PASSWORD", "correct-pw")

    session = _mock_db_with_setting("paper")

    # 장외 시간으로 고정 (07:00 KST)
    fixed_dt = datetime(2026, 3, 31, 7, 0, 0, tzinfo=timezone.utc)
    with patch("api.routes.settings.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_dt

        from api.deps import get_db
        async def override_db():
            yield session
        app.dependency_overrides[get_db] = override_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                "/api/v1/settings/mode",
                json={"target_env": "live", "password": "correct-pw"},
            )

    assert resp.status_code == 200
    assert resp.json()["trading_env"] == "live"


@pytest.mark.asyncio
async def test_mode_switch_wrong_password(app, monkeypatch):
    """PUT /settings/mode -- 잘못된 비밀번호 -> 403."""
    monkeypatch.setattr("api.routes.settings.settings.ADMIN_PASSWORD", "correct-pw")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.put(
            "/api/v1/settings/mode",
            json={"target_env": "live", "password": "wrong-pw"},
        )

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_mode_switch_during_market_hours(app, monkeypatch):
    """PUT /settings/mode -- 장중(09:00~15:30 KST) -> 423."""
    monkeypatch.setattr("api.routes.settings.settings.ADMIN_PASSWORD", "pw")

    # 장중 시간 (09:30 KST = 00:30 UTC)
    fixed_dt = datetime(2026, 3, 31, 0, 30, 0, tzinfo=timezone.utc)
    with patch("api.routes.settings.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_dt

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                "/api/v1/settings/mode",
                json={"target_env": "live", "password": "pw"},
            )

    assert resp.status_code == 423


@pytest.mark.asyncio
async def test_mode_switch_with_active_position(app, monkeypatch):
    """PUT /settings/mode -- 활성 포지션 존재 -> 409."""
    monkeypatch.setattr("api.routes.settings.settings.ADMIN_PASSWORD", "pw")

    session = _mock_db_with_setting("paper", has_position=True)

    # 장외 시간
    fixed_dt = datetime(2026, 3, 31, 7, 0, 0, tzinfo=timezone.utc)
    with patch("api.routes.settings.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_dt

        from api.deps import get_db
        async def override_db():
            yield session
        app.dependency_overrides[get_db] = override_db

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                "/api/v1/settings/mode",
                json={"target_env": "live", "password": "pw"},
            )

    assert resp.status_code == 409


# ── 감사 로그 조회 테스트 ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_audit_logs(app):
    """GET /audit/logs -> 200 + 배열."""
    log = MagicMock()
    log.id = 1
    log.action = "mode_switch"
    log.target_key = "trading_env"
    log.old_value = "paper"
    log.new_value = "live"
    log.actor = "admin"
    log.ip_address = "127.0.0.1"
    log.created_at = datetime(2026, 3, 31, 10, 0, 0)

    result = MagicMock()
    result.scalars.return_value.all.return_value = [log]

    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    from api.deps import get_db
    async def override_db():
        yield session
    app.dependency_overrides[get_db] = override_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/audit/logs")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert data[0]["action"] == "mode_switch"
