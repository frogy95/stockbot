"""수집 스케줄러 — APScheduler 기반 장전/장중/장후 데이터 수집 오케스트레이션."""

import json
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.clients.kis_rest import KISRestClient
from core.redis import RedisClient
from modules.collector.sources.data_go_kr import DataGoKrCollector
from modules.collector.sources.kis_collector import KISCollector
from modules.collector.sources.kis_realtime import (
    parse_raw_message,
    parse_execution,
    parse_orderbook,
)
from modules.collector.ws_manager import WSSubscriptionManager
from modules.collector.trade_strength import TradeStrengthCalculator
from core.clients.kis_ws import KISWebSocketClient

logger = logging.getLogger(__name__)

MISFIRE_GRACE_TIME = 60  # 초
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
    ) -> None:
        self._session_factory = session_factory
        self._rest_client = rest_client
        self._ws_manager = ws_manager
        self._trade_strength = trade_strength
        self._ws_client = ws_client
        self._redis = redis
        self._scheduler = AsyncIOScheduler()
        self._running = False
        self._last_premarket: datetime | None = None
        self._last_etf: datetime | None = None

    async def start(self) -> None:
        """스케줄러 시작 + job 등록."""
        self._scheduler.add_job(
            self._premarket_collect,
            CronTrigger(hour=8, minute=0),
            id="premarket_collect",
            misfire_grace_time=MISFIRE_GRACE_TIME,
        )
        self._scheduler.add_job(
            self._etf_collect,
            CronTrigger(hour=8, minute=5),
            id="etf_collect",
            misfire_grace_time=MISFIRE_GRACE_TIME,
        )
        self._scheduler.add_job(
            self._market_open,
            CronTrigger(hour=9, minute=0),
            id="market_open",
            misfire_grace_time=MISFIRE_GRACE_TIME,
        )
        self._scheduler.add_job(
            self._market_close,
            CronTrigger(hour=15, minute=30),
            id="market_close",
            misfire_grace_time=MISFIRE_GRACE_TIME,
        )
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
        }

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
            self._last_premarket = datetime.now()
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
            self._last_etf = datetime.now()
            logger.info("ETF 수집 완료: %d종목", count)
            return count
        except Exception:
            logger.exception("ETF 수집 실패")
            return 0

    async def _market_open(self) -> None:
        """09:00 WS 연결 + 구독 시작."""
        logger.info("장중 시작: WS 연결")
        try:
            self._ws_client.set_on_data(self._on_realtime_data)
            await self._ws_client.connect()
            logger.info("WS 연결 완료, 구독 대기")
        except Exception:
            logger.exception("WS 연결 실패")

    async def _market_close(self) -> None:
        """15:30 WS 구독 해제 + 연결 종료."""
        logger.info("장후 시작: WS 종료")
        try:
            await self._ws_manager.unsubscribe_all()
            await self._ws_client.disconnect()
            logger.info("WS 종료 완료")
        except Exception:
            logger.exception("WS 종료 실패")

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
