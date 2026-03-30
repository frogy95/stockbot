"""시드 ETF 50종목 테스트."""

import pytest
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.seed_etf import SEED_ETFS, seed_etfs

SPOT_CODES = {"069500", "122630", "114800", "252670", "102110"}
REQUIRED_FIELDS = {"stock_code", "stock_name", "stock_type", "market_type", "etf_type", "leverage_ratio"}
REQUIRED_BRANDS = {"KODEX", "TIGER", "KBSTAR", "ARIRANG", "HANARO"}


def test_seed_etfs_count():
    assert len(SEED_ETFS) >= 50


def test_seed_etfs_spot_check():
    codes = {e["stock_code"] for e in SEED_ETFS}
    missing = SPOT_CODES - codes
    assert not missing, f"spot-check 종목 누락: {missing}"


def test_seed_etfs_required_fields():
    for etf in SEED_ETFS:
        missing = REQUIRED_FIELDS - etf.keys()
        assert not missing, f"{etf['stock_code']} 필수 필드 누락: {missing}"


def test_seed_etfs_brands_covered():
    names = " ".join(e["stock_name"] for e in SEED_ETFS)
    for brand in REQUIRED_BRANDS:
        assert brand in names, f"{brand} 계열 종목 없음"


@pytest.mark.asyncio
async def test_seed_etfs_upserts():
    session = AsyncMock(spec=AsyncSession)
    count = await seed_etfs(session)
    assert count == len(SEED_ETFS)
    assert session.execute.called
    assert session.commit.called
