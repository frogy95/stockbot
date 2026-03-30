"""네이버 뉴스 센티멘트 수집기 테스트."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from modules.collector.sources.naver import NaverCollector


# ---------------------------------------------------------------------------
# calc_sentiment 테스트 (순수 함수 — 모킹 불필요)
# ---------------------------------------------------------------------------

class TestCalcSentiment:
    """NaverCollector.calc_sentiment 단위 테스트."""

    def test_positive_keyword(self):
        """긍정 키워드가 있으면 양수 반환."""
        score = NaverCollector.calc_sentiment("삼성전자 상승 기대감 고조")
        assert score > 0.0

    def test_negative_keyword(self):
        """부정 키워드가 있으면 음수 반환."""
        score = NaverCollector.calc_sentiment("삼성전자 하락 악재 우려")
        assert score < 0.0

    def test_no_keyword(self):
        """긍정/부정 키워드 없으면 0.0 반환."""
        score = NaverCollector.calc_sentiment("삼성전자 실적 발표 예정")
        assert score == 0.0

    def test_html_tags_removed(self):
        """HTML 태그 제거 후 키워드 분석."""
        # <b>상승</b> → '상승'으로 인식해야 함
        score_with_tags = NaverCollector.calc_sentiment("<b>상승</b> 기대")
        score_plain = NaverCollector.calc_sentiment("상승 기대")
        assert score_with_tags == score_plain
        assert score_with_tags > 0.0

    def test_html_tags_removed_negative(self):
        """HTML 태그 안의 부정 키워드도 정상 인식."""
        score = NaverCollector.calc_sentiment("주가 <b>하락</b> 전망")
        assert score < 0.0

    def test_clamp_upper(self):
        """점수가 +1.0을 초과하지 않음."""
        # 긍정 키워드 대량 포함
        title = " ".join(["상승", "호재", "급등", "신고가", "흑자", "성장", "호실적", "매수", "상한가", "돌파"])
        score = NaverCollector.calc_sentiment(title)
        assert score <= 1.0

    def test_clamp_lower(self):
        """점수가 -1.0 미만이 되지 않음."""
        # 부정 키워드 대량 포함
        title = " ".join(["하락", "악재", "급락", "적자", "손실", "감소", "매도", "하한가", "폭락"])
        score = NaverCollector.calc_sentiment(title)
        assert score >= -1.0

    def test_both_positive_and_negative(self):
        """긍정/부정 둘 다 있으면 차이로 계산."""
        # 긍정 2개, 부정 1개 → 양수
        score = NaverCollector.calc_sentiment("상승 호재 하락")
        assert score > 0.0

    def test_empty_string(self):
        """빈 문자열은 0.0 반환."""
        score = NaverCollector.calc_sentiment("")
        assert score == 0.0


# ---------------------------------------------------------------------------
# _parse_pub_date 테스트
# ---------------------------------------------------------------------------

class TestParsePubDate:
    """NaverCollector._parse_pub_date 단위 테스트."""

    def test_valid_rfc2822(self):
        """RFC 2822 형식 정상 파싱."""
        result = NaverCollector._parse_pub_date("Mon, 30 Mar 2026 08:00:00 +0900")
        assert isinstance(result, datetime)
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 30

    def test_invalid_format_returns_none(self):
        """잘못된 형식이면 None 반환."""
        result = NaverCollector._parse_pub_date("2026-03-30 08:00:00")
        assert result is None

    def test_empty_string_returns_none(self):
        """빈 문자열이면 None 반환."""
        result = NaverCollector._parse_pub_date("")
        assert result is None

    def test_garbage_string_returns_none(self):
        """쓰레기 문자열이면 None 반환."""
        result = NaverCollector._parse_pub_date("not a date at all!!!")
        assert result is None


# ---------------------------------------------------------------------------
# search_news 테스트 (httpx 모킹)
# ---------------------------------------------------------------------------

class TestSearchNews:
    """NaverCollector.search_news 단위 테스트."""

    @pytest.mark.asyncio
    async def test_returns_items_list(self):
        """네이버 API 응답의 items 리스트를 반환한다."""
        mock_session = AsyncMock(spec=AsyncSession)
        collector = NaverCollector(mock_session)

        fake_items = [
            {
                "title": "삼성전자 <b>상승</b> 기대",
                "link": "https://news.naver.com/1",
                "pubDate": "Mon, 30 Mar 2026 08:00:00 +0900",
            },
            {
                "title": "삼성전자 실적 발표",
                "link": "https://news.naver.com/2",
                "pubDate": "Mon, 30 Mar 2026 09:00:00 +0900",
            },
        ]
        response_json = {"items": fake_items, "total": 2}

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = response_json

        with patch("modules.collector.sources.naver.httpx.AsyncClient") as mock_client:
            mock_ctx = AsyncMock()
            mock_ctx.get.return_value = mock_resp
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            items = await collector.search_news("삼성전자", display=2)

        assert len(items) == 2
        assert items[0]["link"] == "https://news.naver.com/1"

    @pytest.mark.asyncio
    async def test_http_error_returns_empty_list(self):
        """HTTP 오류 시 빈 리스트 반환."""
        mock_session = AsyncMock(spec=AsyncSession)
        collector = NaverCollector(mock_session)

        with patch("modules.collector.sources.naver.httpx.AsyncClient") as mock_client:
            mock_ctx = AsyncMock()
            mock_ctx.get.side_effect = Exception("network error")
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            items = await collector.search_news("삼성전자")

        assert items == []


# ---------------------------------------------------------------------------
# collect_sentiments 테스트 (DB + httpx 모킹)
# ---------------------------------------------------------------------------

class TestCollectSentiments:
    """NaverCollector.collect_sentiments 단위 테스트."""

    @pytest.mark.asyncio
    async def test_returns_collected_count(self):
        """수집 건수를 정확히 반환한다."""
        mock_session = AsyncMock(spec=AsyncSession)
        collector = NaverCollector(mock_session)

        stock_info = [{"stock_code": "005930", "stock_name": "삼성전자"}]
        fake_items = [
            {
                "title": "삼성전자 <b>상승</b> 급등",
                "link": "https://news.naver.com/1",
                "pubDate": "Mon, 30 Mar 2026 08:00:00 +0900",
            },
            {
                "title": "삼성전자 실적 발표",
                "link": "https://news.naver.com/2",
                "pubDate": "Mon, 30 Mar 2026 09:00:00 +0900",
            },
        ]
        response_json = {"items": fake_items}

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = response_json

        with patch("modules.collector.sources.naver.httpx.AsyncClient") as mock_client:
            mock_ctx = AsyncMock()
            mock_ctx.get.return_value = mock_resp
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            count = await collector.collect_sentiments(stock_info)

        assert count == 2
        assert mock_session.add.call_count == 2
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_stocks(self):
        """여러 종목 처리 시 각각 커밋된다."""
        mock_session = AsyncMock(spec=AsyncSession)
        collector = NaverCollector(mock_session)

        stock_info = [
            {"stock_code": "005930", "stock_name": "삼성전자"},
            {"stock_code": "000660", "stock_name": "SK하이닉스"},
        ]
        fake_items = [
            {
                "title": "뉴스 제목",
                "link": "https://news.naver.com/1",
                "pubDate": "Mon, 30 Mar 2026 08:00:00 +0900",
            },
        ]
        response_json = {"items": fake_items}

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = response_json

        with patch("modules.collector.sources.naver.httpx.AsyncClient") as mock_client:
            mock_ctx = AsyncMock()
            mock_ctx.get.return_value = mock_resp
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch("modules.collector.sources.naver.asyncio.sleep", new_callable=AsyncMock):
                count = await collector.collect_sentiments(stock_info)

        # 종목 2개 × 뉴스 1건 = 2건
        assert count == 2
        # 종목마다 commit 1회 = 총 2회
        assert mock_session.commit.call_count == 2

    @pytest.mark.asyncio
    async def test_news_api_error_skips_stock(self):
        """뉴스 API 에러 시 해당 종목 스킵, 0 반환."""
        mock_session = AsyncMock(spec=AsyncSession)
        collector = NaverCollector(mock_session)

        stock_info = [{"stock_code": "005930", "stock_name": "삼성전자"}]

        with patch("modules.collector.sources.naver.httpx.AsyncClient") as mock_client:
            mock_ctx = AsyncMock()
            mock_ctx.get.side_effect = Exception("network error")
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_ctx)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            count = await collector.collect_sentiments(stock_info)

        assert count == 0
        mock_session.add.assert_not_called()
