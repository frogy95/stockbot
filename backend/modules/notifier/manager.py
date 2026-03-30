"""알림 매니저 — 텔레그램 알림과 승인 흐름을 조율한다."""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from sqlalchemy import func, select

from core.models.trading import TradeHistory
from modules.trading.strategy import TradeSignalData

logger = logging.getLogger(__name__)


class NotifierManager:
    """TelegramBot과 ApprovalManager를 조율하여 알림·승인 흐름을 처리한다."""

    def __init__(self, telegram_bot, approval_manager, session_factory):
        self._bot = telegram_bot
        self._approval = approval_manager
        self._session_factory = session_factory
        # 토큰 → message_id 매핑 (pending 상태 메시지 추적)
        self._pending_messages: dict[str, int] = {}

    async def notify_signal(
        self, signal: TradeSignalData, quantity: int, timeout_sec: int
    ) -> str:
        """매매 신호 발생 시 승인 요청 알림을 발송한다.

        Args:
            signal: 매매 신호 데이터
            quantity: 주문 수량
            timeout_sec: 승인 대기 시간(초)

        Returns:
            생성된 승인 토큰
        """
        # 승인 토큰 생성
        token = await self._approval.create_approval(signal, quantity, timeout_sec)

        # 텔레그램 신호 알림 발송 → message_id 반환
        message_id = await self._bot.send_signal_alert(signal, quantity, token)

        # pending 메시지 추적 등록
        self._pending_messages[token] = message_id

        return token

    async def handle_approval(self, token: str, action: str) -> dict | None:
        """사용자의 승인/거부 액션을 처리한다.

        Args:
            token: 승인 토큰
            action: "approve" 또는 "reject"

        Returns:
            처리 결과 dict (signal, quantity, action) 또는 None (무효/만료)
        """
        data = await self._approval.validate_approval(token)

        if data is None:
            # 이미 처리됐거나 만료된 토큰
            return None

        # 메시지 수정 — 버튼 제거 및 결과 표시
        message_id = self._pending_messages.pop(token, None)
        if message_id is not None:
            if action == "approve":
                edit_text = "✅ 승인됨"
            else:
                edit_text = "❌ 거부됨"
            await self._bot.edit_message(message_id, edit_text)

        return {
            "signal": data["signal"],
            "quantity": data["quantity"],
            "action": action,
        }

    async def notify_fill(
        self,
        stock_code: str,
        quantity: int,
        price: int,
        order_type: str,
    ) -> None:
        """체결 발생 시 텔레그램 알림을 발송한다."""
        text = self._bot.format_fill_message(stock_code, quantity, price, order_type)
        await self._bot.send_notification(text)

    async def notify_timeout(self, token: str) -> None:
        """승인 시간 만료 시 메시지를 수정하고 pending 목록에서 제거한다."""
        message_id = self._pending_messages.pop(token, None)

        if message_id is not None:
            await self._bot.edit_message(message_id, "⏰ 승인 시간 만료")
        else:
            logger.warning("notify_timeout: token=%s 에 해당하는 pending 메시지 없음", token)

    async def send_daily_report(self, session_factory=None) -> None:
        """당일 거래 내역을 집계하여 일일 리포트 알림을 발송한다."""
        # session_factory 파라미터 우선, 없으면 생성자 주입 값 사용
        factory = session_factory or self._session_factory

        today_start = datetime.combine(date.today(), datetime.min.time()).replace(
            tzinfo=timezone.utc
        )

        async with factory() as session:
            # 당일 trade_history 조회
            result = await session.execute(
                select(TradeHistory).where(TradeHistory.exit_time >= today_start)
            )
            records = result.scalars().all()

        total_trades = len(records)
        total_pnl = sum(r.realized_pnl for r in records)
        win_count = sum(1 for r in records if r.realized_pnl > 0)
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0.0

        stats = {
            "total_trades": total_trades,
            "total_pnl": total_pnl,
            "win_rate": win_rate,
        }

        text = self._bot.format_daily_report(stats)
        await self._bot.send_notification(text)
