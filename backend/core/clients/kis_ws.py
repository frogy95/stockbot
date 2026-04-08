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

    # ── 연결 / 해제 ────────────────────────────────────────

    async def connect(self) -> None:
        """WebSocket 연결 및 수신 루프 시작."""
        self._approval_key = await self._token_manager.get_approval_key()
        self._ws = await websockets.connect(
            self._env.ws_url,
            ping_interval=30,
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
        msg = self._build_subscription_message(stock_code, tr_id, tr_type="1")
        await self._ws.send(json.dumps(msg))
        self._subscriptions.add((stock_code, tr_id))
        logger.info("구독 추가: %s (%s)", stock_code, tr_id)

    async def unsubscribe(self, stock_code: str, tr_id: str = "H0STCNT0") -> None:
        """실시간 시세 구독 해제 요청."""
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
                except ConnectionClosed:
                    if self._connected:
                        logger.warning("WebSocket 연결 끊김, 재연결 시도")
                        await self._reconnect()
                    break
        except asyncio.CancelledError:
            pass

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
                )
                self._connected = True
                logger.info("재연결 성공")

                # 기존 구독 복원
                for stock_code, tr_id in subscriptions_snapshot:
                    await self.subscribe(stock_code, tr_id)

                # 수신 루프 재시작
                self._receive_task = asyncio.create_task(self._receive_loop())
                return

            except Exception as e:
                logger.error("재연결 실패 (%d/%d): %s", attempt + 1, MAX_RECONNECT_ATTEMPTS, e)

        self._connected = False
        logger.error("최대 재연결 횟수 초과, 연결 종료")
