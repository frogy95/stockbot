"""trading_mode 설정 + 모드 전환 API 테스트."""
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


def _mock_db(trading_mode="semi-auto", position_count=0):
    """DB 세션 mock — trading_mode 설정 + 포지션 조회용."""
    session = AsyncMock()

    setting = MagicMock()
    setting.key = "trading_mode"
    setting.value = trading_mode
    setting.value_type = "string"
    setting.category = "trading"
    setting.description = "매매 모드 (manual/semi-auto/auto)"

    # 첫 번째 execute: 포지션 count (scalar_one)
    # 두 번째 execute: trading_mode 조회 (scalar_one_or_none)
    position_result = MagicMock()
    position_result.scalar_one.return_value = position_count

    setting_result = MagicMock()
    setting_result.scalar_one_or_none.return_value = setting

    session.execute = AsyncMock(side_effect=[position_result, setting_result])
    session.add = MagicMock()
    session.commit = AsyncMock()
    return session


def _override_db(session):
    from api.deps import get_db
    async def override():
        yield session
    return override


# ── seed_settings 기본값 테스트 ────────────────────────────────────────────


def test_seed_settings_has_trading_mode():
    """SEED_DATA에 trading_mode 항목이 존재하고 기본값이 semi-auto인지 확인."""
    from scripts.seed_settings import SEED_DATA
    matches = [s for s in SEED_DATA if s[0] == "trading_mode"]
    assert len(matches) == 1, "SEED_DATA에 trading_mode 항목이 없습니다"
    key, value, value_type, category, description = matches[0]
    assert value == "semi-auto"
    assert value_type == "string"
    assert category == "trading"


# ── 모드 전환 API 테스트 ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trading_mode_switch_to_auto_success(app, monkeypatch):
    """PUT /settings/trading-mode -- auto 전환 성공 (장외, 포지션 없음) -> 200."""
    monkeypatch.setattr("api.routes.settings.settings.ADMIN_PASSWORD", "correct-pw")

    session = _mock_db("semi-auto", position_count=0)
    app.dependency_overrides[__import__("api.deps", fromlist=["get_db"]).get_db] = _override_db(session)

    # 장외 시간 (07:00 KST = 22:00 UTC 전날)
    fixed_dt = datetime(2026, 4, 7, 22, 0, 0, tzinfo=timezone.utc)
    with patch("api.routes.settings.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_dt

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                "/api/v1/settings/trading-mode",
                json={"target_mode": "auto", "password": "correct-pw"},
            )

    assert resp.status_code == 200
    assert resp.json()["trading_mode"] == "auto"


@pytest.mark.asyncio
async def test_trading_mode_switch_wrong_password(app, monkeypatch):
    """PUT /settings/trading-mode -- 잘못된 비밀번호 -> 403."""
    monkeypatch.setattr("api.routes.settings.settings.ADMIN_PASSWORD", "correct-pw")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.put(
            "/api/v1/settings/trading-mode",
            json={"target_mode": "auto", "password": "wrong-pw"},
        )

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_trading_mode_switch_during_market_hours(app, monkeypatch):
    """PUT /settings/trading-mode -- 장중(09:00~15:30 KST) -> 423."""
    monkeypatch.setattr("api.routes.settings.settings.ADMIN_PASSWORD", "pw")

    # 장중 시간 (10:00 KST = 01:00 UTC)
    fixed_dt = datetime(2026, 4, 7, 1, 0, 0, tzinfo=timezone.utc)
    with patch("api.routes.settings.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_dt

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                "/api/v1/settings/trading-mode",
                json={"target_mode": "auto", "password": "pw"},
            )

    assert resp.status_code == 423


@pytest.mark.asyncio
async def test_trading_mode_switch_to_auto_with_position_blocked(app, monkeypatch):
    """PUT /settings/trading-mode -- auto 전환 시 활성 포지션 있으면 -> 409."""
    monkeypatch.setattr("api.routes.settings.settings.ADMIN_PASSWORD", "pw")

    session = _mock_db("semi-auto", position_count=2)
    app.dependency_overrides[__import__("api.deps", fromlist=["get_db"]).get_db] = _override_db(session)

    fixed_dt = datetime(2026, 4, 7, 22, 0, 0, tzinfo=timezone.utc)
    with patch("api.routes.settings.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_dt

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                "/api/v1/settings/trading-mode",
                json={"target_mode": "auto", "password": "pw"},
            )

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_trading_mode_switch_to_semi_auto_with_position_allowed(app, monkeypatch):
    """PUT /settings/trading-mode -- auto->semi-auto 전환은 포지션 있어도 허용 -> 200."""
    monkeypatch.setattr("api.routes.settings.settings.ADMIN_PASSWORD", "pw")

    # semi-auto나 manual로의 전환은 포지션 체크 건너뜀
    session = AsyncMock()
    setting = MagicMock()
    setting.key = "trading_mode"
    setting.value = "auto"
    setting_result = MagicMock()
    setting_result.scalar_one_or_none.return_value = setting
    session.execute = AsyncMock(return_value=setting_result)
    session.add = MagicMock()
    session.commit = AsyncMock()

    app.dependency_overrides[__import__("api.deps", fromlist=["get_db"]).get_db] = _override_db(session)

    fixed_dt = datetime(2026, 4, 7, 22, 0, 0, tzinfo=timezone.utc)
    with patch("api.routes.settings.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_dt

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                "/api/v1/settings/trading-mode",
                json={"target_mode": "semi-auto", "password": "pw"},
            )

    assert resp.status_code == 200
    assert resp.json()["trading_mode"] == "semi-auto"


@pytest.mark.asyncio
async def test_trading_mode_switch_invalid_mode(app, monkeypatch):
    """PUT /settings/trading-mode -- 허용되지 않은 모드 값 -> 422."""
    monkeypatch.setattr("api.routes.settings.settings.ADMIN_PASSWORD", "pw")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.put(
            "/api/v1/settings/trading-mode",
            json={"target_mode": "turbo", "password": "pw"},
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_trading_mode_switch_records_audit_log(app, monkeypatch):
    """PUT /settings/trading-mode -- AuditLog에 기록 확인."""
    monkeypatch.setattr("api.routes.settings.settings.ADMIN_PASSWORD", "pw")

    session = _mock_db("semi-auto", position_count=0)
    app.dependency_overrides[__import__("api.deps", fromlist=["get_db"]).get_db] = _override_db(session)

    fixed_dt = datetime(2026, 4, 7, 22, 0, 0, tzinfo=timezone.utc)
    with patch("api.routes.settings.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_dt

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.put(
                "/api/v1/settings/trading-mode",
                json={"target_mode": "auto", "password": "pw"},
            )

    assert resp.status_code == 200
    # session.add가 AuditLog 포함하여 호출되었는지 확인
    assert session.add.called
    added_objects = [call.args[0] for call in session.add.call_args_list]
    from core.models.audit_log import AuditLog
    audit_calls = [obj for obj in added_objects if isinstance(obj, AuditLog)]
    assert len(audit_calls) == 1
    assert audit_calls[0].action == "trading_mode_switch"
    assert audit_calls[0].target_key == "trading_mode"
