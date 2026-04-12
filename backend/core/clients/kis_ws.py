"""한국투자증권 WebSocket 클라이언트 — 실시간 시세 수신용 기본 프레임."""

import asyncio
import json
import logging
from typing import Callable

import websockets
from websockets.exceptions import ConnectionClosed

from core.clients.kis_config import KISEnvironment
from core.clients.token_manager import KISTokenManager

logger = logging.getLogger(__name__)

MAX_RECONNECT_ATTEMPTS = 7
BACKOFF_BASE = 2  # 초기 대기 2초, 지수 백오프


class KISWebSocketClient:
    """한투 WebSocket 실시간 시세 클라이언트.

    Phase 1에서는 raw 데이터 전달만 담당하며, 상세 파싱은 Phase 2+에서 구현한다.
    """

    def __init__(
        self,
        env: KISEnvironment,
        token_manager: KISTokenManager,
    ) -> None:
        self._env = env
        self._token_manager = token_manager
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._subscriptions: set[tuple[str, str]] = set()
        self._connected: bool = False
        self._receive_task: asyncio.Task | None = None
        self._on_data: Callable | None = None
        self._on_ws_failure: Callable | None = None
        self._on_reconnect_success: Callable | None = None
        self._approval_key: str | None = None

    # ── 공개 속성 ──────────────────────────────────────────

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def subscription_count(self) -> int:
        return len(self._subscriptions)

    def set_on_data(self, callback: Callable) -> None:
        """실시간 데이터 수신 콜백 등록. callback(tr_id, raw_data) 시그니처."""
        self._on_data = callback

    def set_on_ws_failure(self, callback: Callable) -> None:
        """WS 재연결 최대 실패 시 호출할 콜백 등록."""
        self._on_ws_failure = callback

    def set_on_reconnect_success(self, callback: Callable) -> None:
        """WS 재연결 성공 후 구독 복원 완료 시 호출할 콜백 등록."""
        self._on_reconnect_success = callback

    # ── 연결 / 해제 ────────────────────────────────────────

    async def connect(self) -> None:
        """WebSocket 연결 및 수신 루프 시작."""
        self._approval_key = await self._token_manager.get_approval_key()
        self._ws = await websockets.connect(
            self._env.ws_url,
            ping_interval=30,
            ping_timeout=10,
            open_timeout=10,
        )
        self._connected = True
        self._receive_task = asyncio.create_task(self._receive_loop())
        logger.info("WebSocket 연결 완료: %s", self._env.ws_url)

    async def disconnect(self) -> None:
        """WebSocket 연결 종료."""
        self._connected = False
        if self._receive_task is not None:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        logger.info("WebSocket 연결 종료")

    # ── 구독 / 해제 ────────────────────────────────────────

    async def subscribe(self, stock_code: str, tr_id: str = "H0STCNT0") -> None:
        """실시간 시세 구독 요청."""
        if self._ws is None:
            logger.warning("WS 미연결 상태에서 구독 시도: %s (%s)", stock_code, tr_id)
            return
        msg = self._build_subscription_message(stock_code, tr_id, tr_type="1")
        await self._ws.send(json.dumps(msg))
        self._subscriptions.add((stock_code, tr_id))
        logger.info("구독 추가: %s (%s)", stock_code, tr_id)

    async def unsubscribe(self, stock_code: str, tr_id: str = "H0STCNT0") -> None:
        """실시간 시세 구독 해제 요청."""
        if self._ws is None:
            logger.warning("WS 미연결 상태에서 구독 해제 시도: %s (%s)", stock_code, tr_id)
            return
        msg = self._build_subscription_message(stock_code, tr_id, tr_type="2")
        await self._ws.send(json.dumps(msg))
        self._subscriptions.discard((stock_code, tr_id))
        logger.info("구독 해제: %s (%s)", stock_code, tr_id)

    # ── 내부 메서드 ────────────────────────────────────────

    def _build_subscription_message(
        self, stock_code: str, tr_id: str, tr_type: str
    ) -> dict:
        """구독/해제 요청 메시지 생성."""
        return {
            "header": {
                "approval_key": self._approval_key,
                "custtype": "P",
                "tr_type": tr_type,
                "content-type": "utf-8",
            },
            "body": {
                "input": {
                    "tr_id": tr_id,
                    "tr_key": stock_code,
                },
            },
        }

    async def _receive_loop(self) -> None:
        """수신 루프 — 연결 끊김 시 자동 재연결."""
        try:
            while self._connected:
                try:
                    message = await self._ws.recv()
                    await self._on_message(message)
                except ConnectionClosed as e:
                    if self._connected:
                        code = e.rcvd.code if e.rcvd else None
                        reason = e.rcvd.reason if e.rcvd else ""
                        logger.warning("WebSocket 연결 끊김: code=%s reason=%s", code, reason)
                        await self._reconnect()
                    break
        except asyncio.CancelledError:
            pass

    async def _invoke_callback(self, callback: Callable | None, name: str) -> None:
        """콜백을 안전하게 호출한다. 코루틴 여부를 자동 감지하여 await 처리."""
        if callback is None:
            return
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback()
            else:
                callback()
        except Exception:
            logger.exception("%s 콜백 실행 오류", name)

    async def _on_message(self, message: str) -> None:
        """수신 메시지 처리.

        - JSON 메시지: 서버 응답(구독 확인 등) 로깅
        - 파이프 구분 메시지: tr_id 추출 후 on_data 콜백 호출
        """
        # JSON 응답 (구독 확인, 에러 등)
        try:
            data = json.loads(message)
            logger.info("서버 응답: %s", data)
            return
        except (json.JSONDecodeError, TypeError):
            pass

        # 파이프 구분 실시간 데이터
        if "|" in message:
            parts = message.split("|")
            tr_id = parts[0] if parts else ""
            if self._on_data is not None:
                self._on_data(tr_id, message)

    async def _reconnect(self) -> None:
        """지수 백오프로 자동 재연결, 기존 구독 복원."""
        # 기존 수신 루프 정리 (ConcurrencyError 방지)
        if self._receive_task is not None:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        subscriptions_snapshot = set(self._subscriptions)

        for attempt in range(MAX_RECONNECT_ATTEMPTS):
            wait = BACKOFF_BASE * (2 ** attempt)
            logger.info("재연결 시도 %d/%d (%d초 대기)", attempt + 1, MAX_RECONNECT_ATTEMPTS, wait)
            await asyncio.sleep(wait)

            try:
                self._approval_key = await self._token_manager.get_approval_key()
                self._ws = await websockets.connect(
                    self._env.ws_url,
                    ping_interval=30,
                    ping_timeout=10,
                    open_timeout=10,
                )
                self._connected = True
                logger.info("재연결 성공")

                # 기존 구독 복원 (종목 간 딜레이로 구독 버스트 방지)
                try:
                    stocks: dict[str, list[str]] = {}
                    for stock_code, tr_id in subscriptions_snapshot:
                        stocks.setdefault(stock_code, []).append(tr_id)

                    total = len(stocks)
                    for idx, (stock_code, tr_ids) in enumerate(stocks.items(), start=1):
                        for tr_id in tr_ids:
                            await self.subscribe(stock_code, tr_id)
                        if idx < total:
                            await asyncio.sleep(self._env.ws_reconnect_delay)
                        if idx % 10 == 0 or idx == total:
                            logger.info("구독 복원 중: %d/%d 종목", idx, total)
                except Exception:
                    logger.exception("구독 복원 실패 — 수신 루프는 시작")

                # 수신 루프는 구독 복원 성공/실패 관계없이 항상 시작
                self._receive_task = asyncio.create_task(self._receive_loop())

                await self._invoke_callback(self._on_reconnect_success, "WS 재연결 성공")
                return

            except Exception as e:
                logger.error("재연결 실패 (%d/%d): %s", attempt + 1, MAX_RECONNECT_ATTEMPTS, e)
                # 연결이 열려 있으면 닫아 누수 방지
                if self._ws is not None:
                    try:
                        await self._ws.close()
                    except Exception:
                        pass
                    self._ws = None
                self._connected = False

        self._connected = False
        logger.error("최대 재연결 횟수 초과, 연결 종료")
        await self._invoke_callback(self._on_ws_failure, "WS 실패")
