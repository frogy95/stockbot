"""텔레그램 봇 — 웹훅 수신, 콜백 처리, 메시지 포맷팅."""
from __future__ import annotations

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from modules.notifier.approval import ApprovalManager
from modules.trading.strategy import TradeSignalData


class TelegramBot:
    """텔레그램 봇 인터페이스. 메시지 발송, 콜백 파싱, 웹훅 관리를 담당한다."""

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        approval_manager: ApprovalManager,
    ) -> None:
        self._bot = Bot(token=bot_token)
        # 단일 사용자 화이트리스트 (정수로 변환하여 저장)
        self._authorized_chat_id = int(chat_id)
        self._approval_manager = approval_manager

    # -------------------------------------------------------------------------
    # 메시지 포맷팅
    # -------------------------------------------------------------------------

    def format_signal_message(
        self,
        signal: TradeSignalData,
        quantity: int,
        token: str,
    ) -> tuple[str, InlineKeyboardMarkup]:
        """매매 신호 데이터를 HTML 메시지와 인라인 키보드로 변환한다."""
        direction = "매수" if signal.signal_type == "buy" else "매도"
        confidence_pct = int(signal.confidence * 100)

        # 근거 요약: dict 항목을 줄바꿈 목록으로 구성
        reason_lines = "\n".join(
            f"  • {key}: {value}" for key, value in signal.reason.items()
        )

        text = (
            f"<b>[매매 신호] {direction} 승인 요청</b>\n"
            f"\n"
            f"종목코드: <code>{signal.stock_code}</code>\n"
            f"전략: {signal.strategy_name}\n"
            f"방향: {direction}\n"
            f"수량: {quantity:,}주\n"
            f"진입가: {signal.entry_price:,}원\n"
            f"손절가: {signal.stop_loss:,}원\n"
            f"목표가: {signal.take_profit:,}원\n"
            f"신뢰도: {confidence_pct}%\n"
            f"\n"
            f"<b>신호 근거</b>\n"
            f"{reason_lines}"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ 승인", callback_data=f"approve:{token}"),
                InlineKeyboardButton("❌ 거부", callback_data=f"reject:{token}"),
            ]
        ])
        return text, keyboard

    def format_fill_message(
        self,
        stock_code: str,
        quantity: int,
        price: int,
        order_type: str,
    ) -> str:
        """체결 데이터를 HTML 메시지로 변환한다."""
        direction = "매수" if order_type == "buy" else "매도"
        total_amount = quantity * price

        return (
            f"<b>[체결 확인] {direction}</b>\n"
            f"\n"
            f"종목코드: <code>{stock_code}</code>\n"
            f"방향: {direction}\n"
            f"수량: {quantity:,}주\n"
            f"체결가: {price:,}원\n"
            f"총금액: {total_amount:,}원"
        )

    def format_daily_report(self, stats: dict) -> str:
        """일일 리포트 통계를 HTML 메시지로 변환한다."""
        total_trades = stats.get("total_trades", 0)
        realized_pnl = stats.get("realized_pnl", 0)
        win_rate = stats.get("win_rate", 0.0)
        positions = stats.get("positions", [])

        win_rate_pct = int(win_rate * 100)
        pnl_sign = "+" if realized_pnl >= 0 else ""

        # 포지션 목록 요약
        if positions:
            position_lines = "\n".join(
                f"  • {p}" for p in positions
            )
            position_section = f"\n<b>보유 포지션</b>\n{position_lines}"
        else:
            position_section = "\n보유 포지션 없음"

        return (
            f"<b>[일일 리포트]</b>\n"
            f"\n"
            f"총 거래: {total_trades}건\n"
            f"실현 손익: {pnl_sign}{realized_pnl:,}원\n"
            f"승률: {win_rate_pct}%"
            f"{position_section}"
        )

    # -------------------------------------------------------------------------
    # 메시지 발송
    # -------------------------------------------------------------------------

    async def send_signal_alert(
        self,
        signal: TradeSignalData,
        quantity: int,
        token: str,
    ) -> int:
        """승인 요청 메시지와 인라인 버튼을 발송하고 message_id를 반환한다."""
        text, keyboard = self.format_signal_message(signal, quantity, token)
        message = await self._bot.send_message(
            chat_id=self._authorized_chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        return message.message_id

    async def send_notification(self, text: str) -> int:
        """일반 텍스트 알림을 발송하고 message_id를 반환한다."""
        message = await self._bot.send_message(
            chat_id=self._authorized_chat_id,
            text=text,
            parse_mode="HTML",
        )
        return message.message_id

    async def edit_message(self, message_id: int, text: str) -> None:
        """승인/거부 후 기존 메시지를 수정하고 인라인 버튼을 제거한다."""
        await self._bot.edit_message_text(
            chat_id=self._authorized_chat_id,
            message_id=message_id,
            text=text,
            parse_mode="HTML",
            reply_markup=None,
        )

    # -------------------------------------------------------------------------
    # 콜백 처리
    # -------------------------------------------------------------------------

    def parse_callback_data(self, data: str) -> tuple[str, str]:
        """콜백 데이터 문자열에서 action과 token을 파싱한다.

        예: "approve:some-uuid" -> ("approve", "some-uuid")
        """
        action, _, token = data.partition(":")
        return action, token

    def is_authorized(self, chat_id: int) -> bool:
        """발신 chat_id가 화이트리스트에 포함되어 있는지 검증한다."""
        return chat_id == self._authorized_chat_id

    # -------------------------------------------------------------------------
    # 웹훅 관리
    # -------------------------------------------------------------------------

    async def set_webhook(self, url: str) -> None:
        """텔레그램 서버에 웹훅 URL을 등록한다."""
        await self._bot.set_webhook(url=url)

    async def delete_webhook(self) -> None:
        """종료 시 웹훅을 해제한다."""
        await self._bot.delete_webhook()
