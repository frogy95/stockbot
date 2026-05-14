"""WS 구독 매니저 — 동적 추가/제거, 35종목 상한, asyncio.Lock 동시성 제어."""

import asyncio
import json
import logging
import time

from core.clients.kis_ws import KISWebSocketClient
from core.config import settings

logger = logging.getLogger(__name__)
# Phase 8.6 Sprint 5 T3 — trace 전용 logger (기존 로그와 혼재 금지, WS_TRACE_ENABLED=true 시에만 출력)
ws_trace_logger = logging.getLogger("ws_trace")

DEFAULT_TR_IDS = ["H0STCNT0", "H0STASP0"]


def _ws_trace(event: str, **fields) -> None:
    """WS subscribe/응답/카운터 구조화 trace.

    WS_TRACE_ENABLED=False면 즉시 return — 코드 경로 영향 0.
    """
    if not settings.WS_TRACE_ENABLED:
        return
    payload = {"event": event, "ts": time.time(), **fields}
    ws_trace_logger.info("ws_trace %s", json.dumps(payload, ensure_ascii=False))


class WSSubscriptionManager:
    """한투 WS 종목 구독 매니저.

    - 최대 35종목 운영 상한 (한투 제한 40 - 여유 5)
    - 우선순위 기반 로테이션: 상한 도달 시 가장 낮은 우선순위 종목 교체
    - asyncio.Lock으로 동시 구독 경쟁 조건 방지
    - _ws None 가드 (Phase 1 미해결 #3)
    """

    def __init__(
        self,
        ws_client: KISWebSocketClient,
        max_subscriptions: int = 35,
    ) -> None:
        self._ws = ws_client
        self._max = max_subscriptions
        self._lock = asyncio.Lock()
        # {stock_code: priority_score}
        self._subscriptions: dict[str, float] = {}
        self._tr_ids = DEFAULT_TR_IDS

    @property
    def count(self) -> int:
        return len(self._subscriptions)

    def get_subscribed_stocks(self) -> list[str]:
        return list(self._subscriptions.keys())

    async def subscribe(self, stock_code: str, priority: float = 0.0) -> bool:
        """종목 구독. 성공 시 True, 실패 시 False."""
        async with self._lock:
            _ws_trace(
                "subscribe_request",
                stock_code=stock_code,
                priority=priority,
                current_count=len(self._subscriptions),
                max=self._max,
                connected=bool(self._ws._ws is not None and self._ws.connected),
            )
            # _ws None 가드 (Phase 6에서 and→or 수정)
            if self._ws._ws is None or not self._ws.connected:
                logger.warning("WS 미연결 상태에서 구독 시도: %s", stock_code)
                _ws_trace("subscribe_reject", stock_code=stock_code, reason="not_connected")
                return False

            # 이미 구독 중이면 우선순위만 업데이트
            if stock_code in self._subscriptions:
                self._subscriptions[stock_code] = max(
                    self._subscriptions[stock_code], priority
                )
                _ws_trace("subscribe_already", stock_code=stock_code, priority=priority)
                return True

            # 상한 미만이면 구독
            if len(self._subscriptions) < self._max:
                ok = await self._do_subscribe(stock_code, priority)
                _ws_trace("subscribe_result", stock_code=stock_code, ok=ok, path="under_limit")
                return ok

            # 상한 도달: 가장 낮은 우선순위 종목과 비교
            min_code = min(self._subscriptions, key=self._subscriptions.get)
            min_priority = self._subscriptions[min_code]

            if priority > min_priority:
                await self._do_unsubscribe(min_code)
                ok = await self._do_subscribe(stock_code, priority)
                _ws_trace(
                    "subscribe_result",
                    stock_code=stock_code,
                    ok=ok,
                    path="rotate",
                    evicted=min_code,
                    evicted_priority=min_priority,
                )
                return ok

            logger.info("구독 상한 도달, 우선순위 부족: %s (%.1f)", stock_code, priority)
            _ws_trace(
                "subscribe_reject",
                stock_code=stock_code,
                reason="over_limit_low_priority",
                priority=priority,
                min_priority=min_priority,
            )
            return False

    async def unsubscribe(self, stock_code: str) -> bool:
        """종목 구독 해제."""
        async with self._lock:
            if self._ws._ws is None or not self._ws.connected:
                logger.warning("WS 미연결 상태에서 구독 해제 시도: %s", stock_code)
                return False

            if stock_code not in self._subscriptions:
                return True

            return await self._do_unsubscribe(stock_code)

    async def unsubscribe_all(self) -> None:
        """전체 구독 해제."""
        async with self._lock:
            for code in list(self._subscriptions.keys()):
                try:
                    await self._do_unsubscribe(code)
                except Exception:
                    logger.exception("구독 해제 실패: %s", code)

    async def _do_subscribe(self, stock_code: str, priority: float) -> bool:
        """실제 WS 구독 요청."""
        try:
            for tr_id in self._tr_ids:
                await self._ws.subscribe(stock_code, tr_id)
            self._subscriptions[stock_code] = priority
            logger.info("구독 추가: %s (priority=%.1f, total=%d)", stock_code, priority, len(self._subscriptions))
            return True
        except Exception:
            logger.exception("구독 요청 실패: %s", stock_code)
            return False

    async def _do_unsubscribe(self, stock_code: str) -> bool:
        """실제 WS 구독 해제 요청."""
        try:
            for tr_id in self._tr_ids:
                await self._ws.unsubscribe(stock_code, tr_id)
            self._subscriptions.pop(stock_code, None)
            logger.info("구독 해제: %s (total=%d)", stock_code, len(self._subscriptions))
            return True
        except Exception:
            logger.exception("구독 해제 요청 실패: %s", stock_code)
            return False
