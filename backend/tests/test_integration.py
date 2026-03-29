import pytest
from datetime import date

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings
from core.models.settings import SystemSetting
from core.models.stock import Stock
from core.models.market_data import MarketData
from core.redis import RedisClient
from main import create_app


@pytest.fixture
def engine():
    return create_async_engine(settings.database_url)


@pytest.fixture
def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.mark.asyncio
async def test_seed_data_count(session_factory):
    async with session_factory() as session:
        result = await session.execute(select(func.count()).select_from(SystemSetting))
        count = result.scalar()
    assert count == 21


@pytest.mark.asyncio
async def test_trading_env_is_paper(session_factory):
    async with session_factory() as session:
        result = await session.execute(
            select(SystemSetting).where(SystemSetting.key == "trading_env")
        )
        row = result.scalar_one()
    assert row.value == "paper"


@pytest.mark.asyncio
async def test_max_loss_value_type(session_factory):
    async with session_factory() as session:
        result = await session.execute(
            select(SystemSetting).where(SystemSetting.key == "max_loss_per_trade_pct")
        )
        row = result.scalar_one()
    assert row.value_type == "float"


@pytest.mark.asyncio
async def test_stock_crud(session_factory):
    async with session_factory() as session:
        stock = Stock(
            stock_code="005930",
            stock_name="삼성전자",
            market="kr",
            market_type="KOSPI",
            stock_type="stock",
        )
        session.add(stock)
        await session.commit()

        result = await session.execute(
            select(Stock).where(Stock.stock_code == "005930")
        )
        found = result.scalar_one()
        assert found.stock_name == "삼성전자"

        await session.delete(found)
        await session.commit()


@pytest.mark.asyncio
async def test_market_data_fk(session_factory):
    async with session_factory() as session:
        stock = Stock(
            stock_code="TEST01",
            stock_name="테스트종목",
            market="kr",
            market_type="KOSPI",
            stock_type="stock",
        )
        session.add(stock)
        await session.flush()

        md = MarketData(
            stock_code="TEST01",
            data_date=date(2026, 3, 28),
            close_price=50000,
            volume=1000,
            source="test",
        )
        session.add(md)
        await session.commit()

        result = await session.execute(
            select(MarketData).where(MarketData.stock_code == "TEST01")
        )
        found = result.scalar_one()
        assert found.close_price == 50000

        await session.delete(found)
        await session.execute(select(Stock).where(Stock.stock_code == "TEST01"))
        s = (await session.execute(select(Stock).where(Stock.stock_code == "TEST01"))).scalar_one()
        await session.delete(s)
        await session.commit()


@pytest.mark.asyncio
async def test_market_data_unique_constraint(session_factory):
    async with session_factory() as session:
        stock = Stock(
            stock_code="TEST02",
            stock_name="유니크테스트",
            market="kr",
            market_type="KOSPI",
            stock_type="stock",
        )
        session.add(stock)
        await session.flush()

        md1 = MarketData(
            stock_code="TEST02", data_date=date(2026, 3, 28), source="test"
        )
        session.add(md1)
        await session.commit()

        md2 = MarketData(
            stock_code="TEST02", data_date=date(2026, 3, 28), source="test"
        )
        session.add(md2)
        with pytest.raises(Exception):
            await session.commit()
        await session.rollback()

        # 정리
        await session.execute(
            select(MarketData).where(MarketData.stock_code == "TEST02")
        )
        for row in (await session.execute(select(MarketData).where(MarketData.stock_code == "TEST02"))).scalars():
            await session.delete(row)
        for row in (await session.execute(select(Stock).where(Stock.stock_code == "TEST02"))).scalars():
            await session.delete(row)
        await session.commit()


@pytest.mark.asyncio
async def test_health_api():
    app = create_app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_redis_ping():
    client = RedisClient(settings.redis_url)
    await client.connect()
    assert await client.ping() is True
    await client.disconnect()
