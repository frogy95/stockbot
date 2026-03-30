"""KIS 종목 마스터 수집기 테스트."""

import io
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from modules.collector.sources.kis_master import KISMasterCollector


def _make_zip(filename: str, content: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(filename, content)
    return buf.getvalue()


def _make_mst_record(
    stock_code: str,
    stock_name: str,
    etp_prod_type: str = "1",
) -> bytes:
    """mst 레코드 바이트 생성 (CP949 고정길이 포맷, _RECORD_LEN=200)."""
    record = bytearray(200)
    record[0:9] = stock_code.encode("cp949").ljust(9)
    record[9:21] = ("KR7" + stock_code + "0007").encode("cp949").ljust(12)[:12]
    record[21:61] = stock_name.encode("cp949").ljust(40)[:40]
    record[121:122] = etp_prod_type.encode("cp949")
    return bytes(record)


def _new_collector() -> KISMasterCollector:
    session = AsyncMock(spec=AsyncSession)
    # scalar()는 동기 호출이므로 MagicMock으로 None 반환
    mock_result = MagicMock()
    mock_result.scalar.return_value = None
    session.execute = AsyncMock(return_value=mock_result)
    return KISMasterCollector(session)


# ── parse_kospi_mst ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_parse_kospi_mst_etf():
    collector = _new_collector()
    raw = _make_mst_record("069500", "KODEX 200", "1")
    records = collector.parse_kospi_mst(raw)

    etf = next((r for r in records if r["stock_code"] == "069500"), None)
    assert etf is not None
    assert etf["stock_name"] == "KODEX 200"
    assert etf["market_type"] == "KOSPI"
    assert etf["etp_prod_type"] == "1"


@pytest.mark.asyncio
async def test_parse_kospi_mst_normal_stock():
    collector = _new_collector()
    raw = _make_mst_record("005930", "삼성전자", " ")
    records = collector.parse_kospi_mst(raw)

    samsung = next((r for r in records if r["stock_code"] == "005930"), None)
    assert samsung is not None
    assert samsung["etp_prod_type"].strip() == ""


# ── parse_kosdaq_mst ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_parse_kosdaq_mst_etf():
    collector = _new_collector()
    raw = _make_mst_record("122630", "KODEX 레버리지", "1")
    records = collector.parse_kosdaq_mst(raw)

    etf = next((r for r in records if r["stock_code"] == "122630"), None)
    assert etf is not None
    assert etf["market_type"] == "KOSDAQ"


# ── filter_etf ───────────────────────────────────────────────────────────────

def test_filter_etf_keeps_etf():
    collector = _new_collector()
    records = [
        {"stock_code": "069500", "stock_name": "KODEX 200", "etp_prod_type": "1", "market_type": "KOSPI"},
        {"stock_code": "005930", "stock_name": "삼성전자", "etp_prod_type": " ", "market_type": "KOSPI"},
    ]
    result = collector.filter_etf(records)
    assert len(result) == 1
    assert result[0]["stock_code"] == "069500"
    assert result[0]["stock_type"] == "ETF"


def test_filter_etf_keeps_etn():
    collector = _new_collector()
    records = [{"stock_code": "500001", "stock_name": "신한 레버리지 WTI원유 ETN", "etp_prod_type": "2", "market_type": "KOSPI"}]
    result = collector.filter_etf(records)
    assert len(result) == 1
    assert result[0]["stock_type"] == "ETN"


def test_filter_etf_excludes_normal():
    collector = _new_collector()
    records = [
        {"stock_code": "005930", "stock_name": "삼성전자", "etp_prod_type": " ", "market_type": "KOSPI"},
        {"stock_code": "000660", "stock_name": "SK하이닉스", "etp_prod_type": "", "market_type": "KOSPI"},
    ]
    assert collector.filter_etf(records) == []


# ── enrich_etf_metadata ──────────────────────────────────────────────────────

@pytest.mark.parametrize("name,expected_type,expected_ratio", [
    ("KODEX 레버리지", "leverage", 2),
    ("KODEX 인버스", "inverse", -1),
    ("KODEX 200선물인버스2X", "inverse", -2),
    ("KODEX 나스닥3X", "leverage", 3),
    ("KODEX 200", "normal", 1),
    ("TIGER 200", "normal", 1),
])
def test_enrich_metadata(name, expected_type, expected_ratio):
    collector = _new_collector()
    records = [{"stock_code": "999999", "stock_name": name, "stock_type": "ETF"}]
    result = collector.enrich_etf_metadata(records)
    assert result[0]["etf_type"] == expected_type
    assert result[0]["leverage_ratio"] == expected_ratio


# ── sanity_check ─────────────────────────────────────────────────────────────

def _etf_list_with_spots(extra: int = 0) -> list[dict]:
    spot_codes = ["069500", "122630", "114800", "252670", "102110"]
    base = [{"stock_code": f"{i:06d}"} for i in range(200 + extra)]
    for code in spot_codes:
        base.append({"stock_code": code})
    return base


def test_sanity_check_pass():
    assert KISMasterCollector(_new_collector()._db).sanity_check(_etf_list_with_spots()) is True


def test_sanity_check_fail_count():
    etf_list = [{"stock_code": f"{i:06d}"} for i in range(100)]
    assert KISMasterCollector(_new_collector()._db).sanity_check(etf_list) is False


def test_sanity_check_fail_spot():
    etf_list = [{"stock_code": f"{i:06d}"} for i in range(250)]
    assert KISMasterCollector(_new_collector()._db).sanity_check(etf_list) is False


def test_sanity_check_fail_delta():
    etf_list = _etf_list_with_spots()
    assert KISMasterCollector(_new_collector()._db).sanity_check(etf_list, prev_count=500) is False


# ── sync_to_db ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_to_db_upserts_etf():
    session = AsyncMock(spec=AsyncSession)
    collector = KISMasterCollector(session)
    etf_list = [{
        "stock_code": "069500", "stock_name": "KODEX 200", "stock_type": "ETF",
        "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": "KOSPI200",
    }]
    count = await collector.sync_to_db(etf_list)
    assert count == 1
    assert session.execute.called


# ── download_mst ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_download_mst_success():
    collector = _new_collector()
    mst_content = b"A" * 200
    zip_bytes = _make_zip("kospi_code.mst", mst_content)

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.content = zip_bytes

    with patch("modules.collector.sources.kis_master.httpx.AsyncClient") as mock_client:
        mock_ctx = AsyncMock()
        mock_ctx.get.return_value = mock_resp
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await collector.download_mst("kospi")

    assert result == mst_content


@pytest.mark.asyncio
async def test_download_mst_retry():
    collector = _new_collector()
    mst_content = b"B" * 200
    zip_bytes = _make_zip("kospi_code.mst", mst_content)

    mock_resp_ok = MagicMock()
    mock_resp_ok.raise_for_status = MagicMock()
    mock_resp_ok.content = zip_bytes

    call_count = 0

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("network error")
        return mock_resp_ok

    with patch("modules.collector.sources.kis_master.httpx.AsyncClient") as mock_client:
        mock_ctx = AsyncMock()
        mock_ctx.get.side_effect = side_effect
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await collector.download_mst("kospi", retry_delay=0)

    assert result == mst_content
    assert call_count == 2


@pytest.mark.asyncio
async def test_download_mst_all_fail():
    collector = _new_collector()
    with patch("modules.collector.sources.kis_master.httpx.AsyncClient") as mock_client:
        mock_ctx = AsyncMock()
        mock_ctx.get.side_effect = Exception("network error")
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(Exception):
            await collector.download_mst("kospi", retry_delay=0)


# ── collect 통합 ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_collect_normal_flow():
    collector = _new_collector()
    spot_codes = ["069500", "122630", "114800", "252670", "102110"]
    kospi_data = b"".join(_make_mst_record(c, f"ETF_{c}", "1") for c in spot_codes)
    kospi_data += b"".join(_make_mst_record(f"{i:06d}", f"ETF_{i}", "1") for i in range(250))
    kosdaq_data = b"".join(_make_mst_record(f"{i:06d}", f"KOSDAQ_ETF_{i}", "1") for i in range(10))

    async def fake_download(market: str, retry_delay: float = 10.0) -> bytes:
        return kospi_data if market == "kospi" else kosdaq_data

    with patch.object(collector, "download_mst", side_effect=fake_download):
        result = await collector.collect()

    assert result["source"] == "mst"
    assert result["sanity_passed"] is True
    assert result["etf_count"] > 0


@pytest.mark.asyncio
async def test_collect_fallback_on_download_failure():
    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar.return_value = 1
    session.execute = AsyncMock(return_value=mock_result)
    collector = KISMasterCollector(session)

    async def fake_download_fail(market: str, retry_delay: float = 10.0) -> bytes:
        raise Exception("network error")

    with patch.object(collector, "download_mst", side_effect=fake_download_fail):
        result = await collector.collect()

    assert result["source"] == "existing_db"
    assert result["sanity_passed"] is False
