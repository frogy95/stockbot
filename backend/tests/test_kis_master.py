"""KIS 종목 마스터 수집기 테스트."""

import io
import zipfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from modules.collector.sources.kis_master import KISMasterCollector, SPOT_CHECK_CODES


def _make_zip(filename: str, content: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(filename, content)
    return buf.getvalue()


def _make_mst_line(
    stock_code: str,
    stock_name: str,
    sec_type: str = "EF",
    total_len: int = 288,
) -> bytes:
    """CP949 고정길이 라인 바이트 생성 (바이트 offset 기준).

    bytes 0:9 종목코드(ljust 9), 9:21 ISIN 더미(12바이트),
    21:61 종목명(CP949 ljust 40바이트), 61:63 증권구분(ljust 2바이트), 나머지 공백.
    """
    buf = bytearray(total_len)
    for i in range(total_len):
        buf[i] = 0x20  # space
    buf[0:9] = stock_code.encode("cp949").ljust(9)[:9]
    buf[9:21] = ("KR7" + stock_code + "0007").encode("cp949").ljust(12)[:12]
    buf[21:61] = stock_name.encode("cp949").ljust(40)[:40]
    buf[61:63] = sec_type.encode("cp949").ljust(2)[:2]
    return bytes(buf)


def _make_mst_bytes(lines: list[bytes]) -> bytes:
    """라인 바이트 목록을 줄바꿈으로 결합하여 반환."""
    return b"\n".join(lines)


def _new_collector() -> KISMasterCollector:
    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar.return_value = None
    session.execute = AsyncMock(return_value=mock_result)
    return KISMasterCollector(session)


# ── parse_kospi_mst ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_parse_kospi_mst_etf():
    collector = _new_collector()
    raw = _make_mst_bytes([_make_mst_line("069500", "KODEX 200", "EF")])
    records = collector.parse_kospi_mst(raw)

    etf = next((r for r in records if r["stock_code"] == "069500"), None)
    assert etf is not None
    assert etf["stock_name"] == "KODEX 200"
    assert etf["market_type"] == "KOSPI"
    assert etf["sec_type"] == "EF"


@pytest.mark.asyncio
async def test_parse_kospi_mst_normal_stock():
    collector = _new_collector()
    raw = _make_mst_bytes([_make_mst_line("005930", "삼성전자", "  ")])
    records = collector.parse_kospi_mst(raw)

    samsung = next((r for r in records if r["stock_code"] == "005930"), None)
    assert samsung is not None
    assert samsung["sec_type"].strip() == ""


@pytest.mark.asyncio
async def test_parse_mst_skips_invalid_stock_code():
    """stock_code가 6자리 숫자가 아닌 라인은 파싱 결과에서 제외된다."""
    collector = _new_collector()
    valid_line = _make_mst_line("069500", "KODEX 200", "EF")
    invalid_line = _make_mst_line("ABCDEF", "잘못된종목", "EF")
    raw = _make_mst_bytes([valid_line, invalid_line, b""])
    records = collector.parse_kospi_mst(raw)

    assert len(records) == 1
    assert records[0]["stock_code"] == "069500"


@pytest.mark.asyncio
async def test_parse_mst_skips_short_line():
    """최소 라인 길이(63바이트) 미달 라인은 스킵된다."""
    collector = _new_collector()
    short_line = b"069500" + b" " * 56  # 62바이트 — _MIN_LINE_LEN=63 미달
    raw = _make_mst_bytes([short_line])
    records = collector.parse_kospi_mst(raw)

    assert records == []


# ── parse_kosdaq_mst ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_parse_kosdaq_mst_etf():
    collector = _new_collector()
    raw = _make_mst_bytes([_make_mst_line("122630", "KODEX 레버리지", "EF")])
    records = collector.parse_kosdaq_mst(raw)

    etf = next((r for r in records if r["stock_code"] == "122630"), None)
    assert etf is not None
    assert etf["market_type"] == "KOSDAQ"


# ── filter_etf ───────────────────────────────────────────────────────────────

def test_filter_etf_keeps_etf():
    collector = _new_collector()
    records = [
        {"stock_code": "069500", "stock_name": "KODEX 200", "sec_type": "EF", "market_type": "KOSPI"},
        {"stock_code": "005930", "stock_name": "삼성전자", "sec_type": " ", "market_type": "KOSPI"},
    ]
    result = collector.filter_etf(records)
    assert len(result) == 1
    assert result[0]["stock_code"] == "069500"
    assert result[0]["stock_type"] == "ETF"


def test_filter_etf_keeps_etn():
    collector = _new_collector()
    records = [{"stock_code": "500001", "stock_name": "신한 레버리지 WTI원유 ETN", "sec_type": "EN", "market_type": "KOSPI"}]
    result = collector.filter_etf(records)
    assert len(result) == 1
    assert result[0]["stock_type"] == "ETN"


def test_filter_etf_excludes_normal():
    collector = _new_collector()
    records = [
        {"stock_code": "005930", "stock_name": "삼성전자", "sec_type": " ", "market_type": "KOSPI"},
        {"stock_code": "000660", "stock_name": "SK하이닉스", "sec_type": "", "market_type": "KOSPI"},
    ]
    assert collector.filter_etf(records) == []


def test_filter_etf_skips_unknown_sec_type():
    """알 수 없는 증권구분(예: 'XX')은 결과에서 제외된다."""
    collector = _new_collector()
    records = [{"stock_code": "999999", "stock_name": "알수없는종목", "sec_type": "XX", "market_type": "KOSPI"}]
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


def test_sanity_check_skips_variation_when_prev_low():
    """prev_count < 200이면 변동률 검증 스킵 (최소 종목수 + spot-check만)."""
    collector = _new_collector()
    # prev=150 (200 미만) — 변동률 무관하게 PASS (종목 수만 충족하면 됨)
    etf_list = [{"stock_code": c} for c in SPOT_CHECK_CODES] + [{"stock_code": f"{i:06d}"} for i in range(195)]
    assert collector.sanity_check(etf_list, prev_count=150) is True


def test_sanity_check_allows_30pct_variation():
    """prev_count >= 200이면 +-30% 변동 허용."""
    collector = _new_collector()
    etf_list = [{"stock_code": c} for c in SPOT_CHECK_CODES] + [{"stock_code": f"{i:06d}"} for i in range(595)]
    # prev=800, cur=600 → 25% 감소 → PASS
    assert collector.sanity_check(etf_list, prev_count=800) is True


def test_sanity_check_blocks_over_30pct_variation():
    """prev_count >= 200이면 +-30% 초과 시 FAIL."""
    collector = _new_collector()
    etf_list = [{"stock_code": c} for c in SPOT_CHECK_CODES] + [{"stock_code": f"{i:06d}"} for i in range(495)]
    # prev=800, cur=500 → 37.5% 감소 → FAIL
    assert collector.sanity_check(etf_list, prev_count=800) is False


def test_sanity_check_prev_none_skips_variation():
    """prev_count=None이면 변동률 검증 스킵."""
    collector = _new_collector()
    etf_list = [{"stock_code": c} for c in SPOT_CHECK_CODES] + [{"stock_code": f"{i:06d}"} for i in range(195)]
    assert collector.sanity_check(etf_list, prev_count=None) is True


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
    kospi_lines = [_make_mst_line(c, f"ETF_{c}", "EF") for c in spot_codes]
    kospi_lines += [_make_mst_line(f"{i:06d}", f"ETF_{i}", "EF") for i in range(250)]
    kospi_data = _make_mst_bytes(kospi_lines)

    kosdaq_lines = [_make_mst_line(f"{i:06d}", f"KOSDAQ_ETF_{i}", "EF") for i in range(10)]
    kosdaq_data = _make_mst_bytes(kosdaq_lines)

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
