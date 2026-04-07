"""매매 엔진 오케스트레이터 — 스크리닝->전략->리스크->주문 통합."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select

from core.models.settings import SystemSetting
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
        notifier_manager=None,
        session_factory=None,
    ):
        self._signal_generator = signal_generator
        self._order_manager = order_manager
        self._position_manager = position_manager
        self._risk_manager = risk_manager
        self._position_sizer = position_sizer
        self._eod_liquidator = eod_liquidator
        self._redis = redis_client
        self._notifier = notifier_manager
        self._session_factory = session_factory
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

    async def _get_trading_mode(self) -> str:
        """settings 테이블에서 trading_mode 조회 (Redis 캐시 활용, TTL 60초).

        session_factory가 없으면 Redis만 참조하고, 캐시 미스 시 "semi-auto" 반환.
        """
        # Redis 캐시 확인
        cached = await self._redis.get("trading:mode")
        if cached:
            return cached

        # session_factory가 없으면 기본값 반환
        if self._session_factory is None:
            return "semi-auto"

        # settings 테이블 조회
        try:
            async with self._session_factory() as session:
                stmt = select(SystemSetting).where(SystemSetting.key == "trading_mode")
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()
                mode = row.value if row else "semi-auto"

            # Redis에 60초 캐시
            await self._redis.set("trading:mode", mode, 60)
            return mode
        except Exception:
            logger.exception("trading_mode 조회 실패 — 기본값 semi-auto 사용")
            return "semi-auto"

    async def process_screening_results(
        self, screened_candidates: list[dict]
    ) -> None:
        """2차 스크리닝 결과를 받아 매매 파이프라인을 실행."""
        # 스케줄러 파이프라인 미완료 시 불완전 데이터 기반 매매 차단
        pipeline_healthy = await self._redis.get("scheduler:pipeline_healthy")
        if pipeline_healthy != "true":
            logger.warning("pipeline_healthy=%r (not 'true') — 신호 처리 차단", pipeline_healthy)
            return

        # 14:30 이후 신규 진입 차단
        if self._eod_liquidator.is_entry_blocked():
            logger.info("신규 진입 차단 시간대 — 신호 생성 스킵")
            return

        # 매매 모드 조회
        mode = await self._get_trading_mode()

        # 신호 생성
        signals = await self._signal_generator.generate_signals(screened_candidates)
        if not signals:
            return

        # stock_code → 후보 dict 매핑 (플래그 조회용)
        candidate_map: dict[str, dict] = {
            c["stock_code"]: c for c in screened_candidates if "stock_code" in c
        }

        for signal in signals:
            # manual 모드: 신호 생성(DB 저장)만, 주문/승인 모두 스킵
            if mode == "manual":
                logger.info("manual 모드 — 신호 저장만: %s", signal.stock_code)
                continue

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

            # 후보 플래그 확인 (is_fallback, is_relaxed)
            candidate = candidate_map.get(signal.stock_code, {})
            auto_trade_blocked = (
                candidate.get("is_fallback", False) or candidate.get("is_relaxed", False)
            )
            size_ratio: float = candidate.get("position_size_ratio", 1.0)

            # 포지션 사이징
            position_size = await self._position_sizer.calculate(
                signal.stock_code, signal.entry_price, 0, size_ratio=size_ratio
            )
            if position_size.quantity == 0:
                logger.info("주문 수량 0 — 스킵: %s", signal.stock_code)
                continue

            # 모드 분기
            if mode == "auto" and not auto_trade_blocked:
                # 완전 자동: 즉시 주문 + 알림
                await self._order_manager.submit_order(signal, position_size)
                logger.info(
                    "자동 주문 제출: %s %d주 @%d",
                    signal.stock_code,
                    position_size.quantity,
                    signal.entry_price,
                )
                if self._notifier:
                    text = (
                        f"[자동 주문 알림] {signal.stock_code} "
                        f"{position_size.quantity}주 @{signal.entry_price:,}원 주문 완료"
                    )
                    await self._notifier.send_notification(text)
            else:
                # 반자동 (semi-auto 또는 auto+blocked): 승인 요청
                if self._notifier:
                    timeout = self._get_approval_timeout()
                    token = await self._notifier.notify_signal(
                        signal, position_size.quantity, timeout
                    )
                    logger.info(
                        "승인 요청: %s %d주 @%d (token=%s, timeout=%ds)",
                        signal.stock_code,
                        position_size.quantity,
                        signal.entry_price,
                        token,
                        timeout,
                    )
                else:
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

    async def approve_signal(self, token: str) -> bool:
        """승인 콜백 — 토큰 검증 후 주문 실행."""
        from modules.trading.position_sizer import PositionSize
        from modules.trading.strategy import TradeSignalData

        if not self._notifier:
            return False
        result = await self._notifier.handle_approval(token, "approve")
        if result is None:
            return False
        signal = TradeSignalData(**result["signal"])
        quantity = result["quantity"]
        position_size = PositionSize(
            invest_amount=signal.entry_price * quantity,
            quantity=quantity,
            is_leverage=False,
            size_pct=0,
        )
        await self._order_manager.submit_order(signal, position_size)
        logger.info("승인 주문 실행: %s %d주", signal.stock_code, quantity)
        return True

    async def reject_signal(self, token: str) -> bool:
        """거부 콜백 — 토큰 검증 후 알림."""
        if not self._notifier:
            return False
        result = await self._notifier.handle_approval(token, "reject")
        if result is None:
            return False
        logger.info("신호 거부: token=%s", token)
        return True

    async def on_order_filled(
        self, order_id: int, filled_price: int, signal: object, quantity: int = 0
    ) -> None:
        """매수 주문 체결 콜백 — 포지션 생성."""
        from modules.trading.strategy import TradeSignalData

        if isinstance(signal, TradeSignalData):
            await self._position_manager.open_position(
                signal, quantity, filled_price
            )

    def get_status(self) -> dict:
        """엔진 상태 조회용 공개 메서드."""
        monitor_active = (
            self._monitor_task is not None and not self._monitor_task.done()
        )
        return {
            "is_running": self._running,
            "queue_size": self._order_manager.get_queue_size(),
            "monitor_active": monitor_active,
        }

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
