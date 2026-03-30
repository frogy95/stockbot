"""매매 엔진 오케스트레이터 — 스크리닝->전략->리스크->주문 통합."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo

from core.redis import RedisClient
from modules.trading.eod_liquidator import EodLiquidator
from modules.trading.order_manager import OrderManager
from modules.trading.position_manager import PositionManager
from modules.trading.position_sizer import PositionSizer
from modules.trading.risk_manager import RiskManager
from modules.trading.signal_generator import SignalGenerator

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")


class TradingEngine:
    """매매 엔진 — 전체 매매 파이프라인을 오케스트레이션한다."""

    def __init__(
        self,
        signal_generator: SignalGenerator,
        order_manager: OrderManager,
        position_manager: PositionManager,
        risk_manager: RiskManager,
        position_sizer: PositionSizer,
        eod_liquidator: EodLiquidator,
        redis_client: RedisClient,
    ):
        self._signal_generator = signal_generator
        self._order_manager = order_manager
        self._position_manager = position_manager
        self._risk_manager = risk_manager
        self._position_sizer = position_sizer
        self._eod_liquidator = eod_liquidator
        self._redis = redis_client
        self._running = False
        self._monitor_task: asyncio.Task | None = None

    async def start(self) -> None:
        """엔진 시작: 주문 워커 + 포지션 모니터링 루프."""
        await self._order_manager.start()
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_positions_loop())
        logger.info("매매 엔진 시작")

    async def stop(self) -> None:
        """엔진 종료."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        await self._order_manager.stop()
        logger.info("매매 엔진 종료")

    async def process_screening_results(
        self, screened_candidates: list[dict]
    ) -> None:
        """2차 스크리닝 결과를 받아 매매 파이프라인을 실행."""
        # 14:30 이후 신규 진입 차단
        if self._eod_liquidator.is_entry_blocked():
            logger.info("신규 진입 차단 시간대 — 신호 생성 스킵")
            return

        # 신호 생성
        signals = await self._signal_generator.generate_signals(screened_candidates)
        if not signals:
            return

        for signal in signals:
            # 레버리지 여부 판별
            is_leverage = "레버리지" in signal.reason.get("is_leverage", "") if isinstance(
                signal.reason.get("is_leverage"), str
            ) else signal.reason.get("is_leverage", False)

            # 리스크 체크
            risk_result = await self._risk_manager.can_trade(is_leverage=is_leverage)
            if not risk_result.allowed:
                logger.info(
                    "리스크 차단 [%s]: %s", signal.stock_code, risk_result.reason
                )
                continue

            # 포지션 사이징
            position_size = await self._position_sizer.calculate(
                signal.stock_code, signal.entry_price, 0
            )
            if position_size.quantity == 0:
                logger.info("주문 수량 0 — 스킵: %s", signal.stock_code)
                continue

            # 주문 제출
            await self._order_manager.submit_order(signal, position_size)
            logger.info(
                "주문 제출: %s %d주 @%d",
                signal.stock_code,
                position_size.quantity,
                signal.entry_price,
            )

    async def monitor_positions(self) -> list[dict]:
        """포지션 모니터링: 청산 조건 확인 및 처리."""
        exits = await self._position_manager.check_exit_conditions()
        return exits

    async def _monitor_positions_loop(self, interval: float = 5.0) -> None:
        """포지션 모니터링 루프 (백그라운드)."""
        while self._running:
            try:
                exits = await self._position_manager.check_exit_conditions()
                for exit_info in exits:
                    logger.info(
                        "청산 대상: %s (%s)",
                        exit_info["stock_code"],
                        exit_info["exit_reason"],
                    )
            except Exception:
                logger.exception("포지션 모니터링 오류")
            await asyncio.sleep(interval)

    async def on_order_filled(
        self, order_id: int, filled_price: int, signal: object
    ) -> None:
        """매수 주문 체결 콜백 — 포지션 생성."""
        from modules.trading.strategy import TradeSignalData

        if isinstance(signal, TradeSignalData):
            await self._position_manager.open_position(
                signal, 0, filled_price
            )

    @staticmethod
    def _get_approval_timeout_static(now: datetime) -> int:
        """시간대별 승인 타임아웃 (초)."""
        t = now.time()
        if time(9, 30) <= t <= time(10, 30):
            return 20  # 골든타임
        if time(14, 0) <= t <= time(14, 30):
            return 15  # 장 마감 전
        return 30  # 일반

    def _get_approval_timeout(self) -> int:
        """현재 시각 기반 승인 타임아웃."""
        return self._get_approval_timeout_static(datetime.now(KST))
