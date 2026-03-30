"""시드 ETF 50종목 — 최초 설치 시 stocks 테이블 초기 적재용."""

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.stock import Stock

SEED_ETFS: list[dict] = [
    # ── KODEX (삼성자산운용) ─────────────────────────────────────────────────
    {"stock_code": "069500", "stock_name": "KODEX 200", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": "KOSPI200"},
    {"stock_code": "122630", "stock_name": "KODEX 레버리지", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "leverage", "leverage_ratio": 2, "underlying_index": "KOSPI200"},
    {"stock_code": "114800", "stock_name": "KODEX 인버스", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "inverse", "leverage_ratio": -1, "underlying_index": "KOSPI200"},
    {"stock_code": "252670", "stock_name": "KODEX 200선물인버스2X", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "inverse", "leverage_ratio": -2, "underlying_index": "KOSPI200"},
    {"stock_code": "229200", "stock_name": "KODEX 코스닥150", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": "KOSDAQ150"},
    {"stock_code": "233740", "stock_name": "KODEX 코스닥150레버리지", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "leverage", "leverage_ratio": 2, "underlying_index": "KOSDAQ150"},
    {"stock_code": "251340", "stock_name": "KODEX 코스닥150인버스", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "inverse", "leverage_ratio": -1, "underlying_index": "KOSDAQ150"},
    {"stock_code": "278530", "stock_name": "KODEX 삼성그룹", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    {"stock_code": "091160", "stock_name": "KODEX 반도체", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    {"stock_code": "091180", "stock_name": "KODEX 은행", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    {"stock_code": "140710", "stock_name": "KODEX 운송", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    {"stock_code": "157490", "stock_name": "KODEX 미국S&P500선물(H)", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": "SP500"},
    {"stock_code": "379800", "stock_name": "KODEX 미국S&P500", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": "SP500"},
    {"stock_code": "133690", "stock_name": "KODEX 나스닥100", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": "NASDAQ100"},
    {"stock_code": "304940", "stock_name": "KODEX 2차전지산업", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    # ── TIGER (미래에셋자산운용) ─────────────────────────────────────────────
    {"stock_code": "102110", "stock_name": "TIGER 200", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": "KOSPI200"},
    {"stock_code": "143460", "stock_name": "TIGER 코스닥150", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": "KOSDAQ150"},
    {"stock_code": "360750", "stock_name": "TIGER 미국S&P500", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": "SP500"},
    {"stock_code": "381170", "stock_name": "TIGER 차이나전기차SOLACTIVE", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    {"stock_code": "305720", "stock_name": "TIGER 2차전지테마", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    {"stock_code": "148020", "stock_name": "TIGER 농산물선물(H)", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    {"stock_code": "130680", "stock_name": "TIGER 원유선물Enhanced(H)", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    {"stock_code": "139230", "stock_name": "TIGER 글로벌리츠(합성H)", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    {"stock_code": "195980", "stock_name": "TIGER 골드선물(H)", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    {"stock_code": "329200", "stock_name": "TIGER 미국채10년선물", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    {"stock_code": "441680", "stock_name": "TIGER 미국배당다우존스", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    {"stock_code": "364980", "stock_name": "TIGER 차이나항셍테크", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    # ── KBSTAR (KB자산운용) ──────────────────────────────────────────────────
    {"stock_code": "261220", "stock_name": "KBSTAR 200", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": "KOSPI200"},
    {"stock_code": "273130", "stock_name": "KBSTAR ESG사회책임투자", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    {"stock_code": "396500", "stock_name": "KBSTAR 미국S&P500", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": "SP500"},
    {"stock_code": "463050", "stock_name": "KBSTAR 미국나스닥100", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": "NASDAQ100"},
    {"stock_code": "292150", "stock_name": "KBSTAR 코스닥150", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": "KOSDAQ150"},
    {"stock_code": "322410", "stock_name": "KBSTAR 금현물", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    {"stock_code": "238720", "stock_name": "KBSTAR 200IT", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    {"stock_code": "365590", "stock_name": "KBSTAR 글로벌클린에너지", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    # ── ARIRANG (한화자산운용) ───────────────────────────────────────────────
    {"stock_code": "152100", "stock_name": "ARIRANG 200", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": "KOSPI200"},
    {"stock_code": "161510", "stock_name": "ARIRANG 고배당주", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    {"stock_code": "297090", "stock_name": "ARIRANG 미국S&P500(H)", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": "SP500"},
    {"stock_code": "195930", "stock_name": "ARIRANG 선진국MSCI(합성H)", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    {"stock_code": "252710", "stock_name": "ARIRANG 코스닥150", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": "KOSDAQ150"},
    {"stock_code": "371160", "stock_name": "ARIRANG 글로벌게임&이스포츠", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    # ── HANARO (NH아문디자산운용) ────────────────────────────────────────────
    {"stock_code": "293180", "stock_name": "HANARO 200", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": "KOSPI200"},
    {"stock_code": "385560", "stock_name": "HANARO 글로벌럭셔리S&P(합성)", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    {"stock_code": "334700", "stock_name": "HANARO 코스피", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    {"stock_code": "381180", "stock_name": "HANARO Fn K-POP&미디어", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    {"stock_code": "352560", "stock_name": "HANARO 200선물인버스", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "inverse", "leverage_ratio": -1, "underlying_index": "KOSPI200"},
    {"stock_code": "441640", "stock_name": "HANARO 미국배당다우존스", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": ""},
    # ── 기타 주요 ETF ────────────────────────────────────────────────────────
    {"stock_code": "411060", "stock_name": "ACE 미국S&P500", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": "SP500"},
    {"stock_code": "449170", "stock_name": "SOL 미국S&P500", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": "SP500"},
    {"stock_code": "458730", "stock_name": "PLUS 미국S&P500", "stock_type": "ETF", "market_type": "KOSPI", "etf_type": "normal", "leverage_ratio": 1, "underlying_index": "SP500"},
]


async def seed_etfs(db_session: AsyncSession) -> int:
    """SEED_ETFS를 stocks 테이블에 upsert. 시드된 종목 수 반환."""
    values = [
        {
            "stock_code": e["stock_code"],
            "stock_name": e["stock_name"],
            "market": "kr",
            "market_type": e["market_type"],
            "stock_type": e["stock_type"],
            "is_active": True,
            "extra_data": {
                "etf_type": e["etf_type"],
                "leverage_ratio": e["leverage_ratio"],
                "underlying_index": e.get("underlying_index", ""),
                "source": "seed",
            },
        }
        for e in SEED_ETFS
    ]

    stmt = pg_insert(Stock).values(values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["stock_code"],
        set_={
            "stock_name": stmt.excluded.stock_name,
            "stock_type": stmt.excluded.stock_type,
            "is_active": True,
            "extra_data": stmt.excluded.extra_data,
        },
    )
    await db_session.execute(stmt)
    await db_session.commit()
    return len(values)
