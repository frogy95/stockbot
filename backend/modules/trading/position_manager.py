"""포지션 매니저 — 포지션 생명주기 관리 (진입/가격 갱신/청산 조건 판단/청산)."""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from core.models.trading import PositionRecord, TradeHistory
from modules.trading.risk_manager import REDIS_CONSECUTIVE_LOSS, RiskManager
from modules.trading.strategy import TradeSignalData

KST = ZoneInfo("Asia/Seoul")
REDIS_TRAILING_HIGHS_KEY = "trailing_highs"

logger = logging.getLogger(__name__)


class PositionManager:
    """포지션 매니저.

    포지션의 생성(open_position), 가격 갱신(update_prices),
    청산 조건 체크(check_exit_conditions), 청산(close_position)을 담당한다.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        redis_client,
        risk_manager: RiskManager,
    ):
        self._session_factory = session_factory
        self._redis = redis_client
        self._risk_manager = risk_manager
        # 종목별 트레일링 고점 (Redis `trailing_highs` HSET의 write-through 로컬 캐시)
        self._trailing_highs: dict[str, int] = {}

    async def load_trailing_highs(self) -> None:
        """서버 기동 시 Redis HSET에서 trailing_highs를 로컬 캐시로 복원한다."""
        data = await self._redis.hgetall(REDIS_TRAILING_HIGHS_KEY)
        restored: dict[str, int] = {}
        for code, value in data.items():
            try:
                restored[code] = int(value)
            except (TypeError, ValueError):
                logger.warning("trailing_highs 파싱 실패: %s=%r", code, value)
        self._trailing_highs = restored
        if restored:
            logger.info("trailing_highs Redis 복원: %d종목", len(restored))

    # ------------------------------------------------------------------
    # 포지션 진입
    # ------------------------------------------------------------------

    async def open_position(
        self,
        signal: TradeSignalData,
        quantity: int,
        filled_price: int,
    ) -> PositionRecord:
        """매수 체결 후 positions 테이블에 새 포지션 레코드를 생성한다.

        Args:
            signal: 매매 신호 (stop_loss, take_profit, strategy_name 포함)
            quantity: 체결 수량
            filled_price: 체결 가격

        Returns:
            생성된 PositionRecord 인스턴스
        """
        entry_time = datetime.now(KST)
        position = PositionRecord(
            stock_code=signal.stock_code,
            quantity=quantity,
            avg_price=filled_price,
            current_price=filled_price,
            unrealized_pnl=0,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            trailing_activated=False,
            entry_time=entry_time,
            strategy_name=signal.strategy_name,
        )
        async with self._session_factory() as session:
            session.add(position)
            await session.commit()
            await session.refresh(position)
        return position

    # ------------------------------------------------------------------
    # 가격 갱신
    # ------------------------------------------------------------------

    async def update_prices(self, price_updates: dict[str, int]) -> None:
        """실시간 가격 업데이트를 포지션에 반영한다.

        - current_price, unrealized_pnl 갱신
        - trailing_activated: current_price >= avg_price * 1.02 이면 True
        - _trailing_highs: trailing_activated인 종목은 고점 추적

        Args:
            price_updates: {stock_code: current_price} 딕셔너리
        """
        if not price_updates:
            return

        async with self._session_factory() as session:
            stmt = select(PositionRecord).where(
                PositionRecord.stock_code.in_(list(price_updates.keys()))
            )
            result = await session.execute(stmt)
            positions = result.scalars().all()

            for pos in positions:
                new_price = price_updates.get(pos.stock_code)
                if new_price is None:
                    continue

                pos.current_price = new_price
                pos.unrealized_pnl = (new_price - int(pos.avg_price)) * pos.quantity

                # 트레일링 스탑 활성화 체크 (수익률 2% 이상)
                if new_price >= int(pos.avg_price) * 1.02:
                    pos.trailing_activated = True

                # 트레일링 고점 업데이트 (write-through: 로컬 캐시 + Redis 동기화)
                if pos.trailing_activated:
                    prev_high = self._trailing_highs.get(pos.stock_code, 0)
                    if new_price > prev_high:
                        self._trailing_highs[pos.stock_code] = new_price
                        await self._redis.hset(
                            REDIS_TRAILING_HIGHS_KEY, pos.stock_code, str(new_price)
                        )

            await session.commit()

    # ------------------------------------------------------------------
    # 청산 조건 체크
    # ------------------------------------------------------------------

    async def check_exit_conditions(self) -> list[dict]:
        """모든 활성 포지션의 청산 조건을 순회하며 청산 대상을 반환한다.

        청산 우선순위:
        1. 손절: current_price <= stop_loss
        2. 익절: current_price >= take_profit
        3. 트레일링 스탑: trailing_activated=True, current_price <= trailing_high * 0.99
        4. 보합 청산: 진입 30분 경과 + 수익률 < 1%

        Returns:
            청산 대상 리스트. 각 항목: {stock_code, quantity, exit_reason, position_id}
        """
        to_exit: list[dict] = []
        now = datetime.now(KST)

        async with self._session_factory() as session:
            stmt = select(PositionRecord)
            result = await session.execute(stmt)
            positions = result.scalars().all()

            for pos in positions:
                current_price = int(pos.current_price)
                avg_price = int(pos.avg_price)
                stop_loss = int(pos.stop_loss)
                take_profit = int(pos.take_profit)

                exit_reason: str | None = None

                # 1. 손절
                if current_price <= stop_loss:
                    exit_reason = "stop_loss"

                # 2. 익절
                elif current_price >= take_profit:
                    exit_reason = "take_profit"

                # 3. 트레일링 스탑
                elif pos.trailing_activated:
                    trailing_high = self._trailing_highs.get(pos.stock_code, current_price)
                    if current_price <= trailing_high * 0.99:
                        exit_reason = "trailing"

                # 4. 보합 청산 (30분 경과 + 수익률 1% 미만)
                else:
                    # entry_time이 timezone-aware인지 확인하여 비교
                    entry_time = pos.entry_time
                    if entry_time.tzinfo is None:
                        entry_time = entry_time.replace(tzinfo=KST)
                    elapsed_sec = (now - entry_time).total_seconds()
                    if elapsed_sec >= 1800:
                        pnl_rate = (current_price - avg_price) / avg_price
                        if pnl_rate < 0.01:
                            exit_reason = "timeout"

                if exit_reason:
                    to_exit.append(
                        {
                            "stock_code": pos.stock_code,
                            "quantity": pos.quantity,
                            "exit_reason": exit_reason,
                            "position_id": pos.id,
                        }
                    )

        return to_exit

    # ------------------------------------------------------------------
    # 포지션 청산
    # ------------------------------------------------------------------

    async def close_position(
        self,
        position_id: int,
        exit_price: int,
        exit_reason: str,
    ) -> TradeHistory:
        """포지션을 청산하고 trade_history에 기록한다.

        1. positions 테이블에서 해당 포지션 조회
        2. trade_history에 실현 손익 기록
        3. positions에서 삭제
        4. 손절인 경우 risk_manager.record_loss() 호출
        5. _trailing_highs에서 해당 종목 제거

        Args:
            position_id: 청산할 포지션 ID
            exit_price: 청산 가격
            exit_reason: 청산 사유 (stop_loss / take_profit / trailing / timeout)

        Returns:
            생성된 TradeHistory 인스턴스
        """
        exit_time = datetime.now(KST)

        async with self._session_factory() as session:
            stmt = select(PositionRecord).where(PositionRecord.id == position_id)
            result = await session.execute(stmt)
            position = result.scalar_one()

            avg_price = int(position.avg_price)
            quantity = position.quantity
            entry_time = position.entry_time
            if entry_time.tzinfo is None:
                entry_time = entry_time.replace(tzinfo=KST)

            realized_pnl = (exit_price - avg_price) * quantity
            pnl_rate = (exit_price - avg_price) / avg_price * 100
            holding_duration_sec = int((exit_time - entry_time).total_seconds())

            history = TradeHistory(
                stock_code=position.stock_code,
                strategy_name=position.strategy_name,
                signal_confidence=None,
                entry_price=avg_price,
                exit_price=exit_price,
                quantity=quantity,
                realized_pnl=realized_pnl,
                pnl_rate=pnl_rate,
                holding_duration_sec=holding_duration_sec,
                entry_time=entry_time,
                exit_time=exit_time,
                exit_reason=exit_reason,
            )
            session.add(history)

            await session.delete(position)
            await session.commit()
            await session.refresh(history)

        # 트레일링 고점 제거 (로컬 캐시 + Redis 동기화)
        self._trailing_highs.pop(position.stock_code, None)
        await self._redis.hdel(REDIS_TRAILING_HIGHS_KEY, position.stock_code)

        # 손실 청산은 exit_reason 무관하게 카운터 증가.
        # 수익 청산은 연속 손절 카운터를 리셋하여 정상 매매 재개를 보장.
        if realized_pnl < 0:
            await self._risk_manager.record_loss()
        else:
            await self._redis.delete(REDIS_CONSECUTIVE_LOSS)

        return history
