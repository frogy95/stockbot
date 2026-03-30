"""당일 청산 강제 — 14:50 시장가 매도 + 재시작 시 미청산 처리."""

import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.clients.kis_rest import KISRestClient, OrderRequest
from core.config import settings
from core.models.trading import Order, PositionRecord, TradeHistory
from core.redis import RedisClient

logger = logging.getLogger(__name__)

MISFIRE_GRACE_TIME = 60


class EodLiquidator:
    """장 종료 전 미청산 포지션을 강제 청산하는 모듈.

    - 14:50 크론잡으로 시장가 매도
    - 14:30 이후 신규 진입 차단 플래그
    - 서버 재시작 시 미청산 즉시 처리
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        rest_client: KISRestClient,
        redis_client: RedisClient,
    ):
        self._session_factory = session_factory
        self._rest_client = rest_client
        self._redis = redis_client
        self._force_close_time = time(14, 50)
        self._no_entry_time = time(14, 30)

    def _now_kst(self) -> datetime:
        return datetime.now(ZoneInfo(settings.MARKET_TIMEZONE))

    def is_entry_blocked(self) -> bool:
        """14:30 이후 신규 진입 차단 여부."""
        return self._now_kst().time() >= self._no_entry_time

    async def liquidate_all(self) -> int:
        """모든 활성 포지션을 시장가로 강제 청산한다.

        Returns:
            청산된 포지션 수
        """
        now = self._now_kst()
        count = 0

        async with self._session_factory() as session:
            result = await session.execute(select(PositionRecord))
            positions = result.scalars().all()

            if not positions:
                logger.info("미청산 포지션 없음 — 강제 청산 스킵")
                return 0

            for pos in positions:
                order_req = OrderRequest(
                    stock_code=pos.stock_code,
                    order_type="sell",
                    quantity=pos.quantity,
                    price=0,
                    order_division="01",
                )

                try:
                    resp = await self._rest_client.place_order(order_req)
                    order_no = resp.order_no
                except Exception:
                    logger.exception(
                        "강제 청산 주문 실패: %s", pos.stock_code
                    )
                    order_no = ""

                order = Order(
                    stock_code=pos.stock_code,
                    order_type="sell",
                    order_no=order_no,
                    quantity=pos.quantity,
                    price=0,
                    order_division="01",
                    status="filled" if order_no else "failed",
                    submitted_at=now,
                    filled_at=now if order_no else None,
                )
                session.add(order)

                holding_sec = int((now - pos.entry_time).total_seconds())
                history = TradeHistory(
                    stock_code=pos.stock_code,
                    strategy_name=pos.strategy_name,
                    entry_price=pos.avg_price,
                    exit_price=pos.current_price or pos.avg_price,
                    quantity=pos.quantity,
                    realized_pnl=pos.unrealized_pnl,
                    pnl_rate=(
                        (int(pos.current_price or pos.avg_price) - int(pos.avg_price))
                        / int(pos.avg_price)
                        * 100
                        if int(pos.avg_price) > 0
                        else 0.0
                    ),
                    holding_duration_sec=holding_sec,
                    entry_time=pos.entry_time,
                    exit_time=now,
                    exit_reason="eod",
                )
                session.add(history)
                count += 1

            await session.execute(delete(PositionRecord))
            await session.commit()

        logger.info("강제 청산 완료: %d건", count)
        return count

    async def check_and_liquidate_on_startup(self) -> None:
        """앱 시작 시 14:50 이후 미청산 포지션이 있으면 즉시 청산."""
        now = self._now_kst()
        if now.time() < self._force_close_time:
            return

        async with self._session_factory() as session:
            result = await session.execute(
                select(PositionRecord.id).limit(1)
            )
            has_positions = result.scalar_one_or_none() is not None

        if has_positions:
            logger.warning(
                "서버 재시작 시 미청산 포지션 발견 (현재 %s) — 즉시 청산 실행",
                now.strftime("%H:%M:%S"),
            )
            await self.liquidate_all()

    async def register_schedule(self, scheduler: AsyncIOScheduler) -> None:
        """APScheduler에 14:50 크론잡 등록."""
        tz = ZoneInfo(settings.MARKET_TIMEZONE)
        scheduler.add_job(
            self.liquidate_all,
            CronTrigger(hour=14, minute=50, timezone=tz),
            id="eod_force_liquidate",
            misfire_grace_time=MISFIRE_GRACE_TIME,
        )
        logger.info("당일 청산 크론잡 등록: 14:50 KST")
