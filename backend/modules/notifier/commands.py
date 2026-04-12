"""텔레그램 조회 명령어 핸들러."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from core.config import settings
from core.models.trading import PositionRecord, TradeHistory
from modules.collector.scheduler import PIPELINE_HEALTHY_KEY, PIPELINE_RUNNING_KEY

logger = logging.getLogger(__name__)


class CommandHandler:
    """텔레그램 조회 명령어를 처리한다."""

    def __init__(self, session_factory, redis_client, telegram_bot, collector_scheduler=None):
        self._session_factory = session_factory
        self._redis = redis_client
        self._bot = telegram_bot
        self._scheduler = collector_scheduler

    async def handle_status(self, chat_id: int) -> str:
        """활성 포지션 요약."""
        async with self._session_factory() as session:
            result = await session.execute(select(PositionRecord))
            positions = result.scalars().all()

        if not positions:
            return "📊 <b>포지션 현황</b>\n\n활성 포지션 없음"

        lines = ["📊 <b>포지션 현황</b>\n"]
        for p in positions:
            pnl_emoji = "🟢" if p.unrealized_pnl >= 0 else "🔴"
            lines.append(
                f"{pnl_emoji} <b>{p.stock_code}</b> {p.quantity}주\n"
                f"   평균가 {p.avg_price:,}원 → 현재 {p.current_price:,}원\n"
                f"   평가손익 {p.unrealized_pnl:+,}원"
            )
        return "\n".join(lines)

    async def handle_today(self, chat_id: int) -> str:
        """당일 매매 요약."""
        today = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()
        day_start = datetime.combine(today, time.min).replace(tzinfo=timezone.utc)
        day_end = datetime.combine(today, time.max).replace(tzinfo=timezone.utc)

        async with self._session_factory() as session:
            result = await session.execute(
                select(TradeHistory).where(
                    TradeHistory.exit_time >= day_start,
                    TradeHistory.exit_time <= day_end,
                )
            )
            trades = result.scalars().all()

        if not trades:
            return "📈 <b>오늘 매매 현황</b>\n\n거래 기록 없음"

        total = len(trades)
        total_pnl = sum(t.realized_pnl for t in trades)
        wins = sum(1 for t in trades if t.realized_pnl > 0)
        win_rate = (wins / total * 100) if total > 0 else 0

        pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
        return (
            f"📈 <b>오늘 매매 현황</b>\n\n"
            f"총 거래: {total}건\n"
            f"{pnl_emoji} 실현 손익: {total_pnl:+,}원\n"
            f"승률: {win_rate:.1f}%"
        )

    async def handle_mode(self, chat_id: int) -> str:
        """현재 거래 모드 표시."""
        env = settings.TRADING_ENV
        env_label = "모의거래" if env == "paper" else "실전거래"
        approval_mode = "반자동" if self._bot else "자동"
        return (
            f"⚙️ <b>현재 모드</b>\n\n"
            f"환경: {env_label}\n"
            f"매매: {approval_mode} 모드"
        )

    async def handle_pipeline(self, chat_id: int) -> str:
        """파이프라인 단계별 상태 조회."""
        if self._scheduler is None:
            return "⚠️ 스케줄러 미초기화"

        pipeline_status = await self._scheduler.get_pipeline_status()
        healthy = await self._redis.get(PIPELINE_HEALTHY_KEY)
        running = await self._redis.get(PIPELINE_RUNNING_KEY)

        status_emoji = {"success": "✅", "failed": "❌", "skipped": "⏭️", "pending": "⏳"}
        healthy_label = "🟢 정상" if healthy == "true" else "🔴 비정상"

        lines = [f"🔧 <b>파이프라인 상태</b>  {healthy_label}"]
        if running:
            lines.append("⚙️ <i>현재 실행 중...</i>")
        lines.append("")

        step_labels = {
            "premarket": "장전 수집",
            "etf_master": "ETF 마스터",
            "primary_screen": "1차 스크리닝",
            "etf": "ETF 시세",
            "dart": "DART 재무",
            "sentiment": "뉴스 센티멘트",
        }
        for step, label in step_labels.items():
            info = pipeline_status.get(step, {})
            status = info.get("status", "—")
            emoji = status_emoji.get(status, "❓")
            ts = info.get("timestamp", "")
            time_str = ts[11:19] if ts else ""
            lines.append(f"{emoji} {label}  <code>{time_str}</code>")

        lines.append("\n/recover — 장전 파이프라인 수동 복구")
        return "\n".join(lines)

    async def handle_recover(self, chat_id: int) -> str:
        """장전 파이프라인 수동 복구 트리거."""
        if self._scheduler is None:
            return "⚠️ 스케줄러 미초기화"

        running = await self._redis.get(PIPELINE_RUNNING_KEY)
        if running:
            return "⚙️ 파이프라인이 이미 실행 중입니다.\n/pipeline 으로 진행 상황을 확인하세요."

        # 락 선점 후 백그라운드 실행
        await self._redis.set(PIPELINE_RUNNING_KEY, "true", ttl=600)
        asyncio.create_task(self._scheduler.run_premarket_pipeline())

        return (
            "🚀 <b>장전 파이프라인 복구 시작</b>\n\n"
            "단계: 수집 → ETF → 스크리닝 → DART → 뉴스\n"
            "약 7~10분 소요됩니다.\n\n"
            "/pipeline 으로 진행 상황 확인"
        )

    async def handle_help(self, chat_id: int) -> str:
        """명령어 목록."""
        return (
            "📋 <b>명령어 목록</b>\n\n"
            "/status — 활성 포지션 현황\n"
            "/today — 오늘 매매 요약\n"
            "/mode — 현재 거래 모드\n"
            "/pipeline — 파이프라인 단계별 상태\n"
            "/recover — 장전 파이프라인 수동 복구\n"
            "/help — 명령어 목록"
        )

    async def dispatch(self, command: str, chat_id: int) -> str:
        """명령어를 분기 처리한다."""
        handlers = {
            "/status": self.handle_status,
            "/today": self.handle_today,
            "/mode": self.handle_mode,
            "/pipeline": self.handle_pipeline,
            "/recover": self.handle_recover,
            "/help": self.handle_help,
        }
        handler = handlers.get(command, self.handle_help)
        return await handler(chat_id)
