"""리스크 매니저 — 매매 전 리스크 체크 및 비상 정지 관리."""
from __future__ import annotations

from datetime import datetime, time, date, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from core.config import settings
from core.models.settings import SystemSetting
from core.models.trading import PositionRecord, TradeHistory
from core.redis import RedisClient


# --- Redis 키 상수 ---
REDIS_EMERGENCY_STOP = "risk:emergency_stop"
REDIS_COOLDOWN = "risk:cooldown"
REDIS_CONSECUTIVE_LOSS = "risk:consecutive_loss_count"


class RiskCheckResult(BaseModel):
    """리스크 체크 결과."""

    allowed: bool
    reason: str | None = None
    risk_level: str = "normal"  # "normal", "warning", "blocked", "emergency"


class RiskSettingsLocked(Exception):
    """장중 리스크 설정 변경 시도 시 발생."""


class RiskManager:
    """매매 전 리스크 체크를 수행하는 매니저.

    모든 리스크 파라미터는 settings 테이블에서 로드하며,
    비상 정지/쿨다운 등 실시간 상태는 Redis로 관리한다.
    """

    # 기본값 (settings 테이블에 값이 없을 때 사용)
    DEFAULTS: dict[str, str] = {
        "daily_max_loss_pct": "-3.0",
        "max_position_count": "5",
        "max_leverage_position_count": "2",
        "emergency_stop_pct": "-4.0",
        "consecutive_loss_stop": "3",
        "cooldown_trigger_count": "2",
        "cooldown_duration_min": "60",
        "no_entry_start": "09:00",
        "no_entry_end": "09:30",
        "no_new_entry_time": "14:30",
        "risk_lock_during_trading": "true",
    }

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        redis_client: RedisClient,
    ):
        self._session_factory = session_factory
        self._redis = redis_client
        self._settings: dict[str, str] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    # 설정 로드
    # ------------------------------------------------------------------

    async def load_settings(self) -> None:
        """settings 테이블에서 리스크 파라미터를 로드하여 내부 캐시에 저장."""
        async with self._session_factory() as session:
            stmt = select(SystemSetting).where(
                SystemSetting.category == "risk"
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()

        self._settings = {row.key: row.value for row in rows}
        self._loaded = True

    def _get(self, key: str) -> str:
        """설정 값 조회. 캐시 → 기본값 순서."""
        return self._settings.get(key, self.DEFAULTS.get(key, ""))

    def _get_float(self, key: str) -> float:
        return float(self._get(key))

    def _get_int(self, key: str) -> int:
        return int(self._get(key))

    def _get_time(self, key: str) -> time:
        parts = self._get(key).split(":")
        return time(int(parts[0]), int(parts[1]))

    # ------------------------------------------------------------------
    # 메인 체크
    # ------------------------------------------------------------------

    async def can_trade(self, is_leverage: bool = False) -> RiskCheckResult:
        """모든 리스크 체크를 순차 실행하고 결과를 반환."""
        # 비상 정지 (최우선)
        if await self.check_emergency_stop():
            return RiskCheckResult(
                allowed=False,
                reason="비상 정지 활성화 — 일일 손실이 비상 한도를 초과했습니다",
                risk_level="emergency",
            )

        # 시간대 제한
        if not self.check_time_restriction():
            return RiskCheckResult(
                allowed=False,
                reason="현재 시간대는 신규 진입이 제한됩니다",
                risk_level="blocked",
            )

        # 쿨다운
        if await self.check_cooldown():
            return RiskCheckResult(
                allowed=False,
                reason="쿨다운 기간 중 — 연속 손절로 매매가 일시 정지되었습니다",
                risk_level="blocked",
            )

        # 연속 손절
        if await self.check_consecutive_loss():
            return RiskCheckResult(
                allowed=False,
                reason="연속 손절 한도 초과 — 매매가 정지되었습니다",
                risk_level="blocked",
            )

        # 일일 손실
        if await self.check_daily_loss():
            return RiskCheckResult(
                allowed=False,
                reason="일일 최대 손실 한도에 도달했습니다",
                risk_level="blocked",
            )

        # 포지션 수 제한
        if not await self.check_position_limit(is_leverage):
            return RiskCheckResult(
                allowed=False,
                reason="최대 포지션 수를 초과했습니다"
                if not is_leverage
                else "최대 레버리지 포지션 수를 초과했습니다",
                risk_level="warning",
            )

        return RiskCheckResult(
            allowed=True,
            reason=None,
            risk_level="normal",
        )

    # ------------------------------------------------------------------
    # 개별 체크 메서드
    # ------------------------------------------------------------------

    async def check_daily_loss(self) -> bool:
        """일일 실현+미실현 합산 손실이 한도를 초과했는지 확인.

        Returns:
            True이면 한도 초과 (매매 불가)
        """
        max_loss_pct = self._get_float("daily_max_loss_pct")  # 음수

        async with self._session_factory() as session:
            # 미실현 손익 합계 (활성 포지션)
            unrealized_stmt = select(
                func.coalesce(func.sum(PositionRecord.unrealized_pnl), 0)
            )
            unrealized_result = await session.execute(unrealized_stmt)
            unrealized_pnl = int(unrealized_result.scalar_one())

            # 오늘 실현 손익 합계
            today_start = datetime.combine(
                datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date(), time.min
            )
            realized_stmt = select(
                func.coalesce(func.sum(TradeHistory.realized_pnl), 0)
            ).where(TradeHistory.exit_time >= today_start)
            realized_result = await session.execute(realized_stmt)
            realized_pnl = int(realized_result.scalar_one())

            # 포지션 원금 합계 (avg_price * quantity)
            capital_stmt = select(
                func.coalesce(
                    func.sum(PositionRecord.avg_price * PositionRecord.quantity), 0
                )
            )
            capital_result = await session.execute(capital_stmt)
            total_capital = int(capital_result.scalar_one())

        total_pnl = unrealized_pnl + realized_pnl
        if total_capital == 0:
            return False

        loss_pct = (total_pnl / total_capital) * 100
        return loss_pct <= max_loss_pct  # max_loss_pct는 음수

    async def check_position_limit(self, is_leverage: bool = False) -> bool:
        """활성 포지션 수가 한도 이내인지 확인.

        Returns:
            True이면 한도 이내 (매매 가능), False이면 초과
        """
        max_count = self._get_int("max_position_count")

        async with self._session_factory() as session:
            count_stmt = select(func.count(PositionRecord.id))
            result = await session.execute(count_stmt)
            current_count = result.scalar_one()

        if current_count >= max_count:
            return False

        if is_leverage:
            max_lev = self._get_int("max_leverage_position_count")
            # 레버리지 포지션 수는 별도 카운트가 필요하지만,
            # 현재 모델에 is_leverage 필드가 없으므로 Redis 카운터 활용
            lev_count_str = await self._redis.get("risk:leverage_position_count")
            lev_count = int(lev_count_str) if lev_count_str else 0
            if lev_count >= max_lev:
                return False

        return True

    async def check_emergency_stop(self) -> bool:
        """비상 정지 플래그가 활성화되어 있는지 확인.

        Returns:
            True이면 비상 정지 상태
        """
        flag = await self._redis.get(REDIS_EMERGENCY_STOP)
        return flag == "1"

    async def check_consecutive_loss(self) -> bool:
        """연속 손절 횟수가 한도를 초과했는지 확인.

        Returns:
            True이면 한도 초과 (매매 불가)
        """
        limit = self._get_int("consecutive_loss_stop")
        count_str = await self._redis.get(REDIS_CONSECUTIVE_LOSS)
        count = int(count_str) if count_str else 0
        return count >= limit

    async def check_cooldown(self) -> bool:
        """쿨다운 상태인지 확인 (Redis TTL 키 존재 여부).

        Returns:
            True이면 쿨다운 중 (매매 불가)
        """
        ttl = await self._redis.ttl(REDIS_COOLDOWN)
        return ttl > 0

    def check_time_restriction(self) -> bool:
        """현재 시각이 매매 허용 시간대인지 확인.

        - 09:00~09:30: 관망 시간 (진입 불가)
        - 14:30 이후: 신규 진입 차단

        Returns:
            True이면 매매 가능, False이면 시간 제한
        """
        now = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).time()
        no_entry_start = self._get_time("no_entry_start")
        no_entry_end = self._get_time("no_entry_end")
        no_new_entry = self._get_time("no_new_entry_time")

        # 관망 시간대
        if no_entry_start <= now <= no_entry_end:
            return False

        # 장 마감 전 진입 차단
        if now >= no_new_entry:
            return False

        return True

    # ------------------------------------------------------------------
    # 상태 업데이트
    # ------------------------------------------------------------------

    async def record_loss(self) -> None:
        """손절 발생 시 연속 손절 카운터를 증가시키고 쿨다운을 트리거한다."""
        count_str = await self._redis.get(REDIS_CONSECUTIVE_LOSS)
        count = int(count_str) if count_str else 0
        count += 1
        await self._redis.set(REDIS_CONSECUTIVE_LOSS, str(count))

        # 쿨다운 트리거 체크
        trigger = self._get_int("cooldown_trigger_count")
        if count >= trigger:
            duration_min = self._get_int("cooldown_duration_min")
            await self._redis.set(
                REDIS_COOLDOWN, "1", ttl=duration_min * 60
            )

        # 비상 정지 체크: 일일 손실이 비상 한도 초과 시 Redis 플래그
        emergency_pct = self._get_float("emergency_stop_pct")
        async with self._session_factory() as session:
            unrealized_stmt = select(
                func.coalesce(func.sum(PositionRecord.unrealized_pnl), 0)
            )
            unrealized_result = await session.execute(unrealized_stmt)
            unrealized_pnl = int(unrealized_result.scalar_one())

            today_start = datetime.combine(
                datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date(), time.min
            )
            realized_stmt = select(
                func.coalesce(func.sum(TradeHistory.realized_pnl), 0)
            ).where(TradeHistory.exit_time >= today_start)
            realized_result = await session.execute(realized_stmt)
            realized_pnl = int(realized_result.scalar_one())

            capital_stmt = select(
                func.coalesce(
                    func.sum(PositionRecord.avg_price * PositionRecord.quantity), 0
                )
            )
            capital_result = await session.execute(capital_stmt)
            total_capital = int(capital_result.scalar_one())

        if total_capital > 0:
            total_pnl = unrealized_pnl + realized_pnl
            loss_pct = (total_pnl / total_capital) * 100
            if loss_pct <= emergency_pct:
                await self._redis.set(REDIS_EMERGENCY_STOP, "1")

    async def reset_daily_counters(self) -> None:
        """일일 카운터 초기화 (장 시작 전 호출)."""
        await self._redis.delete(REDIS_CONSECUTIVE_LOSS)
        await self._redis.delete(REDIS_COOLDOWN)
        await self._redis.delete(REDIS_EMERGENCY_STOP)

    # ------------------------------------------------------------------
    # 상태 조회
    # ------------------------------------------------------------------

    async def get_risk_status(self) -> dict[str, Any]:
        """현재 리스크 상태 요약을 반환."""
        emergency = await self.check_emergency_stop()
        cooldown_ttl = await self._redis.ttl(REDIS_COOLDOWN)
        consec_str = await self._redis.get(REDIS_CONSECUTIVE_LOSS)
        consecutive_losses = int(consec_str) if consec_str else 0

        async with self._session_factory() as session:
            pos_count_result = await session.execute(
                select(func.count(PositionRecord.id))
            )
            position_count = pos_count_result.scalar_one()

        return {
            "emergency_stop": emergency,
            "cooldown_active": cooldown_ttl > 0,
            "cooldown_remaining_sec": max(cooldown_ttl, 0),
            "consecutive_losses": consecutive_losses,
            "consecutive_loss_limit": self._get_int("consecutive_loss_stop"),
            "position_count": position_count,
            "max_position_count": self._get_int("max_position_count"),
            "daily_max_loss_pct": self._get_float("daily_max_loss_pct"),
            "emergency_stop_pct": self._get_float("emergency_stop_pct"),
            "settings_loaded": self._loaded,
        }

    # ------------------------------------------------------------------
    # 장중 설정 변경 방지
    # ------------------------------------------------------------------

    def assert_settings_unlocked(self) -> None:
        """장중(09:00~15:30)에 리스크 설정 변경을 시도하면 예외 발생."""
        if self._get("risk_lock_during_trading").lower() != "true":
            return

        now = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).time()
        market_open = time(9, 0)
        market_close = time(15, 30)

        if market_open <= now <= market_close:
            raise RiskSettingsLocked(
                "장중(09:00~15:30)에는 리스크 설정을 변경할 수 없습니다"
            )
