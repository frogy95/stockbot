"""수집 스케줄러 — APScheduler 기반 장전/장중/장후 데이터 수집 오케스트레이션."""

import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.config import settings
from core.models.screening_result import ScreeningResult
from core.models.stock import Stock

from core.clients.kis_rest import KISRestClient
from core.redis import RedisClient
from modules.collector.sources.data_go_kr import DataGoKrCollector
from modules.collector.sources.kis_collector import KISCollector
from modules.collector.sources.kis_master import KISMasterCollector
from modules.collector.sources.kis_realtime import (
    parse_raw_message,
    parse_execution,
    parse_orderbook,
)
from modules.collector.ws_manager import WSSubscriptionManager
from modules.collector.trade_strength import TradeStrengthCalculator
from core.clients.kis_ws import KISWebSocketClient

logger = logging.getLogger(__name__)

MISFIRE_GRACE_TIME = 300  # 초 (5분 — Railway 재시작/스케줄러 지연 대응)
REALTIME_CACHE_TTL = 5  # 초


class CollectorScheduler:
    """수집 스케줄러.

    장전(08:00) 공공데이터포털 일괄 수집, 장중(09:00~15:30) 한투 WS 실시간 수신을 관리한다.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        rest_client: KISRestClient,
        ws_manager: WSSubscriptionManager,
        trade_strength: TradeStrengthCalculator,
        ws_client: KISWebSocketClient,
        redis: RedisClient,
        primary_screener=None,
        realtime_screener=None,
    ) -> None:
        self._session_factory = session_factory
        self._rest_client = rest_client
        self._ws_manager = ws_manager
        self._trade_strength = trade_strength
        self._ws_client = ws_client
        self._redis = redis
        self._primary_screener = primary_screener
        self._realtime_screener = realtime_screener
        self._scheduler = AsyncIOScheduler()
        self._running = False
        self._last_premarket: datetime | None = None
        self._last_etf: datetime | None = None
        self._last_primary_screen: datetime | None = None
        self._last_secondary_screen: datetime | None = None
        self._last_dart: datetime | None = None
        self._last_sentiment: datetime | None = None
        self._last_etf_master: datetime | None = None
        self._telegram_bot = None  # 텔레그램 봇 (main.py에서 후속 주입)

    def set_telegram_bot(self, bot) -> None:
        """텔레그램 봇 참조 설정 (main.py에서 후속 주입)."""
        self._telegram_bot = bot

    async def start(self) -> None:
        """스케줄러 시작 + job 등록."""
        tz = ZoneInfo(settings.MARKET_TIMEZONE)
        self._scheduler.add_job(
            self._premarket_collect,
            CronTrigger(hour=8, minute=0, timezone=tz),
            id="premarket_collect",
            misfire_grace_time=MISFIRE_GRACE_TIME,
        )
        self._scheduler.add_job(
            self._etf_master_collect,
            CronTrigger(hour=8, minute=10, timezone=tz),
            id="etf_master_collect",
            misfire_grace_time=MISFIRE_GRACE_TIME,
        )
        self._scheduler.add_job(
            self._etf_collect,
            CronTrigger(hour=8, minute=15, timezone=tz),
            id="etf_collect",
            misfire_grace_time=MISFIRE_GRACE_TIME,
        )
        self._scheduler.add_job(
            self._market_open,
            CronTrigger(hour=9, minute=0, timezone=tz),
            id="market_open",
            misfire_grace_time=MISFIRE_GRACE_TIME,
        )
        self._scheduler.add_job(
            self._market_close,
            CronTrigger(hour=15, minute=30, timezone=tz),
            id="market_close",
            misfire_grace_time=MISFIRE_GRACE_TIME,
        )
        self._scheduler.add_job(
            self._market_open_recovery,
            CronTrigger(hour=9, minute=5, timezone=tz),
            id="market_open_recovery",
            misfire_grace_time=MISFIRE_GRACE_TIME,
        )
        # 1차 스크리닝: 08:10 (공공데이터포털 수집 완료 후)
        if self._primary_screener:
            self._scheduler.add_job(
                self._primary_screen,
                CronTrigger(hour=8, minute=10, timezone=tz),
                id="primary_screen",
                misfire_grace_time=MISFIRE_GRACE_TIME,
            )
        # 보조 데이터: 08:15 DART 재무, 08:20 네이버 센티멘트 (1차 스크리닝 후)
        self._scheduler.add_job(
            self._dart_collect,
            CronTrigger(hour=8, minute=15, timezone=tz),
            id="dart_collect",
            misfire_grace_time=MISFIRE_GRACE_TIME,
        )
        self._scheduler.add_job(
            self._sentiment_collect,
            CronTrigger(hour=8, minute=20, timezone=tz),
            id="sentiment_collect",
            misfire_grace_time=MISFIRE_GRACE_TIME,
        )
        # 2차 스크리닝: 09:30~15:30 30초 주기
        if self._realtime_screener:
            self._scheduler.add_job(
                self._secondary_screen,
                IntervalTrigger(seconds=30),
                id="secondary_screen",
                misfire_grace_time=MISFIRE_GRACE_TIME,
            )
            # 시작 시에는 일시 정지, _market_open에서 resume
            self._scheduler.get_job("secondary_screen").pause()
        self._scheduler.start()
        self._running = True
        logger.info("수집 스케줄러 시작")

    async def stop(self) -> None:
        """스케줄러 종료."""
        self._scheduler.shutdown(wait=False)
        self._running = False
        logger.info("수집 스케줄러 종료")

    def get_status(self) -> dict:
        """스케줄러 상태 조회."""
        jobs = []
        for job in self._scheduler.get_jobs():
            next_run = job.next_run_time
            jobs.append({
                "id": job.id,
                "next_run": next_run.isoformat() if next_run else None,
            })

        return {
            "running": self._running,
            "job_count": len(jobs),
            "next_jobs": jobs,
            "ws_subscriptions": self._ws_manager.count,
            "last_premarket": self._last_premarket.isoformat() if self._last_premarket else None,
            "last_etf": self._last_etf.isoformat() if self._last_etf else None,
            "last_etf_master": self._last_etf_master.isoformat() if self._last_etf_master else None,
            "last_dart": self._last_dart.isoformat() if self._last_dart else None,
            "last_sentiment": self._last_sentiment.isoformat() if self._last_sentiment else None,
        }

    def get_auxiliary_status(self) -> dict:
        """보조 데이터 수집 상태 조회."""
        return {
            "last_dart": self._last_dart.isoformat() if self._last_dart else None,
            "last_sentiment": self._last_sentiment.isoformat() if self._last_sentiment else None,
        }

    def get_screening_status(self) -> dict:
        """스크리닝 상태 조회."""
        return {
            "primary_last_run": (
                self._last_primary_screen.isoformat() if self._last_primary_screen else None
            ),
            "secondary_last_run": (
                self._last_secondary_screen.isoformat() if self._last_secondary_screen else None
            ),
            "secondary_interval": 30,
            "primary_screener_ready": self._primary_screener is not None,
            "realtime_screener_ready": self._realtime_screener is not None,
        }

    async def trigger_primary_screening(self) -> dict:
        """수동 1차 스크리닝 트리거."""
        if self._primary_screener is None:
            return {"candidates": 0, "passed": 0}
        return await self._primary_screen()

    async def trigger_secondary_screening(self) -> dict:
        """수동 2차 스크리닝 트리거."""
        if self._realtime_screener is None:
            return {"candidates": 0, "passed": 0}
        return await self._secondary_screen()

    async def trigger_etf_master(self) -> dict:
        """수동 ETF 마스터 갱신 트리거."""
        return await self._etf_master_collect()

    async def trigger_dart(self) -> dict:
        """수동 DART 재무 수집 트리거."""
        count = await self._dart_collect()
        return {"financials_collected": count}

    async def trigger_sentiment(self) -> dict:
        """수동 네이버 센티멘트 수집 트리거."""
        count = await self._sentiment_collect()
        return {"sentiments_collected": count}

    async def trigger_premarket(self) -> dict:
        """수동 장전 수집 트리거."""
        count = await self._premarket_collect()
        return {"stocks_collected": count}

    async def trigger_etf(self) -> dict:
        """수동 ETF 수집 트리거."""
        count = await self._etf_collect()
        return {"etfs_collected": count}

    # ── 스케줄 job ──────────────────────────────────────

    async def _premarket_collect(self) -> int:
        """08:00 공공데이터포털 전 종목 수집. 매 실행마다 독립 DB 세션 사용."""
        logger.info("장전 수집 시작")
        try:
            async with self._session_factory() as db_session:
                collector = DataGoKrCollector(db_session)
                count = await collector.collect_all()
            self._last_premarket = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE))
            logger.info("장전 수집 완료: %d종목", count)
            return count
        except Exception:
            logger.exception("장전 수집 실패")
            return 0

    async def _etf_collect(self) -> int:
        """08:05 ETF 시세 수집. 매 실행마다 독립 DB 세션 사용."""
        logger.info("ETF 수집 시작")
        try:
            async with self._session_factory() as db_session:
                collector = KISCollector(self._rest_client, db_session)
                count = await collector.collect_etf_prices()
            self._last_etf = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE))
            logger.info("ETF 수집 완료: %d종목", count)
            return count
        except Exception:
            logger.exception("ETF 수집 실패")
            return 0

    async def _etf_master_collect(self) -> dict:
        """08:10 KIS 마스터파일에서 ETF/ETN 종목 적재. 실패 시 기존 DB 유지."""
        logger.info("ETF 마스터 수집 시작")
        try:
            async with self._session_factory() as db_session:
                collector = KISMasterCollector(db_session)
                result = await collector.collect()

            if result["source"] == "seed":
                pass  # seed 폴백은 _etf_master_collect 내부가 아닌 최초 설치 스크립트에서 처리

            self._last_etf_master = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE))
            logger.info(
                "ETF 마스터 수집 완료: ETF=%d, ETN=%d, source=%s",
                result["etf_count"], result["etn_count"], result["source"],
            )
            return result
        except Exception:
            logger.exception("ETF 마스터 수집 실패")
            return {"etf_count": 0, "etn_count": 0, "source": "error", "sanity_passed": False}

    async def _market_open(self) -> None:
        """09:00 WS 연결 + 구독 시작 + 2차 스크리닝 활성화."""
        logger.info("장중 시작: WS 연결")
        try:
            self._ws_client.set_on_data(self._on_realtime_data)
            await self._ws_client.connect()
            # 2차 스크리닝 30초 주기 활성화
            job = self._scheduler.get_job("secondary_screen")
            if job:
                job.resume()
                logger.info("2차 스크리닝 30초 주기 활성화")
            logger.info("WS 연결 완료, 구독 대기")
        except Exception:
            logger.exception("WS 연결 실패")

    async def _market_open_recovery(self) -> None:
        """09:05 WS 연결 상태 확인 — 미연결 시 _market_open 재시도 + 텔레그램 경고."""
        if self._ws_manager.count > 0:
            logger.info("market_open 복구 불필요: ws_subscriptions=%d", self._ws_manager.count)
            return
        logger.warning("market_open 복구 시작: ws_subscriptions=0")
        if self._telegram_bot:
            await self._telegram_bot.send_notification(
                "<b>[장애 복구]</b> market_open 미실행 감지\n"
                "ws_subscriptions=0 → 자동 재시도 중..."
            )
        await self._market_open()
        if self._telegram_bot:
            subs = self._ws_manager.count
            status = "복구 성공" if subs > 0 else "복구 실패"
            await self._telegram_bot.send_notification(
                f"<b>[장애 복구]</b> {status}\nws_subscriptions={subs}"
            )

    async def _market_close(self) -> None:
        """15:30 WS 구독 해제 + 연결 종료 + 2차 스크리닝 중지."""
        logger.info("장후 시작: WS 종료")
        try:
            # 2차 스크리닝 일시 정지
            job = self._scheduler.get_job("secondary_screen")
            if job:
                job.pause()
                logger.info("2차 스크리닝 중지")
            await self._ws_manager.unsubscribe_all()
            await self._ws_client.disconnect()
            logger.info("WS 종료 완료")
        except Exception:
            logger.exception("WS 종료 실패")

    # ── 스크리닝 job ─────────────────────────────────────

    async def _primary_screen(self) -> dict:
        """08:10 1차 스크리닝: DB 정적 필터 + 팩터 스코어링."""
        logger.info("1차 스크리닝 시작")
        try:
            async with self._session_factory() as db_session:
                results = await self._primary_screener.screen(db_session)
                saved = await self._primary_screener.save_results(db_session, results)
                await db_session.commit()

            # 1차 결과로 WS 구독 목록 업데이트
            for item in results:
                await self._ws_manager.subscribe(
                    item["stock_code"],
                    priority=float(item.get("score", 0)),
                )

            passed = [r for r in results if r.get("is_passed")]
            self._last_primary_screen = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE))
            logger.info("1차 스크리닝 완료: %d후보, %d통과", len(results), len(passed))
            return {"candidates": len(results), "passed": len(passed)}
        except Exception as e:
            logger.exception("1차 스크리닝 실패")
            return {"candidates": 0, "passed": 0, "error": str(e)}

    async def _secondary_screen(self) -> dict:
        """장중 30초 주기 2차 스크리닝: 실시간 필터 + 팩터 스코어링."""
        logger.info("2차 스크리닝 시작")
        try:
            async with self._session_factory() as db_session:
                candidate_codes = await self._get_latest_primary_codes(db_session)

                if not candidate_codes:
                    return {"candidates": 0, "passed": 0}

                results = await self._realtime_screener.screen(candidate_codes, db_session)

            passed = [r for r in results if r.get("is_passed")]
            self._last_secondary_screen = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE))
            logger.info("2차 스크리닝 완료: %d후보, %d통과", len(candidate_codes), len(passed))
            return {"candidates": len(candidate_codes), "passed": len(passed)}
        except Exception:
            logger.exception("2차 스크리닝 실패")
            return {"candidates": 0, "passed": 0}

    async def _dart_collect(self) -> int:
        """08:15 DART 재무 데이터 수집 — 1차 스크리닝 통과 종목 대상."""
        logger.info("DART 재무 수집 시작")
        try:
            from modules.collector.sources.dart import DartCollector

            async with self._session_factory() as db_session:
                stock_codes = await self._get_latest_primary_codes(db_session)

                if not stock_codes:
                    logger.info("DART 재무 수집 대상 없음")
                    return 0

                collector = DartCollector(db_session)
                count = await collector.collect_financials(stock_codes)

            self._last_dart = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE))
            logger.info("DART 재무 수집 완료: %d건", count)
            return count
        except Exception:
            logger.exception("DART 재무 수집 실패")
            return 0

    async def _sentiment_collect(self) -> int:
        """08:20 네이버 뉴스 센티멘트 수집 — 1차 스크리닝 통과 종목 대상."""
        logger.info("네이버 센티멘트 수집 시작")
        try:
            from modules.collector.sources.naver import NaverCollector

            async with self._session_factory() as db_session:
                stock_info = await self._get_latest_primary_stock_info(db_session)

                if not stock_info:
                    logger.info("네이버 센티멘트 수집 대상 없음")
                    return 0

                collector = NaverCollector(db_session)
                count = await collector.collect_sentiments(stock_info)

            self._last_sentiment = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE))
            logger.info("네이버 센티멘트 수집 완료: %d건", count)
            return count
        except Exception:
            logger.exception("네이버 센티멘트 수집 실패")
            return 0

    # ── 내부 헬퍼 ────────────────────────────────────────

    async def _get_latest_primary_codes(self, db_session: AsyncSession) -> list[str]:
        """최신 1차 스크리닝 통과 종목 코드 목록을 반환한다 (단일 쿼리)."""
        latest_subq = (
            select(func.max(ScreeningResult.screened_at))
            .where(ScreeningResult.screening_type == "primary")
            .scalar_subquery()
        )
        stmt = select(ScreeningResult.stock_code).where(
            ScreeningResult.screening_type == "primary",
            ScreeningResult.screened_at == latest_subq,
        )
        result = await db_session.execute(stmt)
        return [row[0] for row in result.all()]

    async def _get_latest_primary_stock_info(self, db_session: AsyncSession) -> list[dict]:
        """최신 1차 스크리닝 통과 종목의 코드+종목명을 반환한다 (단일 쿼리)."""
        latest_subq = (
            select(func.max(ScreeningResult.screened_at))
            .where(ScreeningResult.screening_type == "primary")
            .scalar_subquery()
        )
        stmt = (
            select(ScreeningResult.stock_code, Stock.stock_name)
            .join(Stock, Stock.stock_code == ScreeningResult.stock_code)
            .where(
                ScreeningResult.screening_type == "primary",
                ScreeningResult.screened_at == latest_subq,
            )
        )
        result = await db_session.execute(stmt)
        return [{"stock_code": row[0], "stock_name": row[1]} for row in result.all()]

    # ── WS 수신 콜백 ───────────────────────────────────

    def _on_realtime_data(self, tr_id: str, raw_data: str) -> None:
        """WS 수신 콜백 — 파서 -> Redis 캐싱 -> 체결강도."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._process_realtime_data(tr_id, raw_data))
        except RuntimeError:
            pass

    async def _process_realtime_data(self, tr_id: str, raw_data: str) -> None:
        """실시간 데이터 처리."""
        parsed = parse_raw_message(raw_data)
        if parsed is None:
            return

        msg_tr_id, _encrypted, body = parsed

        if msg_tr_id == "H0STCNT0":
            execution = parse_execution(body)
            if execution:
                # Redis 캐싱
                await self._redis.set(
                    f"realtime:{execution.stock_code}:execution",
                    json.dumps({
                        "stock_code": execution.stock_code,
                        "time": execution.time,
                        "price": execution.price,
                        "volume": execution.volume,
                        "acml_volume": execution.acml_volume,
                        "change_rate": execution.change_rate,
                        "sell_or_buy": execution.sell_or_buy,
                    }),
                    ttl=REALTIME_CACHE_TTL,
                )
                # 체결강도 업데이트
                import time
                self._trade_strength.add_execution(
                    execution.stock_code,
                    time.time(),
                    execution.volume,
                    execution.sell_or_buy,
                )

        elif msg_tr_id == "H0STASP0":
            orderbook = parse_orderbook(body)
            if orderbook:
                await self._redis.set(
                    f"realtime:{orderbook.stock_code}:orderbook",
                    json.dumps({
                        "stock_code": orderbook.stock_code,
                        "time": orderbook.time,
                        "total_ask_volume": orderbook.total_ask_volume,
                        "total_bid_volume": orderbook.total_bid_volume,
                        "ask_count": len(orderbook.asks),
                        "bid_count": len(orderbook.bids),
                    }),
                    ttl=REALTIME_CACHE_TTL,
                )
