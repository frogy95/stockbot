"""매매 엔진 오케스트레이터 — 스크리닝->전략->리스크->주문 통합."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select

from core.clients.kis_rest import KISRestClient, OrderRequest
from core.models.settings import SystemSetting
from core.models.trading import PositionRecord
from core.redis import RedisClient
from modules.trading.eod_liquidator import EodLiquidator
from modules.trading.order_manager import OrderManager, _MARKET_ORDER_DIVISION
from modules.trading.position_manager import PositionManager
from modules.trading.position_sizer import PositionSizer
from modules.trading.risk_manager import RiskManager
from modules.trading.signal_generator import SignalGenerator

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")

_INFLIGHT_KEY_PREFIX = "exit:inflight:"
_INFLIGHT_TTL_SEC = 30  # 청산 폴링 최대 6초(3회x2초)보다 넉넉, 비정상 종료 시 자동 만료

# Phase 8 Sprint 2: 차단 관측성
# 텔레그램 알림이 나가는 차단 사유 (나머지는 로그만)
_ALERT_BLOCK_REASONS = {"pipeline_unhealthy", "risk_blocked"}
# 동일 (stock_code, reason) 알림 스팸 방지 TTL (초)
_BLOCK_ALERT_DEDUP_TTL = 300


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
        rest_client: KISRestClient | None = None,
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
        self._rest_client = rest_client
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

    async def _log_block(
        self,
        stock_code: str,
        reason: str,
        *,
        mode: str | None = None,
        breakout_tier: str | None = None,
        extra: dict | None = None,
    ) -> None:
        """차단 사유 구조화 로깅 + 선택적 텔레그램 알림 (5분 dedup).

        Args:
            stock_code: 종목 코드 (파이프라인 차단은 "-")
            reason: 차단 사유 키 (pipeline_unhealthy/eod_blocked/risk_blocked 등)
            mode: 매매 모드 (있으면 로그에 포함)
            breakout_tier: 진입 tier (있으면 로그에 포함)
            extra: 추가 구조화 필드 (detail dict)
        """
        details: dict = {
            "stock_code": stock_code,
            "block_reason": reason,
        }
        if mode is not None:
            details["mode"] = mode
        if breakout_tier is not None:
            details["breakout_tier"] = breakout_tier
        if extra:
            details.update(extra)
        logger.info("engine_block stock=%s reason=%s %s", stock_code, reason, details)

        # 선택적 텔레그램 알림 (risk_blocked / pipeline_unhealthy만, 5분 dedup)
        if reason not in _ALERT_BLOCK_REASONS or self._notifier is None:
            return
        dedup_key = f"engine:block:dedup:{stock_code}:{reason}"
        if await self._redis.get(dedup_key):
            return
        await self._redis.set(dedup_key, "1", ttl=_BLOCK_ALERT_DEDUP_TTL)
        try:
            await self._notifier.send_system_alert("risk_warning", str(details))
        except Exception:
            logger.exception("차단 사유 알림 전송 실패: %s/%s", stock_code, reason)

    async def process_screening_results(
        self, screened_candidates: list[dict]
    ) -> None:
        """2차 스크리닝 결과를 받아 매매 파이프라인을 실행."""
        # 스케줄러 파이프라인 미완료 시 불완전 데이터 기반 매매 차단
        pipeline_healthy = await self._redis.get("scheduler:pipeline_healthy")
        if pipeline_healthy != "true":
            await self._log_block(
                "-",
                "pipeline_unhealthy",
                extra={"pipeline_healthy": pipeline_healthy},
            )
            return

        # 14:30 이후 신규 진입 차단
        if self._eod_liquidator.is_entry_blocked():
            await self._log_block("-", "eod_blocked")
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
                await self._log_block(signal.stock_code, "manual_mode_skip", mode=mode)
                continue

            # 레버리지 여부 판별
            is_leverage = "레버리지" in signal.reason.get("is_leverage", "") if isinstance(
                signal.reason.get("is_leverage"), str
            ) else signal.reason.get("is_leverage", False)

            # 리스크 체크
            risk_result = await self._risk_manager.can_trade(is_leverage=is_leverage)
            if not risk_result.allowed:
                await self._log_block(
                    signal.stock_code,
                    "risk_blocked",
                    mode=mode,
                    breakout_tier=signal.reason.get("breakout_tier"),
                    extra={
                        "reason": risk_result.reason,
                        "risk_level": risk_result.risk_level,
                    },
                )
                continue

            # 후보 플래그 확인 (is_fallback, is_relaxed)
            candidate = candidate_map.get(signal.stock_code, {})
            auto_trade_blocked = (
                candidate.get("is_fallback", False) or candidate.get("is_relaxed", False)
            )
            candidate_ratio: float = candidate.get("position_size_ratio", 1.0)

            # Phase 8 Sprint 2: prev_close tier는 반 포지션 (추격매수 리스크 억제)
            breakout_tier = signal.reason.get("breakout_tier", "prev_high")
            tier_ratio = 0.5 if breakout_tier == "prev_close" else 1.0
            size_ratio: float = min(candidate_ratio, tier_ratio)
            logger.info(
                "진입 사이징: %s tier=%s candidate_ratio=%.2f tier_ratio=%.2f final=%.2f",
                signal.stock_code,
                breakout_tier,
                candidate_ratio,
                tier_ratio,
                size_ratio,
            )

            # 포지션 사이징 — 실잔고 조회
            balance_amount = 0
            if self._rest_client is not None:
                try:
                    balance = await self._rest_client.get_balance()
                    balance_amount = balance.available_cash
                    logger.debug("주문가능 예수금: %d원", balance_amount)
                except Exception:
                    logger.exception("잔고 조회 실패 — 주문 수량 계산 불가: %s", signal.stock_code)
                    await self._log_block(
                        signal.stock_code,
                        "balance_fetch_failed",
                        mode=mode,
                        breakout_tier=breakout_tier,
                    )
                    continue

            position_size = await self._position_sizer.calculate(
                signal.stock_code, signal.entry_price, balance_amount, size_ratio=size_ratio
            )
            if position_size.quantity == 0:
                await self._log_block(
                    signal.stock_code,
                    "quantity_zero",
                    mode=mode,
                    breakout_tier=breakout_tier,
                    extra={"balance": balance_amount, "size_ratio": size_ratio},
                )
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
        """포지션 모니터링 루프 (백그라운드).

        장 시간(09:00~15:30) 내에만 가격 수집→갱신→청산 조건 확인→청산 실행.
        """
        while self._running:
            try:
                now_kst = datetime.now(KST)
                t = now_kst.time()
                if not (time(9, 0) <= t <= time(15, 30)):
                    await asyncio.sleep(interval)
                    continue

                price_updates = await self._collect_price_updates()
                if price_updates:
                    await self._position_manager.update_prices(price_updates)

                exits = await self._position_manager.check_exit_conditions()
                for exit_info in exits:
                    await self._execute_exit(exit_info)
            except Exception:
                logger.exception("포지션 모니터링 오류")
            await asyncio.sleep(interval)

    async def _collect_price_updates(self) -> dict[str, int]:
        """활성 포지션의 실시간 가격을 수집한다 (Redis WS 우선 + REST 폴백)."""
        prices: dict[str, int] = {}

        # 활성 포지션의 stock_code 목록 조회
        if self._session_factory is None:
            return prices

        async with self._session_factory() as session:
            stmt = select(PositionRecord.stock_code)
            result = await session.execute(stmt)
            stock_codes = list(result.scalars().all())

        if not stock_codes:
            return prices

        for code in stock_codes:
            # Redis WS 데이터 우선
            raw = await self._redis.get(f"realtime:{code}:execution")
            if raw:
                try:
                    data = json.loads(raw)
                    price = int(data.get("current_price", 0))
                    if price > 0:
                        prices[code] = price
                        continue
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass

            # REST 폴백
            if self._rest_client is not None:
                try:
                    stock_price = await self._rest_client.get_stock_price(code)
                    if stock_price.price > 0:
                        prices[code] = stock_price.price
                except Exception:
                    logger.warning("가격 조회 실패 (다음 루프 재시도): %s", code)

        return prices

    async def _execute_exit(self, exit_info: dict) -> None:
        """청산 매도를 실행한다.

        1. in-flight 플래그 체크 — 이미 진행 중이면 스킵 (중복 매도 방지)
        2. 시장가 매도 주문 발송
        3. 체결 폴링 (최대 3회, 2초 간격)
        4. 체결 시 close_position 호출
        5. 알림 전송
        6. finally 블록에서 in-flight 플래그 삭제 (성공/실패 무관)
        """
        stock_code = exit_info["stock_code"]
        quantity = exit_info["quantity"]
        exit_reason = exit_info["exit_reason"]
        position_id = exit_info["position_id"]

        if self._rest_client is None:
            logger.error("REST 클라이언트 미설정 — 청산 실행 불가: %s", stock_code)
            return

        inflight_key = f"{_INFLIGHT_KEY_PREFIX}{stock_code}"
        if await self._redis.get(inflight_key):
            logger.info("in-flight 청산 진행 중 — 스킵: %s", stock_code)
            return
        await self._redis.set(inflight_key, "1", ttl=_INFLIGHT_TTL_SEC)

        try:
            order_req = OrderRequest(
                stock_code=stock_code,
                order_type="sell",
                quantity=quantity,
                price=0,
                order_division=_MARKET_ORDER_DIVISION,
            )
            try:
                response = await self._rest_client.place_order(order_req)
            except Exception:
                logger.exception("청산 매도 주문 실패: %s", stock_code)
                return

            order_no = response.order_no

            # 체결 폴링 (최대 3회 x 2초)
            exit_price = 0
            for poll in range(3):
                await asyncio.sleep(2.0)
                try:
                    status_data = await self._rest_client.get_order_status(order_no)
                    price = OrderManager._extract_filled_price(status_data, 0)
                    if price > 0:
                        exit_price = price
                        break
                except Exception:
                    logger.warning("청산 체결 조회 실패 (poll %d): %s", poll + 1, stock_code)

            if exit_price == 0:
                logger.warning("청산 체결 미확인 (다음 루프 재시도): %s", stock_code)
                return

            try:
                await self._position_manager.close_position(position_id, exit_price, exit_reason)
                logger.info("청산 완료: %s @%d (%s)", stock_code, exit_price, exit_reason)
            except Exception:
                logger.exception("close_position 실패: %s", stock_code)
                return

            if self._notifier:
                try:
                    await self._notifier.send_notification(
                        f"[청산 완료] {stock_code} @{exit_price:,}원 ({exit_reason})"
                    )
                except Exception:
                    logger.warning("청산 알림 전송 실패: %s", stock_code)
        finally:
            await self._redis.delete(inflight_key)

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
        self, order_id: int, filled_price: int, signal_data: object, quantity: int = 0
    ) -> None:
        """매수 주문 체결 콜백 — 포지션 생성 + 일일 거래 카운터 증가."""
        from modules.trading.strategy import TradeSignalData

        if isinstance(signal_data, TradeSignalData):
            await self._position_manager.open_position(
                signal_data, quantity, filled_price
            )
            # Phase 8 Sprint 2: 진입 체결 1회 = 일일 거래 1건
            # 카운터 실패가 포지션 생성을 막지 않도록 에러 격리
            try:
                await self._risk_manager.incr_daily_trade_count()
            except Exception:
                logger.exception(
                    "일일 거래 카운터 증가 실패 — 포지션 생성은 이미 완료됨: %s",
                    signal_data.stock_code,
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
