"""네이버 뉴스 센티멘트 수집기 — 키워드 기반 간이 센티멘트 점수."""

import asyncio
import logging
import re
from datetime import datetime
from email.utils import parsedate_to_datetime

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.models.news_sentiment import NewsSentiment

logger = logging.getLogger(__name__)

SEARCH_URL = "https://openapi.naver.com/v1/search/news.json"
DEFAULT_DISPLAY = 10

POSITIVE_KEYWORDS = ["상승", "호재", "급등", "신고가", "흑자", "성장", "호실적", "매수", "상한가", "돌파", "회복", "증가"]
NEGATIVE_KEYWORDS = ["하락", "악재", "급락", "적자", "손실", "감소", "매도", "하한가", "폭락", "위기", "부진", "실적악화"]


class NaverCollector:
    """네이버 뉴스 검색 API를 이용한 센티멘트 수집기."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._db = db_session

    async def search_news(self, query: str, display: int = DEFAULT_DISPLAY) -> list[dict]:
        """네이버 뉴스 검색. 에러 시 빈 리스트 반환."""
        params = {
            "query": query,
            "display": display,
            "sort": "date",
        }
        headers = {
            "X-Naver-Client-Id": settings.NAVER_CLIENT_ID,
            "X-Naver-Client-Secret": settings.NAVER_CLIENT_SECRET,
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(SEARCH_URL, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            return data.get("items", [])
        except Exception:
            logger.exception("네이버 뉴스 검색 실패: query=%s", query)
            return []

    @staticmethod
    def calc_sentiment(title: str) -> float:
        """키워드 사전 기반 간이 센티멘트 점수 계산.

        HTML 태그를 제거한 뒤 긍정/부정 키워드 카운트로 점수를 산출한다.
        score = (pos - neg) / max(pos + neg, 1), 범위 -1.0 ~ +1.0.
        """
        # HTML 태그 제거
        clean = re.sub(r"<[^>]+>", "", title)

        pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in clean)
        neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in clean)

        score = (pos - neg) / max(pos + neg, 1)
        return max(-1.0, min(1.0, score))

    async def collect_sentiments(self, stock_info: list[dict]) -> int:
        """종목 리스트의 뉴스 센티멘트를 수집해 DB에 저장한다.

        Args:
            stock_info: [{"stock_code": "...", "stock_name": "..."}] 형태의 리스트

        Returns:
            수집된 뉴스 건수
        """
        total_collected = 0

        for idx, stock in enumerate(stock_info):
            stock_code = stock["stock_code"]
            stock_name = stock["stock_name"]

            # 종목 간 딜레이 (첫 번째 종목 제외)
            if idx > 0:
                await asyncio.sleep(0.1)

            news_items = await self.search_news(stock_name, display=10)

            for news_item in news_items:
                raw_title = news_item.get("title", "")
                clean_title = re.sub(r"<[^>]+>", "", raw_title)
                score = self.calc_sentiment(raw_title)

                # 매칭된 첫 번째 키워드 추출
                matched_keyword = None
                for kw in POSITIVE_KEYWORDS:
                    if kw in clean_title:
                        matched_keyword = kw
                        break
                if matched_keyword is None:
                    for kw in NEGATIVE_KEYWORDS:
                        if kw in clean_title:
                            matched_keyword = kw
                            break

                record = NewsSentiment(
                    stock_code=stock_code,
                    title=clean_title,
                    source_url=news_item.get("link"),
                    published_at=self._parse_pub_date(news_item.get("pubDate", "")),
                    sentiment_score=score,
                    keyword=matched_keyword,
                )
                self._db.add(record)
                total_collected += 1

            await self._db.commit()

        logger.info("네이버 뉴스 센티멘트 수집 완료: %d건", total_collected)
        return total_collected

    @staticmethod
    def _parse_pub_date(pub_date_str: str) -> datetime | None:
        """RFC 2822 형식의 날짜 문자열을 datetime으로 변환. 실패 시 None 반환."""
        if not pub_date_str:
            return None
        try:
            return parsedate_to_datetime(pub_date_str)
        except Exception:
            return None
